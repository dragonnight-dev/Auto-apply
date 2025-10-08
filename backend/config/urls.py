from django.http import JsonResponse
from django.urls import include, path, re_path

from .ui import console


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/health", health),
    path("api/", include("accounts.urls")),
    path("api/", include("automation.urls")),
    re_path(r"^(?!api/)(?P<path>.*)$", console),
]
