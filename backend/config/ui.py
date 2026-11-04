"""Serve the built React console from the same port as the API and sockets."""
import mimetypes

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.static import serve

# The Windows registry can map .js to text/plain, and browsers refuse such module scripts.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def console(request, path=""):
    root = settings.FRONTEND_DIST
    if not (root / "index.html").exists():
        return HttpResponse("The console is not built. Run: npm run build (in frontend/)", status=503,
                            content_type="text/plain")
    try:
        return serve(request, path or "index.html", document_root=root)
    except Http404:
        return serve(request, "index.html", document_root=root)
