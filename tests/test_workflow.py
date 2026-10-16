from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client

from apps.core import clock
from apps.payments.models import WorkerPayment
from apps.tickets import services, workflow
from apps.tickets.models import Reminder, Ticket, TicketEvent
from tests.factories import PASSWORD, campus, make_location, make_ticket

S = Ticket.Status


@pytest.fixture
def people(db):
    return campus()


def client_for(user):
    c = Client()
    assert c.login(username=user.username, password=PASSWORD)
    return c


def test_status_choices_match_state_machine_yaml():
    assert set(Ticket.Status.values) == set(workflow.load_spec()["states"].keys())


def test_every_yaml_guard_is_implemented():
    for t in workflow.load_spec()["transitions"]:
        for guard in t.get("guards") or []:
            assert guard in workflow.GUARDS, f"Guard not implemented: {guard}"


def test_full_lifecycle_requester_confirms_and_worker_gets_paid(people):
    student, admin, worker = people["student"], people["admin"], people["worker"]
    ticket = make_ticket(student)
    assert ticket.status == S.SUBMITTED
    assert (ticket.priority_score, ticket.priority_band) == (25, "P4")  # moderate only
    ticket = workflow.perform_transition(ticket, admin, S.TRIAGED)
    ticket = workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    assert ticket.assigned_to == worker
    assert Reminder.objects.filter(recipient=worker, kind=Reminder.Kind.NEW_JOB).exists()

    ticket = workflow.perform_transition(ticket, worker, S.IN_PROGRESS)
    worker.refresh_from_db()
    assert worker.current_location == ticket.location  # worker is located at the job

    ticket = workflow.perform_transition(
        ticket, worker, S.REPORTED_FIXED,
        {"checklist": True, "work_notes": "Replaced capacitor", "material_cost": "120"},
    )
    assert ticket.sla_stopped_at is not None
    ticket = workflow.perform_transition(ticket, student, S.VERIFIED_FIXED)
    assert ticket.verified_method == Ticket.VerifiedMethod.REQUESTER_CONFIRM

    payment = WorkerPayment.objects.get(ticket=ticket)
    assert payment.worker == worker
    assert payment.amount == Decimal("420.00")  # 300 rate + 120 materials
    assert payment.status == WorkerPayment.Status.PENDING
    kinds = list(ticket.events.values_list("to_status", flat=True))
    assert kinds == ["SUBMITTED", "TRIAGED", "ASSIGNED", "IN_PROGRESS", "REPORTED_FIXED",
                     "VERIFIED_FIXED"]


def test_worker_can_verify_on_site_with_completion_code_only(people):
    student, admin, worker = people["student"], people["admin"], people["worker"]
    ticket = make_ticket(student)
    ticket = workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    ticket = workflow.perform_transition(ticket, worker, S.IN_PROGRESS)
    ticket = workflow.perform_transition(ticket, worker, S.REPORTED_FIXED, {"checklist": True})

    with pytest.raises(workflow.TransitionError, match="code is not correct"):
        workflow.perform_transition(ticket, worker, S.VERIFIED_FIXED, {"code": "000000x"})
    ticket = workflow.perform_transition(
        ticket, worker, S.VERIFIED_FIXED, {"code": ticket.completion_code}
    )
    assert ticket.verified_method == Ticket.VerifiedMethod.ON_SITE_CODE


def test_admin_cannot_mark_verified_fixed(people):
    student, admin, worker = people["student"], people["admin"], people["worker"]
    ticket = make_ticket(student)
    ticket = workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    ticket = workflow.perform_transition(ticket, worker, S.IN_PROGRESS)
    ticket = workflow.perform_transition(ticket, worker, S.REPORTED_FIXED, {"checklist": True})
    with pytest.raises(workflow.TransitionError):
        workflow.perform_transition(ticket, admin, S.VERIFIED_FIXED)


