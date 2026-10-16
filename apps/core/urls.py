from django.urls import path

from . import views

urlpatterns = [
    path("healthz", views.healthz_view, name="healthz"),
    path("healthz/", views.healthz_view, name="healthz_slash"),
    path("", views.home_view, name="home"),
]
