from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("complaints/", views.ticket_list, name="list"),
    path("complaints/new/", views.ticket_create, name="create"),
    path("complaints/<int:pk>/", views.ticket_detail, name="detail"),
    path("complaints/<int:pk>/action/", views.ticket_action, name="action"),
    path("complaints/<int:pk>/reassign/", views.ticket_reassign, name="reassign"),
    path("complaints/<int:pk>/comment/", views.ticket_comment, name="comment"),
    path("complaints/<int:pk>/remind/", views.ticket_remind, name="remind"),
    path("track/", views.track, name="track"),
    path("reminders/", views.reminder_list, name="reminders"),
    path("reminders/done-all/", views.reminder_all_done, name="reminders_all_done"),
    path("reminders/<int:pk>/done/", views.reminder_done, name="reminder_done"),
    path("reminders/<int:pk>/delete/", views.reminder_delete, name="reminder_delete"),
]
