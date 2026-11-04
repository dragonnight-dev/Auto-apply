from django.urls import path

from .consumers import BossConsumer, ClientConsumer

websocket_urlpatterns = [
    path("ws/client/", ClientConsumer.as_asgi()),
    path("ws/boss/", BossConsumer.as_asgi()),
]