def test_report_fixed_requires_checklist(people):
    student, admin, worker = people["student"], people["admin"], people["worker"]
    ticket = make_ticket(student)
    ticket = workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    ticket = workflow.perform_transition(ticket, worker, S.IN_PROGRESS)
    with pytest.raises(workflow.TransitionError, match="checklist"):
        workflow.perform_transition(ticket, worker, S.REPORTED_FIXED, {})


def test_unassigned_worker_is_denied(people):
    student, admin, worker, other = (people["student"], people["admin"], people["worker"],
                                     people["other_worker"])
    ticket = make_ticket(student)
    ticket = workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    with pytest.raises(workflow.TransitionError, match="assigned worker"):
        workflow.perform_transition(ticket, other, S.IN_PROGRESS)


def test_student_cannot_assign_or_cancel_others_complaint(people):
    ticket = make_ticket(people["student"])
    with pytest.raises(workflow.TransitionError):
        workflow.perform_transition(ticket, people["student"], S.ASSIGNED,
                                    {"assignee": people["worker"]})
    with pytest.raises(workflow.TransitionError, match="raised this complaint"):
        workflow.perform_transition(ticket, people["other_student"], S.CANCELLED)
    ticket = workflow.perform_transition(ticket, people["student"], S.CANCELLED)
    assert ticket.status == S.CANCELLED


def test_stale_form_is_rejected(people):
    ticket = make_ticket(people["student"])
    workflow.perform_transition(ticket, people["admin"], S.TRIAGED)
    with pytest.raises(workflow.TransitionError, match="updated by someone else"):
        workflow.perform_transition(ticket, people["admin"], S.TRIAGED, expected_status=S.SUBMITTED)


def test_waiting_for_access_pauses_sla_and_counts_attempts(people, settings):
    settings.DEMO_MODE = True
    clock.reset()
    student, admin, worker = people["student"], people["admin"], people["worker"]
    ticket = make_ticket(student)
    ticket = workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    ticket = workflow.perform_transition(ticket, worker, S.IN_PROGRESS)
    due_before = ticket.effective_due_at()
    ticket = workflow.perform_transition(ticket, worker, S.WAITING_ACCESS, {"reason": "Room locked"})
    assert ticket.access_attempts == 1 and ticket.is_paused
    clock.advance(timedelta(hours=5))
    ticket = workflow.perform_transition(ticket, worker, S.IN_PROGRESS)
    assert ticket.paused_seconds >= 5 * 3600 - 5
    assert ticket.effective_due_at() >= due_before + timedelta(hours=5) - timedelta(seconds=5)
    clock.reset()


def test_reopen_after_not_fixed(people):
    student, admin, worker = people["student"], people["admin"], people["worker"]
    ticket = make_ticket(student)
    ticket = workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    ticket = workflow.perform_transition(ticket, worker, S.IN_PROGRESS)
    ticket = workflow.perform_transition(ticket, worker, S.REPORTED_FIXED, {"checklist": True})
    with pytest.raises(workflow.TransitionError, match="reason"):
        workflow.perform_transition(ticket, student, S.REOPENED, {})
    ticket = workflow.perform_transition(ticket, student, S.REOPENED, {"reason": "Still broken"})
    assert ticket.reopen_count == 1
    assert ticket.sla_stopped_at is None
    ticket = workflow.perform_transition(ticket, worker, S.IN_PROGRESS)
    assert ticket.status == S.IN_PROGRESS


def test_unverified_fix_auto_closes_after_72_hours(people, settings):
    settings.DEMO_MODE = True
    clock.reset()
    student, admin, worker = people["student"], people["admin"], people["worker"]
    ticket = make_ticket(student)
    ticket = workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    ticket = workflow.perform_transition(ticket, worker, S.IN_PROGRESS)
    ticket = workflow.perform_transition(ticket, worker, S.REPORTED_FIXED, {"checklist": True})

    clock.advance(timedelta(hours=30))
    services.run_due_tasks(force=True)
    assert Reminder.objects.filter(recipient=student, kind=Reminder.Kind.CONFIRM_FIX).exists()
    ticket.refresh_from_db()
    assert ticket.status == S.REPORTED_FIXED

    clock.advance(timedelta(hours=43))
    services.run_due_tasks(force=True)
    ticket.refresh_from_db()
    assert ticket.status == S.CLOSED_UNVERIFIED
    assert not WorkerPayment.objects.filter(ticket=ticket).exists()  # only verified fixes pay
    clock.reset()


