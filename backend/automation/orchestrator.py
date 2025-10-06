"""The apply workflow: sync a URL, collect the page, build plans, send them, record results.

Runs on the event loop. Database work goes through database_sync_to_async; SLM work runs
on separate threads so a slow model never blocks the database thread or other sockets.
"""
import asyncio
import base64
import logging
from pathlib import Path

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.db import transaction

from accounts.models import Client
from slm.client import SLMClient

from .dom import DomError, is_http_url, normalize_dom
from .models import ApplyHistory, ApplySession, FillPlan
from .planner import build_plan
from .tailor import tailor_resume

logger = logging.getLogger(__name__)
BOSS_GROUP = "boss"
State = ApplySession.State
_background_tasks = set()


class WorkflowError(Exception):
    """A request the boss can correct; the message is shown in the UI."""


async def notify_boss():
    await get_channel_layer().group_send(BOSS_GROUP, {"type": "state.changed"})


async def _send(channel_name: str, payload: dict):
    await get_channel_layer().send(channel_name, {"type": "server.command", "payload": payload})


async def drain_background_tasks():
    while _background_tasks:
        await asyncio.gather(*list(_background_tasks), return_exceptions=True)


def _spawn(coroutine):
    task = asyncio.create_task(coroutine)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


# ---- state snapshot ----------------------------------------------------------------------

def _session_state(session):
    if session is None:
        return None
    return {
        "id": session.id,
        "url": session.url,
        "state": session.state,
        "error": session.error,
        "title": session.dom.get("title", ""),
        "plans": [
            {"id": plan.id, "client_id": plan.client_id, "status": plan.status, "actions": len(plan.actions),
             "skipped": plan.skipped}
            for plan in session.plans.order_by("id")
        ],
    }


@database_sync_to_async
def snapshot() -> dict:
    return {
        "type": "state",
        "clients": [client.to_state() for client in Client.objects.all()],
        "session": _session_state(ApplySession.objects.order_by("-id").first()),
    }


# ---- connection tracking -----------------------------------------------------------------

@database_sync_to_async
def _attach(client_id: int, channel_name: str):
    Client.objects.filter(id=client_id).update(channel_name=channel_name, action=Client.Action.IDLE)


async def client_connected(client_id: int, channel_name: str):
    await _attach(client_id, channel_name)
    await _send(channel_name, {"type": "get_url"})
    await notify_boss()


def _record_failure(plan: FillPlan, reason: str):
    plan.status = FillPlan.Status.FAILED
    plan.save(update_fields=["status"])
    ApplyHistory.objects.create(client_id=plan.client_id, apply_url=plan.session.url,
                                status=ApplyHistory.Status.FAILED, results={"error": reason})


def _finish_session_if_complete(session_id: int):
    if not FillPlan.objects.filter(session_id=session_id, status=FillPlan.Status.SENT).exists():
        ApplySession.objects.filter(id=session_id, state=State.FILLING).update(state=State.DONE)


@database_sync_to_async
def _detach(client_id: int, channel_name: str) -> bool:
    with transaction.atomic():
        # A reconnect may already have replaced this socket; then the client is still online.
        updated = Client.objects.filter(id=client_id, channel_name=channel_name).update(
            channel_name="", action=Client.Action.IDLE)
        if not updated:
            return False
        ApplySession.objects.filter(source_client_id=client_id, state=State.SYNCING).update(
            state=State.FAILED, error="The client providing the page disconnected.")
        plans = FillPlan.objects.select_related("session").filter(client_id=client_id, status=FillPlan.Status.SENT)
        for plan in plans:
            _record_failure(plan, "Client disconnected before reporting results.")
            _finish_session_if_complete(plan.session_id)
    return True


async def client_disconnected(client_id: int, channel_name: str):
    if await _detach(client_id, channel_name):
        await notify_boss()


@database_sync_to_async
def _set_url(client_id: int, url: str):
    Client.objects.filter(id=client_id).update(current_url=url)


