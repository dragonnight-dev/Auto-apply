from django.urls import path

from .consumers import ClientConsumer

websocket_urlpatterns = [
    path("ws/client/", ClientConsumer.as_asgi()),
]