def test_overdue_job_reminds_worker_and_admins_once(people, settings):
    settings.DEMO_MODE = True
    clock.reset()
    student, admin, worker = people["student"], people["admin"], people["worker"]
    ticket = make_ticket(student, severity="critical")  # score 50 -> P3, 72h SLA
    ticket = workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    clock.advance(timedelta(hours=ticket.sla_hours + 1))
    services.run_due_tasks(force=True)
    services.run_due_tasks(force=True)
    assert Reminder.objects.filter(recipient=worker, kind=Reminder.Kind.SLA_OVERDUE).count() == 1
    assert Reminder.objects.filter(recipient=admin, kind=Reminder.Kind.SLA_OVERDUE).count() == 1
    ticket.refresh_from_db()
    assert ticket.priority_score > 50  # aging raised the priority
    clock.reset()


def test_priority_uses_safety_and_critical_location(people):
    loc = make_location("Health Centre", "Medical Room 1")
    ticket = make_ticket(people["student"], location=loc, severity="major", safety_flag=True)
    # major 40 + safety 30 + critical location 10 = 80 -> P1, 4h SLA
    assert ticket.priority_score == 80
    assert ticket.priority_band == "P1"
    assert ticket.sla_hours == 4


def test_double_submit_returns_existing_ticket(people):
    loc = make_location()
    first = make_ticket(people["student"], location=loc)
    second, created = services.create_ticket(
        created_by=people["student"], title="Ceiling fan not working",
        description="dup", category="electrical", severity="moderate", location=loc,
    )
    assert created is False and second.pk == first.pk


def test_recurrence_is_detected(people):
    loc = make_location()
    make_ticket(people["student"], location=loc)
    again = make_ticket(people["other_student"], location=loc, title="Fan broken again")
    assert again.is_recurrence is True


def test_reassignment_preserves_history(people):
    student, admin, worker, other = (people["student"], people["admin"], people["worker"],
                                     people["other_worker"])
    ticket = make_ticket(student)
    ticket = workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    ticket = workflow.reassign(ticket, admin, other, "Worker on leave")
    assert ticket.assigned_to == other
    assert ticket.events.filter(kind=TicketEvent.Kind.REASSIGNED).exists()
    assert ticket.events.filter(kind=TicketEvent.Kind.ASSIGNED).exists()


def test_http_flow_through_the_browser_views(people):
    student, admin, worker = people["student"], people["admin"], people["worker"]
    loc = make_location()
    sc = client_for(student)
    resp = sc.post("/complaints/new/", {
        "title": "Tap leaking badly", "category": "plumbing", "location": loc.pk,
        "location_detail": "", "severity": "moderate", "affected_people": 2,
        "description": "Water keeps dripping from the tap all night.",
    })
    ticket = Ticket.objects.get(title="Tap leaking badly")
    assert resp.status_code == 302 and resp["Location"] == f"/complaints/{ticket.pk}/"
    page = sc.get(f"/complaints/{ticket.pk}/").content.decode()
    assert ticket.completion_code in page  # requester sees their code

    ac = client_for(admin)
    ac.post(f"/complaints/{ticket.pk}/action/", {"to": "ASSIGNED", "assignee": worker.pk,
                                                 "from_status": "SUBMITTED"})
    ticket.refresh_from_db()
    assert ticket.status == S.ASSIGNED

    wc = client_for(worker)
    worker_page = wc.get(f"/complaints/{ticket.pk}/").content.decode()
    assert ticket.completion_code not in worker_page  # worker must ask the requester
    wc.post(f"/complaints/{ticket.pk}/action/", {"to": "IN_PROGRESS"})
    wc.post(f"/complaints/{ticket.pk}/action/", {
        "to": "REPORTED_FIXED", "checklist": "on", "work_notes": "New washer",
        "material_cost": "40", "code": ticket.completion_code,
    })
    ticket.refresh_from_db()
    assert ticket.status == S.VERIFIED_FIXED
    assert WorkerPayment.objects.filter(ticket=ticket, amount=Decimal("340.00")).exists()

    # tracking by number
    resp = sc.get("/track/", {"code": ticket.code})
    assert resp.status_code == 302 and resp["Location"] == ticket.get_absolute_url()