async def client_reported_url(client_id: int, url):
    if is_http_url(url):
        await _set_url(client_id, url)
        await notify_boss()


# ---- 1. sync url -------------------------------------------------------------------------

@database_sync_to_async
def _begin_sync(url: str):
    with transaction.atomic():
        if ApplySession.objects.filter(state=State.FILLING).exists():
            raise WorkflowError("Clients are still filling a form. Wait for them to finish.")
        clients = list(Client.objects.filter(enabled=True).exclude(channel_name=""))
        if not clients:
            raise WorkflowError("No enabled client is connected.")
        ApplySession.objects.filter(state__in=[State.SYNCING, State.PLANNING, State.READY]).update(
            state=State.FAILED, error="Replaced by a newer sync.")
        session = ApplySession.objects.create(url=url, source_client=clients[0])
        Client.objects.filter(id__in=[c.id for c in clients]).update(action=Client.Action.SYNCING)
    return session.id, clients


async def start_sync(url):
    if not is_http_url(url):
        raise WorkflowError("Enter a valid http or https URL.")
    session_id, clients = await _begin_sync(url)
    for index, client in enumerate(clients):
        # Only one client returns the page; its form is the same for everyone.
        await _send(client.channel_name, {"type": "sync_url", "session_id": session_id, "url": url,
                                          "send_dom": index == 0})
    await notify_boss()
    return session_id


@database_sync_to_async
def _finish_sync(client_id: int, session_id, ok: bool, error: str):
    Client.objects.filter(id=client_id).update(action=Client.Action.IDLE)
    if not ok:
        ApplySession.objects.filter(id=session_id, source_client_id=client_id, state=State.SYNCING).update(
            state=State.FAILED, error=error[:500] or "The page could not be opened.")


async def client_sync_result(client_id: int, content: dict):
    error = content.get("error") if isinstance(content.get("error"), str) else ""
    await _finish_sync(client_id, content.get("session_id"), content.get("ok") is True, error)
    await notify_boss()


# ---- 2. page data -> plans ---------------------------------------------------------------

@database_sync_to_async
def _store_dom(client_id: int, session_id, dom: dict):
    """Accept the page only from the assigned client, once. Returns the targets to plan for."""
    updated = ApplySession.objects.filter(id=session_id, source_client_id=client_id, state=State.SYNCING).update(
        state=State.PLANNING, dom=dom)
    if not updated:
        return None
    return list(Client.objects.filter(enabled=True).exclude(channel_name=""))


def generate_plan(dom: dict, client: Client, session_id: int) -> dict:
    """Blocking: talks to the SLM. Takes no database connection."""
    slm = SLMClient()
    plan = build_plan(dom, client.profile, slm)
    plan["resume_file"] = ""
    if any(action["op"] == "upload" for action in plan["actions"]):
        tailored = tailor_resume(client.email, client.resume_text, dom["text"], session_id, slm)
        plan["resume_file"] = str(tailored) if tailored else client.resume_path
    return plan


@database_sync_to_async
def _save_plan(session_id: int, client_id: int, plan: dict):
    FillPlan.objects.create(session_id=session_id, client_id=client_id, actions=plan["actions"],
                            skipped=plan["skipped"], resume_file=plan["resume_file"])


@database_sync_to_async
def _save_failed_plan(session_id: int, client_id: int, reason: str):
    FillPlan.objects.create(session_id=session_id, client_id=client_id, status=FillPlan.Status.FAILED,
                            skipped=[{"selector": "", "label": "plan", "reason": reason}])


@database_sync_to_async
def _plans_ready(session_id: int):
    ApplySession.objects.filter(id=session_id, state=State.PLANNING).update(state=State.READY)


