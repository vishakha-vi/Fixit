from django.urls import path

from apps.accounts.views import worker_locator

from . import views

urlpatterns = [
    path("healthz", views.healthz_view, name="healthz"),
    path("healthz/", views.healthz_view, name="healthz_slash"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("workers/", worker_locator, name="worker_locator"),
    path("showcase/", views.showcase_view, name="showcase"),
    path("", views.home_view, name="home"),
]