def test_idor_other_students_complaint_is_404(people):
    ticket = make_ticket(people["student"])
    other = client_for(people["other_student"])
    assert other.get(f"/complaints/{ticket.pk}/").status_code == 404
    assert other.post(f"/complaints/{ticket.pk}/action/", {"to": "CANCELLED"}).status_code == 404
    resp = other.get("/track/", {"code": ticket.code})
    assert resp.status_code == 200 and "No complaint" in resp.content.decode()
    # unassigned worker cannot see it either
    assert client_for(people["other_worker"]).get(f"/complaints/{ticket.pk}/").status_code == 404
    # staff can view all (read-only)
    assert client_for(people["staff"]).get(f"/complaints/{ticket.pk}/").status_code == 200


def test_manual_reminder_goes_to_assigned_worker(people):
    student, admin, worker = people["student"], people["admin"], people["worker"]
    ticket = make_ticket(student)
    workflow.perform_transition(ticket, admin, S.ASSIGNED, {"assignee": worker})
    sc = client_for(student)
    resp = sc.post(f"/complaints/{ticket.pk}/remind/", {"target": "worker", "message": "Please come today"})
    assert resp.status_code == 302
    reminder = Reminder.objects.get(recipient=worker, kind=Reminder.Kind.MANUAL)
    assert reminder.message == "Please come today"
    # cooldown stops spamming
    sc.post(f"/complaints/{ticket.pk}/remind/", {"target": "worker", "message": "again"})
    assert Reminder.objects.filter(recipient=worker, kind=Reminder.Kind.MANUAL).count() == 1
    # worker sees it in their reminders inbox
    page = client_for(worker).get("/reminders/").content.decode()
    assert "Please come today" in page


def test_invalid_submission_shows_errors_and_creates_nothing(people):
    sc = client_for(people["student"])
    resp = sc.post("/complaints/new/", {"title": "Hi", "category": "", "description": "short"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "at least 5 characters" in body and "This field is required" in body
    assert not Ticket.objects.exists()


def test_hostile_text_is_escaped(people):
    loc = make_location()
    ticket = make_ticket(people["student"], location=loc, title="<script>alert(1)</script> fan",
                         description="<img src=x onerror=alert(1)> ಕನ್ನಡ हिंदी 🙂")
    page = client_for(people["student"]).get(f"/complaints/{ticket.pk}/").content.decode()
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert "ಕನ್ನಡ हिंदी 🙂" in page


def test_safety_flag_alerts_admins_immediately(people):
    ticket = make_ticket(people["student"], safety_flag=True, severity="major")
    assert Reminder.objects.filter(recipient=people["admin"], kind=Reminder.Kind.SAFETY,
                                   ticket=ticket).exists()
    resp = client_for(people["student"]).post("/complaints/new/", {
        "title": "Sparks from socket", "category": "electrical", "location": ticket.location.pk,
        "severity": "critical", "affected_people": 0, "safety_flag": "on",
        "description": "Sparks come out when plugging in a charger.",
    }, follow=True)
    assert "Safety issue flagged" in resp.content.decode()
