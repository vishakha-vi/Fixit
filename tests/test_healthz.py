from unittest.mock import patch

from django.db import OperationalError
from django.test import Client


def test_healthz_healthy():
    client = Client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["db"] is True
    assert "version" in data
    assert "demo_mode" in data
    assert "time" in data


def test_healthz_db_failure():
    client = Client()
    with patch("django.db.connection.cursor", side_effect=OperationalError("Database connection lost")):
        resp = client.get("/healthz")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "error"
        assert data["db"] is False
        assert "version" in data
        assert "time" in data
