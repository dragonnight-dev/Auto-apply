"""Small helpers for the JSON API."""
import json
from functools import wraps

from django.contrib.auth import get_user_model
from django.http import JsonResponse

from .tokens import read_token


def error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def json_body(request) -> dict:
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def bearer_token(request):
    header = request.headers.get("Authorization", "")
    return header[7:] if header.startswith("Bearer ") else None


def boss_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        boss_id = read_token(bearer_token(request), "boss")
        if boss_id is None or not get_user_model().objects.filter(id=boss_id, is_active=True).exists():
            return error("Authentication required.", 401)
        return view(request, *args, **kwargs)

    return wrapper
