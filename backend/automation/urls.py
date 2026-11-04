from django.urls import path

from . import views

urlpatterns = [
    path("clients/<int:client_id>", views.client_detail),
    path("history", views.history_list),
    path("history/<int:history_id>", views.history_detail),
    path("stats", views.statistics),
]
