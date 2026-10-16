from decimal import Decimal

import pytest
from django.test import Client

from apps.accounts import features as F
from apps.accounts.models import User
from apps.payments.models import WorkerPayment
from apps.tickets import workflow
from apps.tickets.models import Ticket
from tests.factories import PASSWORD, campus, make_location, make_ticket


@pytest.fixture
def people(db):
    return campus()


def client_for(user):
    c = Client()
    assert c.login(username=user.username, password=PASSWORD)
    return c


# ---- feature access -------------------------------------------------------

def test_role_defaults():
    assert set(F.default_features_for_role("student")) == {
        F.SUBMIT_COMPLAINT, F.TRACK_COMPLAINT, F.REMINDERS
    }
    assert F.WORK_ON_COMPLAINTS in F.default_features_for_role("worker")
    assert F.DASHBOARD in F.default_features_for_role("staff")


def test_admin_always_has_every_feature(people):
    admin = people["admin"]
    admin.features = []
    assert all(admin.has_feature(code) for code in F.ALL_FEATURE_CODES)


@pytest.mark.parametrize("path", ["/dashboard/", "/payments/", "/workers/", "/portal/"])
def test_student_is_denied_admin_features(people, path):
    resp = client_for(people["student"]).get(path)
    assert resp.status_code == 403
    assert "access" in resp.content.decode().lower()


def test_admin_granted_feature_takes_effect(people):
    student = people["student"]
    assert client_for(student).get("/dashboard/").status_code == 403
    student.features = [*student.features, F.DASHBOARD]
    student.save()
    assert client_for(student).get("/dashboard/").status_code == 200


def test_staff_with_manage_feature_can_assign(people):
    staff, worker = people["staff"], people["worker"]
    ticket = make_ticket(people["student"])
    with pytest.raises(workflow.TransitionError):
        workflow.perform_transition(ticket, staff, Ticket.Status.ASSIGNED, {"assignee": worker})
    staff.features = [*staff.features, F.MANAGE_COMPLAINTS]
    staff.save()
    ticket = workflow.perform_transition(ticket, staff, Ticket.Status.ASSIGNED, {"assignee": worker})
    assert ticket.assigned_to == worker


def test_anonymous_is_redirected_to_login():
    resp = Client().get("/complaints/")
    assert resp.status_code == 302 and "/accounts/login/" in resp["Location"]


# ---- signup ----------------------------------------------------------------

def test_student_can_sign_up_and_raise_complaint(db):
    c = Client()
    resp = c.post("/accounts/signup/", {
        "first_name": "Neha", "last_name": "Gupta", "email": "Neha@Campus.edu",
        "phone": "9999999999", "department": "Hostel B 101",
        "password1": "Very-Strong-Pass-42", "password2": "Very-Strong-Pass-42",
    })
    assert resp.status_code == 302
    user = User.objects.get(email="neha@campus.edu")
    assert user.role == User.Role.STUDENT and user.username == "neha@campus.edu"
    assert user.has_feature(F.SUBMIT_COMPLAINT) and not user.has_feature(F.DASHBOARD)
    assert c.get("/complaints/new/").status_code == 200
    # duplicate email refused
    resp = Client().post("/accounts/signup/", {
        "first_name": "X", "email": "neha@campus.edu",
        "password1": "Very-Strong-Pass-42", "password2": "Very-Strong-Pass-42",
    })
    assert resp.status_code == 200 and "already exists" in resp.content.decode()


def test_signup_can_be_disabled(db, settings):
    settings.ALLOW_STUDENT_SIGNUP = False
    assert Client().get("/accounts/signup/").status_code == 404


# ---- admin portal: users -----------------------------------------------------

def test_admin_creates_staff_account_with_custom_features(people):
    ac = client_for(people["admin"])
    resp = ac.post("/portal/users/new/", {
        "first_name": "Kavita", "last_name": "Rao", "email": "kavita@campus.edu",
        "role": "staff", "phone": "", "department": "Library", "is_active": "on",
        "specialty": "general", "rate_per_job": "250", "availability": "on_duty",
        "features": [F.SUBMIT_COMPLAINT, F.DASHBOARD, F.WORKER_PAYMENTS],
        "password": "",
    })
    assert resp.status_code == 302
    user = User.objects.get(email="kavita@campus.edu")
    assert user.role == User.Role.STAFF
    assert set(user.features) == {F.SUBMIT_COMPLAINT, F.DASHBOARD, F.WORKER_PAYMENTS}
    # a temporary password was generated and shown once
    follow = ac.get(resp["Location"])
    messages = [str(m) for m in follow.context["messages"]]
    assert any("Temporary password" in m for m in messages)
    temp = next(m for m in messages if "Temporary password" in m).split("Temporary password: ")[1].split(" ")[0]
    assert Client().login(username="kavita@campus.edu", password=temp)


