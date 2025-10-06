import base64
import tempfile
from pathlib import Path
from unittest.mock import patch

from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings

from accounts.models import Client
from accounts.tokens import issue_token
from automation import orchestrator as workflow
from automation.models import ApplyHistory, ApplySession, FillPlan
from config.asgi import application

DOM = {"title": "Job", "text": "Build", "fields": [{"selector": "#e", "type": "email", "label": "Email"}]}


def fake_plan(_dom, client, _session_id):
    return {"actions": [{"op": "fill", "selector": "#e", "label": "Email", "source": "rule", "value": client.email}],
            "skipped": [], "resume_file": ""}


class SocketTestCase(TransactionTestCase):
    def make_client(self, email="a@example.com", **extra):
        return Client.objects.create(email=email, password="x", profile={"full_name": "Ann Lee"}, **extra)

    async def open_client(self, client):
        socket = WebsocketCommunicator(application, "/ws/client/")
        await socket.connect()
        await socket.send_json_to({"type": "auth", "token": issue_token("client", client.id)})
        self.assertEqual((await socket.receive_json_from())["type"], "auth_ok")
        self.assertEqual((await socket.receive_json_from())["type"], "get_url")
        return socket


class AuthTests(SocketTestCase):
    async def test_bad_tokens_are_closed(self):
        for token in ("junk", issue_token("boss", 1), issue_token("client", 999)):
            socket = WebsocketCommunicator(application, "/ws/client/")
            await socket.connect()
            await socket.send_json_to({"type": "auth", "token": token})
            self.assertEqual((await socket.receive_json_from())["type"], "auth_failed")
            await socket.disconnect()

    async def test_messages_before_auth_are_refused(self):
        socket = WebsocketCommunicator(application, "/ws/client/")
        await socket.connect()
        await socket.send_json_to({"type": "url", "url": "https://example.com"})
        self.assertEqual((await socket.receive_json_from())["type"], "auth_failed")
        await socket.disconnect()

    async def test_silent_socket_is_closed(self):
        with patch("automation.consumers.AUTH_TIMEOUT_SECONDS", 0.01):
            socket = WebsocketCommunicator(application, "/ws/client/")
            await socket.connect()
            message = await socket.receive_output(timeout=1)
            self.assertEqual(message["code"], 4401)
            await socket.disconnect()

    async def test_invalid_json_does_not_crash_the_socket(self):
        client = await Client.objects.acreate(email="a@example.com", password="x")
        socket = await self.open_client(client)
        await socket.send_to(text_data="{not json")
        await socket.send_json_to({"type": "url", "url": "https://example.com/a"})
        await socket.disconnect()
        await client.arefresh_from_db()
        self.assertEqual(client.current_url, "https://example.com/a")


class ConnectionTests(SocketTestCase):
    async def test_connection_state_is_tracked(self):
        client = await Client.objects.acreate(email="a@example.com", password="x")
        socket = await self.open_client(client)
        await client.arefresh_from_db()
        self.assertTrue(client.connected)
        await socket.disconnect()
        await client.arefresh_from_db()
        self.assertFalse(client.connected)

    async def test_old_socket_closing_does_not_disconnect_a_reconnected_client(self):
        client = await Client.objects.acreate(email="a@example.com", password="x")
        old = await self.open_client(client)
        new = await self.open_client(client)
        await old.disconnect()
        await client.arefresh_from_db()
        self.assertTrue(client.connected)
        await new.disconnect()

    async def test_url_report_ignores_bad_schemes(self):
        client = await Client.objects.acreate(email="a@example.com", password="x")
        socket = await self.open_client(client)
        await socket.send_json_to({"type": "url", "url": "javascript:alert(1)"})
        await socket.send_json_to({"type": "url", "url": "https://example.com/job"})
        await socket.disconnect()
        await client.arefresh_from_db()
        self.assertEqual(client.current_url, "https://example.com/job")


