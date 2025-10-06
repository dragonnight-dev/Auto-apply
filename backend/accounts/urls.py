from django.urls import path

from . import views

urlpatterns = [
    path("clients/signup", views.client_signup),
    path("clients/signin", views.client_signin),
    path("boss/signup", views.boss_signup),
    path("boss/signin", views.boss_signin),
]
