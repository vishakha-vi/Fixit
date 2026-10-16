import pytest
from django.test import Client

from apps.accounts.models import User


@pytest.fixture
def demo_users(db):
    password = "TestSecretPassword123!"
    users = {
        "requester": User.objects.create_user(
            username="test_requester",
            email="req@test.com",
            password=password,
            role=User.Role.STUDENT,
        ),
        "technician": User.objects.create_user(
            username="test_technician",
            email="tech@test.com",
            password=password,
            role=User.Role.WORKER,
        ),
        "admin": User.objects.create_user(
            username="test_admin",
            email="admin@test.com",
            password=password,
            role=User.Role.ADMIN,
            is_staff=True,
        ),
    }
    return users, password


def test_login_success_for_all_roles(demo_users):
    users, password = demo_users
    client = Client()

    for role_name, user in users.items():
        login_success = client.login(username=user.username, password=password)
        assert login_success is True, f"Failed to login user {user.username} with role {role_name}"
        client.logout()


def test_login_wrong_password_fails(demo_users):
    users, _ = demo_users
    client = Client()
    user = users["requester"]
    login_success = client.login(username=user.username, password="WrongPassword!")
    assert login_success is False


def test_logout_requires_post(demo_users):
    users, password = demo_users
    client = Client()
    client.login(username=users["requester"].username, password=password)

    # In Django 5+, LogoutView strictly requires POST
    get_resp = client.get("/accounts/logout/")
    assert get_resp.status_code == 405

    # POST logout succeeds
    post_resp = client.post("/accounts/logout/")
    assert post_resp.status_code in (302, 200)
    assert "_auth_user_id" not in client.session


def test_login_with_email_address(demo_users):
    users, password = demo_users
    client = Client()
    assert client.login(username="REQ@test.com", password=password) is True


def test_deactivated_user_cannot_login(demo_users):
    users, password = demo_users
    user = users["technician"]
    user.is_active = False
    user.save()
    assert Client().login(username=user.username, password=password) is False
