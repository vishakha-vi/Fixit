from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("", views.payment_list, name="list"),
    path("new/", views.payment_create, name="create"),
    path("<int:pk>/edit/", views.payment_edit, name="edit"),
    path("<int:pk>/paid/", views.payment_mark_paid, name="mark_paid"),
    path("<int:pk>/cancel/", views.payment_cancel, name="cancel"),
    path("worker/<int:worker_id>/pay-all/", views.payment_pay_all, name="pay_all"),
]
