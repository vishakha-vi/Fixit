from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Authentication views
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    # Core endpoints (healthz, home)
    path("", include("apps.core.urls")),
]

handler404 = "apps.core.views.custom_404_view"
handler500 = "apps.core.views.custom_500_view"
