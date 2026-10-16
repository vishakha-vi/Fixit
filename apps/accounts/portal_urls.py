from django.urls import path

from . import portal_views as views

app_name = "portal"

urlpatterns = [
    path("", views.portal_home, name="home"),
    path("users/", views.user_list, name="users"),
    path("users/new/", views.user_create, name="user_create"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("users/<int:pk>/password/", views.user_password, name="user_password"),
    path("users/<int:pk>/toggle-active/", views.user_toggle_active, name="user_toggle_active"),
    path("users/<int:pk>/reset-features/", views.user_reset_features, name="user_reset_features"),
    path("role-defaults.json", views.role_defaults_json, name="role_defaults"),
    path("areas/", views.areas, name="areas"),
    path("areas/<str:kind>/<int:pk>/delete/", views.area_delete, name="area_delete"),
    path("demo-clock/", views.demo_clock, name="demo_clock"),
]
