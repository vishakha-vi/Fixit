import os
import subprocess
import sys

from django.conf import settings


def test_auth_user_model():
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_timezone_and_use_tz():
    assert settings.TIME_ZONE == "Asia/Kolkata"
    assert settings.USE_TZ is True


def test_missing_secret_key_raises_when_debug_false():
    env = os.environ.copy()
    env["DEBUG"] = "False"
    env["SECRET_KEY"] = ""

    cmd = [
        sys.executable,
        "-c",
        "import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; import django; django.setup()",
    ]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "SECRET_KEY environment variable is required when DEBUG is False" in proc.stderr
