import asyncio

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model

from accounts.models import Client
from accounts.tokens import read_token

from . import orchestrator as workflow

AUTH_TIMEOUT_SECONDS = 10
CLOSE_UNAUTHENTICATED = 4401


class TokenConsumer(AsyncJsonWebsocketConsumer):
    """A socket whose first message must be {"type": "auth", "token": ...}."""

    role = ""
    subject = None
    _auth_timer = None

    async def connect(self):
        await self.accept()
        self._auth_timer = asyncio.create_task(self._close_if_silent())

    async def _close_if_silent(self):
        await asyncio.sleep(AUTH_TIMEOUT_SECONDS)
        if self.subject is None:
            await self.close(CLOSE_UNAUTHENTICATED)

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        try:
            await super().receive(text_data, bytes_data, **kwargs)
        except ValueError:
            pass  # not JSON text: ignore rather than dropping the connection

    async def receive_json(self, content, **kwargs):
        if not isinstance(content, dict):
            return
        if self.subject is None:
            await self._authenticate(content)
            return
        try:
            await self.handle(content)
        except workflow.WorkflowError as exc:
            await self.send_json({"type": "error", "message": str(exc)})

    async def _authenticate(self, content):
        subject = read_token(content.get("token"), self.role) if content.get("type") == "auth" else None
        if subject is None or not await self.subject_exists(subject):
            await self.send_json({"type": "auth_failed"})
            await self.close(CLOSE_UNAUTHENTICATED)
            return
        self.subject = subject
        self._auth_timer.cancel()
        await self.send_json({"type": "auth_ok"})
        await self.authenticated()

    async def disconnect(self, code):
        if self._auth_timer:
            self._auth_timer.cancel()


class ClientConsumer(TokenConsumer):
    role = "client"

    @database_sync_to_async
    def subject_exists(self, subject):
        return Client.objects.filter(id=subject).exists()

    async def authenticated(self):
        await workflow.client_connected(self.subject, self.channel_name)

    async def handle(self, content):
        kind = content.get("type")
        if kind == "url":
            await workflow.client_reported_url(self.subject, content.get("url"))
        elif kind == "sync_result":
            await workflow.client_sync_result(self.subject, content)
        elif kind == "dom":
            await workflow.client_sent_dom(self.subject, content)
        elif kind == "fill_result":
            await workflow.client_fill_result(self.subject, content)

    async def server_command(self, event):
        await self.send_json(event["payload"])

    async def disconnect(self, code):
        await super().disconnect(code)
        if self.subject is not None:
            await workflow.client_disconnected(self.subject, self.channel_name)


class BossConsumer(TokenConsumer):
    role = "boss"

    @database_sync_to_async
    def subject_exists(self, subject):
        return get_user_model().objects.filter(id=subject, is_active=True, is_staff=True).exists()

    async def authenticated(self):
        await self.channel_layer.group_add(workflow.BOSS_GROUP, self.channel_name)
        await self.send_json(await workflow.snapshot())

    async def handle(self, content):
        kind = content.get("type")
        if kind == "sync":
            await workflow.start_sync(content.get("url"))
        elif kind == "fill":
            await workflow.start_fill(content.get("session_id"))
        elif kind == "refresh":
            await self.send_json(await workflow.snapshot())

    async def state_changed(self, _event):
        await self.send_json(await workflow.snapshot())

    async def disconnect(self, code):
        await super().disconnect(code)
        if self.subject is not None:
            await self.channel_layer.group_discard(workflow.BOSS_GROUP, self.channel_name)
