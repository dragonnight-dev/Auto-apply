import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

django_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter

from automation.routing import websocket_urlpatterns

# Sockets authenticate with a token in their first message, and extensions connect
# from chrome-extension:// origins, so no Origin allow-list applies here.
application = ProtocolTypeRouter({"http": django_app, "websocket": URLRouter(websocket_urlpatterns)})