def test_admin_edits_features_and_deletes_user(people):
    ac = client_for(people["admin"])
    student = people["student"]
    ticket = make_ticket(student)
    resp = ac.post(f"/portal/users/{student.pk}/edit/", {
        "first_name": student.first_name, "last_name": "", "email": student.email,
        "role": "student", "phone": "", "department": "", "is_active": "on",
        "specialty": "general", "rate_per_job": "250", "availability": "on_duty",
        "features": [F.SUBMIT_COMPLAINT],
    })
    assert resp.status_code == 302
    student.refresh_from_db()
    assert student.features == [F.SUBMIT_COMPLAINT]

    page = ac.get(f"/portal/users/{student.pk}/").content.decode()
    assert ticket.code in page  # all records of the user are visible

    assert ac.get(f"/portal/users/{student.pk}/delete/").status_code == 200
    assert ac.post(f"/portal/users/{student.pk}/delete/").status_code == 302
    assert not User.objects.filter(pk=student.pk).exists()
    ticket.refresh_from_db()
    assert ticket.created_by is None  # complaint record is kept


def test_admin_cannot_delete_or_demote_self(people):
    admin = people["admin"]
    ac = client_for(admin)
    ac.post(f"/portal/users/{admin.pk}/delete/")
    assert User.objects.filter(pk=admin.pk).exists()
    resp = ac.post(f"/portal/users/{admin.pk}/edit/", {
        "first_name": "A", "email": admin.email, "role": "student", "is_active": "on",
        "specialty": "general", "rate_per_job": "250", "availability": "on_duty",
    })
    assert resp.status_code == 200
    admin.refresh_from_db()
    assert admin.role == User.Role.ADMIN


def test_portal_lists_every_user(people):
    page = client_for(people["admin"]).get("/portal/users/").content.decode()
    for user in people.values():
        assert user.email in page


def test_non_admin_with_all_features_still_cannot_open_portal(people):
    staff = people["staff"]
    staff.features = list(F.ALL_FEATURE_CODES)
    staff.save()
    assert client_for(staff).get("/portal/users/").status_code == 403


# ---- payments --------------------------------------------------------------

def _verified_ticket(people):
    student, admin, worker = people["student"], people["admin"], people["worker"]
    ticket = make_ticket(student)
    ticket = workflow.perform_transition(ticket, admin, "ASSIGNED", {"assignee": worker})
    ticket = workflow.perform_transition(ticket, worker, "IN_PROGRESS")
    ticket = workflow.perform_transition(ticket, worker, "REPORTED_FIXED", {"checklist": True})
    return workflow.perform_transition(ticket, student, "VERIFIED_FIXED")


def test_admin_marks_payment_paid_and_worker_sees_only_own(people):
    ticket = _verified_ticket(people)
    payment = WorkerPayment.objects.get(ticket=ticket)
    WorkerPayment.objects.create(worker=people["other_worker"], kind="bonus", amount=Decimal("99"),
                                 description="Other worker bonus")

    ac = client_for(people["admin"])
    resp = ac.post(f"/payments/{payment.pk}/paid/", {"method": "upi", "reference": "UPI123"})
    assert resp.status_code == 302
    payment.refresh_from_db()
    assert payment.status == "paid" and payment.reference == "UPI123" and payment.paid_at

    page = client_for(people["worker"]).get("/payments/").content.decode()
    assert "My earnings" in page and ticket.code in page
    assert "Other worker bonus" not in page
    # workers cannot mark payments paid
    assert client_for(people["worker"]).post(f"/payments/{payment.pk}/paid/", {"method": "upi"}).status_code == 403


def test_admin_records_manual_payment_and_exports_csv(people):
    ac = client_for(people["admin"])
    resp = ac.post("/payments/new/", {
        "worker": people["worker"].pk, "kind": "salary", "amount": "12000",
        "description": "October salary", "pay_now": "on", "method": "bank", "reference": "NEFT1",
    })
    assert resp.status_code == 302
    p = WorkerPayment.objects.get(description="October salary")
    assert p.status == "paid" and p.worker_name
    csv_resp = ac.get("/payments/", {"export": "csv"})
    assert csv_resp["Content-Type"].startswith("text/csv")
    assert "October salary" in csv_resp.content.decode()


# ---- dashboard & locator -----------------------------------------------------

def test_dashboard_counts_complaints(people):
    _verified_ticket(people)
    make_ticket(people["other_student"], title="Another problem here")
    resp = client_for(people["admin"]).get("/dashboard/", {"period": "7"})
    assert resp.status_code == 200
    s = resp.context["s"]
    assert s["total"] == 2 and s["resolved"] == 1 and s["open"] == 1
    assert len(s["trend"]["columns"]) == 7
    assert client_for(people["staff"]).get("/dashboard/").status_code == 200


def test_worker_location_update_and_locator(people):
    worker = people["worker"]
    loc = make_location("Mess Hall", "Kitchen")
    wc = client_for(worker)
    resp = wc.post("/accounts/my-location/", {
        "current_location": loc.pk, "availability": "on_duty", "lat": "28.545100", "lng": "77.192600",
    })
    assert resp.status_code == 302
    worker.refresh_from_db()
    assert worker.current_location == loc and worker.last_lat is not None

    page = client_for(people["staff"]).get("/workers/").content.decode()
    assert "Mess Hall" in page and worker.display_name in page and "google.com/maps" in page
    # students cannot locate workers by default
    assert client_for(people["student"]).get("/workers/").status_code == 403
