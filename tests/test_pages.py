from django.test import Client, RequestFactory

from apps.core.views import custom_500_view


def test_home_page():
    client = Client()
    resp = client.get("/")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "FixIt" in content
    assert "Sign in" in content or "login" in content.lower()


def test_login_page():
    client = Client()
    resp = client.get("/accounts/login/")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "Sign in" in content
    assert 'name="username"' in content
    assert 'name="password"' in content


def test_404_page():
    client = Client()
    resp = client.get("/this-route-definitely-does-not-exist/")
    assert resp.status_code == 404
    content = resp.content.decode("utf-8")
    assert "404" in content
    assert "Traceback" not in content


def test_500_page_does_not_leak_traceback():
    factory = RequestFactory()
    request = factory.get("/")
    resp = custom_500_view(request)
    assert resp.status_code == 500
    content = resp.content.decode("utf-8")
    assert "500" in content
    assert "Incident Reference ID" in content
    assert "Traceback" not in content
    assert "Exception" not in content
