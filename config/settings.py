import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Read .env file if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, v = stripped.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# DEBUG defaults to False
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t", "yes")

# SECRET_KEY validation
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY environment variable is required when DEBUG is False.")
    SECRET_KEY = "fixit-insecure-dev-secret-key-change-in-production"

# ALLOWED_HOSTS
allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", "")
if allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]
elif DEBUG:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
else:
    ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # FixIt local apps
    "apps.accounts",
    "apps.core",
    "apps.locations",
    "apps.tickets",
    "apps.payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.DueTasksMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.fixit",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database configuration
default_db_url = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
database_url = os.environ.get("DATABASE_URL", default_db_url)
DATABASES = {
    "default": dj_database_url.config(
        default=database_url,
        conn_max_age=600,
    )
}

# Custom User Model
AUTH_USER_MODEL = "accounts.User"

# Sign in with email address or username
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailOrUsernameBackend"]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization and Timezone
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication URLs
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# CSRF Trusted Origins
csrf_trusted_env = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
if csrf_trusted_env:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_trusted_env.split(",") if origin.strip()]
elif DEBUG:
    CSRF_TRUSTED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]
else:
    CSRF_TRUSTED_ORIGINS = []

# Security settings in production
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # SECURE_COOKIES=False only for plain-http local use of a production build
    _secure_cookies = os.environ.get("SECURE_COOKIES", "True").lower() in ("true", "1", "t", "yes")
    CSRF_COOKIE_SECURE = _secure_cookies
    SESSION_COOKIE_SECURE = _secure_cookies
    # Allow controlling redirect via env for local production-simulation or proxy testing
    if os.environ.get("SECURE_SSL_REDIRECT", "True").lower() in ("true", "1", "t", "yes"):
        SECURE_SSL_REDIRECT = True

# Bootstrap alert classes for django.contrib.messages
MESSAGE_TAGS = {40: "danger"}

# Email notifications for reminders (console output unless SMTP is configured)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() in ("true", "1", "t", "yes")
    EMAIL_TIMEOUT = 10
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_NOTIFICATIONS = bool(EMAIL_HOST)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "FixIt <no-reply@fixit.local>")

# Students may create their own accounts; staff and workers are created by admins
ALLOW_STUDENT_SIGNUP = os.environ.get("ALLOW_STUDENT_SIGNUP", "True").lower() in (
    "true", "1", "t", "yes"
)

# Demo mode & Versioning
DEMO_MODE = os.environ.get("DEMO_MODE", "False").lower() in ("true", "1", "t", "yes")
# Print demo usernames + password on the sign-in page (never on public sites by default)
DEMO_SHOW_CREDENTIALS = os.environ.get(
    "DEMO_SHOW_CREDENTIALS", "True" if DEBUG else "False"
).lower() in ("true", "1", "t", "yes")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0-mvp")
