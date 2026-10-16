from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = "FixIt database admin"
admin.site.site_title = "FixIt admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Authentication views
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("accounts/", include("apps.accounts.urls")),
    path("portal/", include("apps.accounts.portal_urls")),
    path("payments/", include("apps.payments.urls")),
    path("", include("apps.tickets.urls")),
    # Core endpoints (healthz, home, dashboard, worker locator)
    path("", include("apps.core.urls")),
]

handler403 = "apps.core.views.custom_403_view"
handler404 = "apps.core.views.custom_404_view"
handler500 = "apps.core.views.custom_500_view"