@patch("automation.orchestrator.generate_plan", fake_plan)
class WorkflowTests(SocketTestCase):
    async def asyncSetUp(self):
        pass

    async def sync_two(self):
        first = await Client.objects.acreate(email="a@example.com", password="x")
        second = await Client.objects.acreate(email="b@example.com", password="x")
        await Client.objects.acreate(email="off@example.com", password="x", enabled=False)
        sockets = [await self.open_client(first), await self.open_client(second)]
        session_id = await workflow.start_sync("https://jobs.example.com/1")
        return first, second, sockets, session_id

    async def test_sync_asks_exactly_one_client_for_the_page(self):
        first, second, sockets, session_id = await self.sync_two()
        messages = [await socket.receive_json_from() for socket in sockets]
        self.assertEqual([m["type"] for m in messages], ["sync_url", "sync_url"])
        self.assertEqual([m["send_dom"] for m in messages], [True, False])
        self.assertEqual(messages[0]["url"], "https://jobs.example.com/1")
        await first.arefresh_from_db()
        self.assertEqual(first.action, "syncing")
        for socket in sockets:
            await socket.disconnect()

    async def test_full_workflow_records_history(self):
        first, second, sockets, session_id = await self.sync_two()
        for socket in sockets:
            await socket.receive_json_from()
            await socket.send_json_to({"type": "sync_result", "session_id": session_id, "ok": True})
        await sockets[0].send_json_to({"type": "dom", "session_id": session_id, "dom": DOM})
        await sockets[0].receive_nothing()
        await workflow.drain_background_tasks()

        session = await ApplySession.objects.aget(id=session_id)
        self.assertEqual(session.state, "ready")
        self.assertEqual(await FillPlan.objects.filter(session=session).acount(), 2)

        await workflow.start_fill(session_id)
        with self.assertRaises(workflow.WorkflowError):
            await workflow.start_fill(session_id)  # a double click sends nothing twice

        fills = [await socket.receive_json_from() for socket in sockets]
        self.assertEqual([f["actions"][0]["value"] for f in fills], ["a@example.com", "b@example.com"])
        await first.arefresh_from_db()
        self.assertEqual(first.action, "filling")

        ok = [{"selector": "#e", "ok": True}]
        await sockets[0].send_json_to({"type": "fill_result", "plan_id": fills[0]["plan_id"], "results": ok})
        await sockets[1].send_json_to({"type": "fill_result", "plan_id": fills[1]["plan_id"],
                                       "results": [{"selector": "#e", "ok": False, "error": "gone"}]})
        for socket in sockets:
            await socket.receive_nothing()
            await socket.disconnect()

        session = await ApplySession.objects.aget(id=session_id)
        self.assertEqual(session.state, "done")
        statuses = {h.client_id: h.status async for h in ApplyHistory.objects.all()}
        self.assertEqual(statuses, {first.id: "filled", second.id: "failed"})
        await first.arefresh_from_db()
        self.assertEqual(first.action, "no-action")

    async def test_page_from_another_client_is_ignored(self):
        first, second, sockets, session_id = await self.sync_two()
        await sockets[1].send_json_to({"type": "dom", "session_id": session_id, "dom": DOM})
        await sockets[1].receive_json_from()
        await sockets[1].receive_nothing()
        session = await ApplySession.objects.aget(id=session_id)
        self.assertEqual(session.state, "syncing")
        for socket in sockets:
            await socket.disconnect()

    async def test_client_cannot_report_results_for_another_plan(self):
        first, second, sockets, session_id = await self.sync_two()
        await sockets[0].send_json_to({"type": "dom", "session_id": session_id, "dom": DOM})
        await sockets[0].receive_json_from()
        await sockets[0].receive_nothing()
        await workflow.drain_background_tasks()
        await workflow.start_fill(session_id)
        await sockets[1].receive_json_from()
        fills = [await socket.receive_json_from() for socket in sockets]
        await sockets[1].send_json_to({"type": "fill_result", "plan_id": fills[0]["plan_id"], "results": []})
        await sockets[1].receive_nothing()
        self.assertEqual(await ApplyHistory.objects.filter(client=second).acount(), 0)
        for socket in sockets:
            await socket.disconnect()

    async def test_disconnect_during_fill_is_recorded_as_failure(self):
        first, second, sockets, session_id = await self.sync_two()
        await sockets[0].send_json_to({"type": "dom", "session_id": session_id, "dom": DOM})
        await sockets[0].receive_json_from()
        await sockets[0].receive_nothing()
        await workflow.drain_background_tasks()
        await workflow.start_fill(session_id)
        for socket in sockets:
            await socket.disconnect()
        session = await ApplySession.objects.aget(id=session_id)
        self.assertEqual(session.state, "done")
        self.assertEqual(await ApplyHistory.objects.filter(status="failed").acount(), 2)

    async def test_source_disconnect_fails_the_sync(self):
        first, second, sockets, session_id = await self.sync_two()
        await sockets[0].disconnect()
        session = await ApplySession.objects.aget(id=session_id)
        self.assertEqual(session.state, "failed")
        await sockets[1].disconnect()

    async def test_source_navigation_failure_fails_the_sync(self):
        first, second, sockets, session_id = await self.sync_two()
        await sockets[0].receive_json_from()
        await sockets[0].send_json_to({"type": "sync_result", "session_id": session_id, "ok": False, "error": "404"})
        await sockets[0].receive_nothing()
        session = await ApplySession.objects.aget(id=session_id)
        self.assertEqual((session.state, session.error), ("failed", "404"))
        for socket in sockets:
            await socket.disconnect()


