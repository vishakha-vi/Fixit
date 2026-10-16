# FixIt 🔧

> *"FixIt measures whether things actually got fixed, not whether tickets got closed."*

FixIt is a campus and residential maintenance complaint system for universities and housing communities.
Students and staff raise complaints, admins assign them to workers, workers fix them, and a complaint only
counts as **fixed** once the person who raised it confirms it (or the worker enters that person's on-site
completion code). Workers are paid per *verified* fix.

---

## ✨ Features

| Feature | What it does |
|---|---|
| **Dashboard** | How many complaints come in across campus: totals, open/overdue counts, average time to fix, a raised-vs-fixed trend per day, and breakdowns by status, category, building and priority, plus a worker performance table. Filter by period and building. |
| **Complaint tracking** | Every complaint gets a number (`FIX-00012`). The **Track** page and each complaint page show a progress tracker (Submitted → Reviewed → Worker assigned → In progress → Reported fixed → Confirmed fixed), a full timeline, comments and the SLA countdown. |
| **Reminders** | In-app reminder inbox with a badge in the menu. Send a reminder from any complaint to the worker, the requester or the admins (now or at a set time), add personal reminders, and get **automatic** reminders: unassigned complaints, half the SLA used, overdue jobs and "please confirm the fix". Unconfirmed fixes close automatically after 72 hours. Optional email through SMTP. |
| **Worker payments** | A pending payment is created automatically when a fix is confirmed (worker's rate per job + material cost). Admins mark payments paid (UPI, bank, cash or cheque, with a reference number), pay a worker's whole balance at once, add salary, bonus or adjustment entries, and export CSV. Workers see their own earnings. |
| **Worker locator** | Shows where every worker is, grouped by building: available, busy on a job, off duty or on leave. Shows their current job, phone, home area and optional GPS position (opens in Google Maps). Workers update their location and availability themselves, and starting a job moves them to that job's location. Admins see workers who cover the building first when assigning. |
| **Admin portal** | `/portal/`: create, edit, deactivate and delete **any** account, choose exactly which features each person can use, reset passwords, see every record for each user (complaints, jobs, payments, reminders, activity), and manage buildings and rooms. |

### Roles and feature access

Each account has a role, and the admin can switch individual features on or off for every user.

| Feature | Student | Staff | Worker | Admin |
|---|:-:|:-:|:-:|:-:|
| Raise complaints | ✓ | ✓ | | ✓ |
| Track own complaints, confirm fix, reopen | ✓ | ✓ | | ✓ |
| Work on assigned jobs | | | ✓ | ✓ |
| View all complaints (read-only) | | ✓ | | ✓ |
| Manage complaints (assign, reassign, reject, merge) | | | | ✓ |
| Dashboard | | ✓ | | ✓ |
| Reminders | ✓ | ✓ | ✓ | ✓ |
| My earnings | | | ✓ | ✓ |
| Worker payments (all workers) | | | | ✓ |
| Worker locator | | ✓ | | ✓ |
| Admin portal (users and access) | | | | ✓ |

*(✓ = default for new accounts. Admins always have everything; for everyone else the admin decides.)*

- **Students** can sign up themselves at `/accounts/signup/`, or get an account from the admin.
- **Staff and workers** are created by the admin in the portal. They sign in with the **email address** the admin entered. If the admin leaves the password empty, a strong temporary password is generated and shown once.

---

## 🔑 Admin portal and demo accounts

| What | Where |
|---|---|
| Admin portal (users, access, buildings) | `/portal/` |
| Raw database admin (Django admin) | `/admin/` |
| Dashboard | `/dashboard/` |

With `DEMO_MODE=True`, `python manage.py reset_demo --yes` loads a demo campus: 8 buildings, 10 users and about 45
complaints in every state, with payments and reminders. Every demo account uses the password in
`DEMO_PASSWORD` (default `DemoFixItPass123!`). You can sign in with either the username or the email:

| Role | Username | Email |
|---|---|---|
| Admin | `admin_demo` | `admin@demo.campus.edu` |
| Staff (warden) | `staff_demo` | `staff@demo.campus.edu` |
| Student | `student_demo` | `student@demo.campus.edu` |
| Worker (electrician) | `worker_demo` | `worker@demo.campus.edu` |

Other demo users are `priya_demo` and `arjun_demo` (students), and `suresh_demo`, `anita_demo`, `vikram_demo` and `imran_demo` (workers).
In demo mode the admin portal also has **demo clock** buttons (+1h / +24h / +72h). Use them to see SLA
reminders, overdue alerts and the 72-hour auto-close happen.

For a real deployment, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` and run `python manage.py setup_site` (the
Render blueprint does this on every deploy). That creates your admin account. Set `DEMO_MODE=False` to start with an empty campus.

---

## 🚀 Quickstart

### Prerequisites
- Python 3.12+
- Git

### Windows PowerShell

```powershell
# 1. Create and activate a virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Development settings
$env:DEBUG="True"; $env:DEMO_MODE="True"

# 4. Create the database and load the demo campus
python manage.py migrate
python manage.py reset_demo --yes

# 5. Start the server, then open http://127.0.0.1:8000
python manage.py runserver 127.0.0.1:8000
```

### macOS / Linux / WSL (`make`)

```bash
make setup
export DEBUG=True DEMO_MODE=True
make migrate
make reset-demo
make run
```

### Checks

```bash
pytest -q                                              # automated tests
ruff check .                                           # linter
python manage.py makemigrations --check --dry-run      # migrations up to date
python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

### Useful commands

| Command | Purpose |
|---|---|
| `python manage.py reset_demo --yes` | Wipe complaints, payments and reminders, then reload the demo campus (DEMO_MODE only) |
| `python manage.py setup_site` | Idempotent deploy step: create the admin from env and seed demo data if empty (demo mode) |
| `python manage.py ensure_admin --email you@x.edu --password ...` | Create or promote an admin account |
| `python manage.py run_scheduler` | Run time-based rules now (auto-close, SLA reminders). They also run automatically, at most once a minute, while people use the site. |

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
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_NAME` | empty | Main admin account created by `setup_site` / `ensure_admin`. |
| `ALLOW_STUDENT_SIGNUP` | `True` | Let students register themselves. |
| `DEMO_MODE` | `False` | Enables the demo clock, `reset_demo` and demo seeding. |
| `DEMO_PASSWORD` | `DemoFixItPass123!` | Password for the demo users. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | empty | Optional SMTP. When set, reminders are also emailed. |
| `APP_VERSION` | `1.0.0-mvp` | Release version shown in the footer and `/healthz`. |

---

## 📁 Project Structure

```
fixit/
├── apps/
│   ├── accounts/       # User model, roles, feature access, sign-up, admin portal, worker locator
│   ├── core/           # Home, dashboard, /healthz, clock, demo seed and setup commands
│   ├── locations/      # Buildings and rooms/areas
│   ├── payments/       # Worker payments and earnings
│   └── tickets/        # Complaints, state machine engine, priority/SLA, reminders, stats
├── config/             # Django settings, WSGI, ASGI and URL routing
├── docs/               # Architecture decisions, state machine, priority rules, scenarios
├── scripts/            # Asset vendoring and deployment smoke test
├── static/             # Vendored Bootstrap 5 + HTMX (no runtime CDN) and FixIt CSS
├── templates/          # Server-rendered pages (Bootstrap 5)
├── tests/              # Pytest suite
├── Dockerfile          # Production container
├── docker-compose.yml  # Local stack with PostgreSQL
└── render.yaml         # Render deployment blueprint
```

The complaint lifecycle is driven by [`docs/state_machine.yaml`](docs/state_machine.yaml): the code reads
the states, the allowed transitions and the role rules from that file, and enforces each guard listed there.
Priority and SLA follow [`docs/priority_rules.yaml`](docs/priority_rules.yaml).

---

## 📚 Documentation

- [00. Architecture Decisions](docs/00-decisions.md)
- [01. State Machine Specification](docs/01-state-machine.md) and [YAML Definition](docs/state_machine.yaml)
- [02. Priority Rules & SLAs](docs/02-priority-rules.md) and [YAML Definition](docs/priority_rules.yaml)
- [03. Permission Matrix](docs/03-permission-matrix.md)
- [04. Verification Scenarios Checklist](docs/04-scenarios.md)
- [05. Assumptions & Limitations](docs/05-assumptions-limitations.md)
- [Render Deployment Guide](docs/DEPLOY.md)

---

## 📦 Third-Party Libraries and Data Sources

- **Django** (BSD 3-Clause): high-level Python web framework.
- **Bootstrap 5.3.3** (MIT): responsive front-end toolkit, vendored locally.
- **HTMX 2.0.4** (BSD 2-Clause): browser interactivity through HTML attributes, vendored locally.
- **WhiteNoise** (MIT): production static file serving.
- **dj-database-url** (BSD 2-Clause): 12-factor database configuration.
- **psycopg** (LGPLv3 / BSD): PostgreSQL database adapter.
- **PyYAML** (MIT): YAML parsing for the state machine and priority specifications.
- **pytest & pytest-django** (MIT / BSD): testing framework.
- **ruff** (MIT): fast Python linter.
- **Gunicorn** (MIT): WSGI HTTP server for production deployment.
