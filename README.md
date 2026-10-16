# FixIt 🔧

> *"FixIt measures whether things actually got fixed, not whether tickets got closed."*

FixIt is a modern, transparent campus and residential maintenance request management system designed for universities and housing communities.

Unlike legacy ticketing systems where technicians mark tasks "completed" without resident verification, FixIt enforces resident confirmation (or verified on-site completion codes) before any ticket is marked `VERIFIED_FIXED`.

---

## 🚀 Quickstart

### Prerequisites
- Python 3.12+ (or Python 3.13)
- Git

### 1. Using `make` (Unix / WSL / Git Bash with Make)

```bash
# Setup virtual environment and dependencies
make setup

# Apply database migrations
make migrate

# Launch local development server
make run

# Run automated tests
make test

# Run linter
make lint

# Execute runtime smoke tests
make smoke
```

### 2. Without `make` (Windows PowerShell / Plain Terminal)

```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Apply database migrations
python manage.py migrate

# 4. (Optional) Initialize demo users and clock
# Requires DEMO_MODE=True in environment
$env:DEMO_MODE="True"
python manage.py reset_demo --yes

# 5. Start development server
python manage.py runserver 127.0.0.1:8000

# 6. Run test suite
pytest -q

# 7. Run code linting
ruff check .

# 8. Run smoke test against running server
python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` for local customizations.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | None | Cryptographic key. Required when `DEBUG=False`. |
| `DEBUG` | `False` | Enables development error diagnostics. |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | Database connection string (PostgreSQL in production). |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Permitted HTTP host headers. |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8000` | Whitelisted origins for CSRF POST requests. |
| `DEMO_MODE` | `False` | Enables simulated demo clock and `reset_demo` command. |
| `DEMO_PASSWORD` | `DemoFixItPass123!` | Password assigned to recreated demo users. |
| `APP_VERSION` | `0.1.0-phase0` | Release version tag shown on landing page and `/healthz`. |

---

## 🧪 Testing

FixIt includes comprehensive test suites covering configuration, authentication, simulated clocks, state machines, priority rules, and static source scans:

```bash
# Run pytest with quiet reporting
pytest -q

# Run full tests with detailed output
pytest -v

# Run smoke test against target deployment
python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

---

## 📁 Project Structure

```
fixit/
├── apps/
│   ├── accounts/       # Custom User model (requester, technician, admin)
│   ├── core/           # Health check (/healthz), clock simulation, demo tools
│   ├── locations/      # Facility and campus space placeholders (Phase 1)
│   └── tickets/        # Maintenance request workflows (Phase 1)
├── config/             # Django settings, WSGI, ASGI, and URL routing
├── docs/               # Architecture decisions, state machines, and priority rules
├── scripts/            # Asset vendoring and deployment smoke test scripts
├── static/vendor/      # Vendored Bootstrap 5 and HTMX assets (no runtime CDN)
├── templates/          # Server-rendered semantic templates (Bootstrap 5)
├── tests/              # Pytest test suite for validation gates
├── Dockerfile          # Production container specification
├── docker-compose.yml  # Local multi-container stack with PostgreSQL
├── render.yaml         # Render deployment blueprint
└── pyproject.toml      # Tool configurations for ruff and pytest
```

---

## 📚 Documentation Links

- [00. Architecture Decisions & Setting](file:///c:/Users/MAHENDRA/Desktop/hackvision%20website/docs/00-decisions.md)
- [01. State Machine Specification](file:///c:/Users/MAHENDRA/Desktop/hackvision%20website/docs/01-state-machine.md) and [YAML Definition](file:///c:/Users/MAHENDRA/Desktop/hackvision%20website/docs/state_machine.yaml)
- [02. Priority Rules & SLAs](file:///c:/Users/MAHENDRA/Desktop/hackvision%20website/docs/02-priority-rules.md) and [YAML Definition](file:///c:/Users/MAHENDRA/Desktop/hackvision%20website/docs/priority_rules.yaml)
- [03. Permission Matrix](file:///c:/Users/MAHENDRA/Desktop/hackvision%20website/docs/03-permission-matrix.md)
- [04. 35 Verification Scenarios Checklist](file:///c:/Users/MAHENDRA/Desktop/hackvision%20website/docs/04-scenarios.md)
- [05. Assumptions & Limitations](file:///c:/Users/MAHENDRA/Desktop/hackvision%20website/docs/05-assumptions-limitations.md)
- [Render Deployment Guide](file:///c:/Users/MAHENDRA/Desktop/hackvision%20website/docs/DEPLOY.md)

---

## 📦 Third-Party Libraries and Data Sources

- **Django** (BSD 3-Clause) — High-level Python web framework.
- **Bootstrap 5.3.3** (MIT) — Responsive front-end toolkit, vendored locally.
- **HTMX 2.0.4** (BSD 2-Clause) — Modern browser interactivity via HTML attributes, vendored locally.
- **WhiteNoise** (MIT) — Production static file serving.
- **dj-database-url** (BSD 2-Clause) — 12-factor database configuration.
- **psycopg** (LGPLv3 / BSD) — PostgreSQL database adapter.
- **PyYAML** (MIT) — YAML parsing for state machine and priority specifications.
- **pytest & pytest-django** (MIT / BSD) — Testing framework.
- **ruff** (MIT) — Fast Python linter.
- **Gunicorn** (MIT) — WSGI HTTP Server for production deployment.