class StartSyncValidationTests(SocketTestCase):
    async def test_rejects_bad_url_and_no_clients(self):
        with self.assertRaises(workflow.WorkflowError):
            await workflow.start_sync("javascript:alert(1)")
        with self.assertRaises(workflow.WorkflowError):
            await workflow.start_sync("https://example.com")

    async def test_new_sync_replaces_a_waiting_one(self):
        client = await Client.objects.acreate(email="a@example.com", password="x")
        socket = await self.open_client(client)
        old = await workflow.start_sync("https://example.com/1")
        await workflow.start_sync("https://example.com/2")
        self.assertEqual((await ApplySession.objects.aget(id=old)).state, "failed")
        await socket.disconnect()


class ResumeDeliveryTests(SocketTestCase):
    async def test_upload_plan_carries_the_resume(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(RESUME_DIR=Path(tmp)):
            path = Path(tmp) / "a@example.com.pdf"
            path.write_bytes(b"%PDF-1.4 data")

            def plan(_dom, _client, _session):
                return {"actions": [{"op": "upload", "selector": "#r", "label": "Resume", "source": "resume"}],
                        "skipped": [], "resume_file": str(path)}

            client = await Client.objects.acreate(email="a@example.com", password="x",
                                                  profile={"full_name": "Ann / Lee"})
            socket = await self.open_client(client)
            with patch("automation.orchestrator.generate_plan", plan):
                session_id = await workflow.start_sync("https://example.com/1")
                await socket.receive_json_from()
                await socket.send_json_to({"type": "dom", "session_id": session_id, "dom": DOM})
                await socket.receive_nothing()
                await workflow.drain_background_tasks()
            await workflow.start_fill(session_id)
            fill = await socket.receive_json_from()
            self.assertEqual(fill["resume"]["filename"], "Ann__Lee.pdf")
            self.assertEqual(base64.b64decode(fill["resume"]["base64"]), b"%PDF-1.4 data")
            await socket.disconnect()

    async def test_missing_resume_file_is_recorded_not_raised(self):
        def plan(_dom, _client, _session):
            return {"actions": [{"op": "upload", "selector": "#r", "label": "Resume", "source": "resume"}],
                    "skipped": [], "resume_file": "/nonexistent/x.pdf"}

        client = await Client.objects.acreate(email="a@example.com", password="x")
        socket = await self.open_client(client)
        with patch("automation.orchestrator.generate_plan", plan):
            session_id = await workflow.start_sync("https://example.com/1")
            await socket.receive_json_from()
            await socket.send_json_to({"type": "dom", "session_id": session_id, "dom": DOM})
            await socket.receive_nothing()
            await workflow.drain_background_tasks()
        await workflow.start_fill(session_id)
        self.assertEqual((await ApplySession.objects.aget(id=session_id)).state, "done")
        self.assertEqual((await ApplyHistory.objects.aget(client=client)).status, "failed")
        await socket.disconnect()
