from unittest.mock import patch

from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from accounts.models import Client
from accounts.tokens import issue_token
from automation import orchestrator as workflow
from automation.models import ApplyHistory, ApplySession
from config.asgi import application

DOM = {"title": "Job", "text": "Build", "fields": []}


def fake_plan(_dom, _client, _session_id):
    return {"actions": [{"op": "fill", "selector": "#a", "label": "A", "source": "rule", "value": "v"}],
            "skipped": [{"selector": "#g", "label": "Gender", "reason": "sensitive"}], "resume_file": ""}


class BossSocketTests(TransactionTestCase):
    async def open_boss(self):
        user = await get_user_model().objects.acreate_user(username="boss", password="x", is_staff=True)
        socket = WebsocketCommunicator(application, "/ws/boss/")
        await socket.connect()
        await socket.send_json_to({"type": "auth", "token": issue_token("boss", user.id)})
        self.assertEqual((await socket.receive_json_from())["type"], "auth_ok")
        self.assertEqual((await socket.receive_json_from())["type"], "state")
        return socket

    async def open_client(self, email="a@example.com"):
        client = await Client.objects.acreate(email=email, password="x")
        socket = WebsocketCommunicator(application, "/ws/client/")
        await socket.connect()
        await socket.send_json_to({"type": "auth", "token": issue_token("client", client.id)})
        await socket.receive_json_from()
        await socket.receive_json_from()
        return client, socket

    async def latest_state(self, socket):
        state = await socket.receive_json_from()
        while not await socket.receive_nothing():
            state = await socket.receive_json_from()
        return state

    async def test_client_token_is_refused(self):
        socket = WebsocketCommunicator(application, "/ws/boss/")
        await socket.connect()
        await socket.send_json_to({"type": "auth", "token": issue_token("client", 1)})
        self.assertEqual((await socket.receive_json_from())["type"], "auth_failed")
        await socket.disconnect()

    async def test_non_staff_user_is_refused(self):
        user = await get_user_model().objects.acreate_user(username="plain", password="x")
        socket = WebsocketCommunicator(application, "/ws/boss/")
        await socket.connect()
        await socket.send_json_to({"type": "auth", "token": issue_token("boss", user.id)})
        self.assertEqual((await socket.receive_json_from())["type"], "auth_failed")
        await socket.disconnect()

    async def test_sees_client_connect_url_and_disconnect(self):
        boss = await self.open_boss()
        client, socket = await self.open_client()
        state = await self.latest_state(boss)
        self.assertEqual(state["clients"][0]["email"], "a@example.com")
        self.assertTrue(state["clients"][0]["connected"])

        await socket.send_json_to({"type": "url", "url": "https://example.com/x"})
        state = await self.latest_state(boss)
        self.assertEqual(state["clients"][0]["url"], "https://example.com/x")

        await socket.disconnect()
        state = await self.latest_state(boss)
        self.assertFalse(state["clients"][0]["connected"])
        await boss.disconnect()

    @patch("automation.orchestrator.generate_plan", fake_plan)
    async def test_boss_drives_sync_and_fill(self):
        boss = await self.open_boss()
        client, socket = await self.open_client()
        await self.latest_state(boss)

        await boss.send_json_to({"type": "sync", "url": "https://jobs.example.com/1"})
        command = await socket.receive_json_from()
        self.assertEqual(command["url"], "https://jobs.example.com/1")
        state = await self.latest_state(boss)
        self.assertEqual(state["session"]["state"], "syncing")
        self.assertEqual(state["clients"][0]["action"], "syncing")

        await socket.send_json_to({"type": "sync_result", "session_id": command["session_id"], "ok": True})
        await socket.send_json_to({"type": "dom", "session_id": command["session_id"], "dom": DOM})
        await socket.receive_nothing()
        await workflow.drain_background_tasks()
        state = await self.latest_state(boss)
        self.assertEqual(state["session"]["state"], "ready")
        self.assertEqual(state["session"]["plans"][0]["actions"], 1)
        self.assertEqual(state["session"]["plans"][0]["skipped"][0]["reason"], "sensitive")
        self.assertNotIn("dom", state["session"])

        await boss.send_json_to({"type": "fill", "session_id": command["session_id"]})
        fill = await socket.receive_json_from()
        await socket.send_json_to({"type": "fill_result", "plan_id": fill["plan_id"],
                                   "results": [{"selector": "#a", "ok": True}]})
        await socket.receive_nothing()
        state = await self.latest_state(boss)
        self.assertEqual(state["session"]["state"], "done")
        history = await ApplyHistory.objects.aget(client=client)
        self.assertEqual(history.results["skipped"][0]["reason"], "sensitive")
        await socket.disconnect()
        await boss.disconnect()

    async def test_workflow_errors_are_reported_to_the_boss(self):
        boss = await self.open_boss()
        await boss.send_json_to({"type": "sync", "url": "https://example.com"})
        self.assertEqual((await boss.receive_json_from())["message"], "No enabled client is connected.")
        await boss.send_json_to({"type": "fill", "session_id": 12345})
        self.assertEqual((await boss.receive_json_from())["type"], "error")
        await boss.disconnect()

    @patch("automation.orchestrator.generate_plan", fake_plan)
    async def test_reconnect_during_fill_does_not_block_the_next_sync(self):
        client, old = await self.open_client()
        session_id = await workflow.start_sync("https://example.com/1")
        await old.receive_json_from()
        await old.send_json_to({"type": "dom", "session_id": session_id, "dom": DOM})
        await old.receive_nothing()
        await workflow.drain_background_tasks()
        await workflow.start_fill(session_id)

        new = WebsocketCommunicator(application, "/ws/client/")
        await new.connect()
        await new.send_json_to({"type": "auth", "token": issue_token("client", client.id)})
        await new.receive_json_from()
        await new.receive_json_from()

        self.assertEqual((await ApplySession.objects.aget(id=session_id)).state, "done")
        self.assertEqual((await ApplyHistory.objects.aget(client=client)).status, "failed")
        await workflow.start_sync("https://example.com/2")
        await old.disconnect()
        await new.disconnect()