async def _generate_plans(session_id: int, dom: dict, clients: list):
    generate = sync_to_async(generate_plan, thread_sensitive=False)
    for client in clients:
        try:
            plan = await generate(dom, client, session_id)
            await _save_plan(session_id, client.id, plan)
        except Exception:
            logger.exception("Plan failed for client %s", client.id)
            await _save_failed_plan(session_id, client.id, "plan_error")
        await notify_boss()
    await _plans_ready(session_id)
    await notify_boss()


async def client_sent_dom(client_id: int, content: dict):
    try:
        dom = normalize_dom(content.get("dom"))
    except DomError:
        await _finish_sync(client_id, content.get("session_id"), False, "The page data was invalid.")
        await notify_boss()
        return
    clients = await _store_dom(client_id, content.get("session_id"), dom)
    if clients is None:
        return
    _spawn(_generate_plans(content["session_id"], dom, clients))
    await notify_boss()


# ---- 3. fill -----------------------------------------------------------------------------

def _resume_payload(plan: FillPlan):
    if not any(action["op"] == "upload" for action in plan.actions):
        return None
    data = Path(plan.resume_file).read_bytes()
    name = (plan.client.profile.get("full_name") or "Resume").replace(" ", "_")
    safe_name = "".join(ch for ch in name if ch.isalnum() or ch in "_-") or "Resume"
    return {"filename": f"{safe_name}.pdf", "base64": base64.b64encode(data).decode("ascii")}


@database_sync_to_async
def _begin_fill(session_id):
    with transaction.atomic():
        # The conditional update makes a double click send each plan only once.
        if not ApplySession.objects.filter(id=session_id, state=State.READY).update(state=State.FILLING):
            raise WorkflowError("This page has no fill data ready.")
        outgoing = []
        plans = FillPlan.objects.select_related("client", "session").filter(
            session_id=session_id, status=FillPlan.Status.READY)
        for plan in plans:
            if not (plan.client.connected and plan.client.enabled):
                _record_failure(plan, "Client was offline or disabled.")
                continue
            try:
                resume = _resume_payload(plan)
            except OSError as exc:
                logger.error("Resume unreadable for client %s: %s", plan.client_id, exc)
                _record_failure(plan, "Resume file could not be read.")
                continue
            plan.status = FillPlan.Status.SENT
            plan.save(update_fields=["status"])
            Client.objects.filter(id=plan.client_id).update(action=Client.Action.FILLING)
            outgoing.append((plan.client.channel_name, {"type": "fill", "plan_id": plan.id, "actions": plan.actions,
                                                        "resume": resume}))
        _finish_session_if_complete(session_id)
    return outgoing


async def start_fill(session_id):
    for channel_name, payload in await _begin_fill(session_id):
        await _send(channel_name, payload)
    await notify_boss()


def _result_status(results: list) -> str:
    succeeded = sum(1 for result in results if isinstance(result, dict) and result.get("ok") is True)
    if results and succeeded == len(results):
        return ApplyHistory.Status.FILLED
    return ApplyHistory.Status.PARTIAL if succeeded else ApplyHistory.Status.FAILED


@database_sync_to_async
def _store_results(client_id: int, plan_id, results: list):
    with transaction.atomic():
        plan = FillPlan.objects.select_related("session").filter(
            id=plan_id, client_id=client_id, status=FillPlan.Status.SENT).first()
        if plan is None:
            return False  # unknown, someone else's, or already reported
        plan.status = FillPlan.Status.DONE
        plan.save(update_fields=["status"])
        ApplyHistory.objects.create(client_id=client_id, apply_url=plan.session.url,
                                    status=_result_status(results),
                                    results={"actions": results, "skipped": plan.skipped})
        Client.objects.filter(id=client_id).update(action=Client.Action.IDLE)
        _finish_session_if_complete(plan.session_id)
    return True


async def client_fill_result(client_id: int, content: dict):
    results = content.get("results") if isinstance(content.get("results"), list) else []
    if await _store_results(client_id, content.get("plan_id"), results[:300]):
        await notify_boss()
