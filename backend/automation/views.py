from asgiref.sync import async_to_sync
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from accounts.http import boss_required, error, json_body
from accounts.models import Client

from .models import ApplyHistory
from .orchestrator import notify_boss

HISTORY_LIMIT = 500


def _history_row(row: ApplyHistory) -> dict:
    return {"id": row.id, "client_id": row.client_id, "url": row.apply_url, "time": row.time.isoformat(),
            "status": row.status, "results": row.results}


@csrf_exempt
@require_http_methods(["PATCH"])
@boss_required
def client_detail(request, client_id):
    enabled = json_body(request).get("enabled")
    if not isinstance(enabled, bool):
        return error("'enabled' must be true or false.")
    if not Client.objects.filter(id=client_id).update(enabled=enabled):
        return error("Client not found.", 404)
    async_to_sync(notify_boss)()
    return JsonResponse(Client.objects.get(id=client_id).to_state())


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
@boss_required
def history_list(request):
    rows = ApplyHistory.objects.all()
    client_id = request.GET.get("client", "")
    if client_id:
        if not client_id.isdecimal():
            return error("'client' must be a number.")
        rows = rows.filter(client_id=int(client_id))
    if request.method == "DELETE":
        if not client_id:
            return error("Choose a client whose history to delete.")
        rows.delete()
        return HttpResponse(status=204)
    return JsonResponse({"history": [_history_row(row) for row in rows[:HISTORY_LIMIT]]})


@csrf_exempt
@require_http_methods(["DELETE"])
@boss_required
def history_detail(_request, history_id):
    deleted, _ = ApplyHistory.objects.filter(id=history_id).delete()
    return HttpResponse(status=204) if deleted else error("History entry not found.", 404)


@require_GET
@boss_required
def statistics(_request):
    def count_of(status):
        return Count("history", filter=Q(history__status=status))

    clients = Client.objects.annotate(
        total=Count("history"),
        filled=count_of(ApplyHistory.Status.FILLED),
        partial=count_of(ApplyHistory.Status.PARTIAL),
        failed=count_of(ApplyHistory.Status.FAILED),
    )
    return JsonResponse({"clients": [
        {"client_id": c.id, "email": c.email, "total": c.total, "filled": c.filled, "partial": c.partial,
         "failed": c.failed}
        for c in clients
    ]})
