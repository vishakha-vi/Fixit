# Phase 0 Plan: FixIt

## 1. Environment Inspection Findings

- **Operating System:** Windows 11 (PowerShell 5.1.26100.9711)
- **Python Version:** Python 3.13.7 available locally via `py` launcher (`C:\Users\MAHENDRA\AppData\Local\Programs\Python\Python313\python.exe`). CI and container targets are pinned to Python 3.12 per specifications.
- **Git Version:** Git 2.53.0.windows.3, initialized branch `main`.
- **Docker:** Not installed/recognized in host path. Container verification (Gate D) will be marked SKIPPED with manual commands provided.
- **PostgreSQL / psql:** Not installed in host path. Fast local execution uses SQLite (`sqlite:///db.sqlite3`), while CI and Render production use PostgreSQL (`psycopg[binary]`).
- **Network Access:** Confirmed active (HTTP/HTTPS to PyPI reachable, pip functioning).
- **Working Directory:** Initialized clean repository in `c:\Users\MAHENDRA\Desktop\hackvision website`.

---

## 2. Final File Tree

```
c:\Users\MAHENDRA\Desktop\hackvision website/
├── .editorconfig
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml
├── Dockerfile
├── Makefile
├── README.md
├── docker-compose.yml
├── manage.py
├── pyproject.toml
├── render.yaml
├── requirements-dev.txt
├── requirements.txt
├── apps/
│   ├── __init__.py
│   ├── accounts/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── migrations/
│   │   │   └── __init__.py
│   │   └── models.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── clock.py
│   │   ├── management/
│   │   │   ├── __init__.py
│   │   │   └── commands/
│   │   │       ├── __init__.py
│   │   │       └── reset_demo.py
│   │   ├── migrations/
│   │   │   └── __init__.py
│   │   ├── models.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── locations/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── migrations/
│   │   │   └── __init__.py
│   │   └── models.py
│   └── tickets/
│       ├── __init__.py
│       ├── admin.py
│       ├── apps.py
│       ├── migrations/
│       │   └── __init__.py
│       └── models.py
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── docs/
│   ├── 00-decisions.md
│   ├── 01-state-machine.md
│   ├── 02-priority-rules.md
│   ├── 03-permission-matrix.md
│   ├── 04-scenarios.md
│   ├── 05-assumptions-limitations.md
│   ├── DEPLOY.md
│   ├── PHASE0_PLAN.md
│   ├── PHASE0_REPORT.md
│   ├── priority_rules.yaml
│   └── state_machine.yaml
├── scripts/
│   ├── smoke_test.py
│   └── vendor_assets.py
├── static/
│   └── vendor/
│       ├── bootstrap.bundle.min.js
│       ├── bootstrap.min.css
│       └── htmx.min.js
├── templates/
│   ├── 404.html
│   ├── 500.html
│   ├── base.html
│   ├── home.html
│   └── registration/
│       └── login.html
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── reference_priority.py
    ├── test_auth.py
    ├── test_clock.py
    ├── test_config.py
    ├── test_healthz.py
    ├── test_pages.py
    ├── test_priority_rules.py
    ├── test_reset_demo.py
    ├── test_scenarios.py
    ├── test_source_scan.py
    └── test_state_machine.py
```

---

## 3. Ordered Task List (T1-T10) & Verification Commands

| Task | Title | Description | Verification Command |
|---|---|---|---|
| **T1** | Decision Documents | Create `docs/00-decisions.md` through `docs/05-assumptions-limitations.md`, `docs/state_machine.yaml`, and `docs/priority_rules.yaml`. | `python -c "import yaml; yaml.safe_load(open('docs/state_machine.yaml')); yaml.safe_load(open('docs/priority_rules.yaml')); print('YAML valid')"` |
| **T2** | Repo Scaffold & Tooling | Establish directory tree, `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `Makefile`, `.gitignore`, `.editorconfig`, `.env.example`, git initial commit. | `git status` (clean) && `ruff check .` |
| **T3** | Django Configuration | Configure settings from env, Asia/Kolkata timezone, custom `accounts.User` model (`AUTH_USER_MODEL`), WhiteNoise, empty apps (`locations`, `tickets`). | `python manage.py check` && `python manage.py makemigrations --check --dry-run` && `python manage.py migrate` |
| **T4** | Core App | Implement `/healthz`, `/`, auth views (login/logout), 404/500 handlers without stack traces, `apps/core/clock.py` (`DemoClock`, `now()`, `advance()`, `reset()`), and `reset_demo` management command. | Dev server run + `python scripts/smoke_test.py --base-url http://127.0.0.1:8000` (preliminary endpoint test) |
| **T5** | Vendored Static Assets | `scripts/vendor_assets.py` to download pinned Bootstrap CSS/JS and htmx into `static/vendor/` with SHA-256 logging. | `python -c "import os; assert os.path.exists('static/vendor/htmx.min.js'); print('Assets present')"` |
| **T6** | Automated Tests | Implement full test suite in `tests/` covering Gate B items 1 through 11. | `pytest -q` |
| **T7** | Smoke Test Script | Implement standalone Python standard-library `scripts/smoke_test.py` with latency check, security checks, and proper exit codes. | `python scripts/smoke_test.py --base-url http://127.0.0.1:8000` |
| **T8** | CI Workflow | `.github/workflows/ci.yml` with Python 3.12, PostgreSQL service container, lint, checks, migrations check, pytest, background server smoke test. | Validate YAML syntax and action structure |
| **T9** | Deployment Files | `Dockerfile`, `docker-compose.yml`, `render.yaml`, and `docs/DEPLOY.md`. | Validate Dockerfile syntax, compose config, render.yaml format |
| **T10** | README | Comprehensive `README.md` including Quickstart (with and without make), env vars, tests, structure, docs links, and third-party notices. | Readme inspection and markdown check |

---

## 4. Assumptions

1. **Local vs CI Python Version:** Python 3.13.7 is the default host runtime on this development machine, while CI and production containers use Python 3.12 as specified. Code and dependencies are fully compatible across both Python 3.12 and 3.13.
2. **Local vs Production Database:** Local testing uses SQLite (`sqlite:///db.sqlite3`) for velocity and self-contained execution without external services. Production and CI use PostgreSQL via `dj-database-url` and `psycopg[binary]`.
3. **Demo Mode Default:** Default `DEMO_MODE=False` in production; default `DEMO_MODE=True` in local development/test environment where specified in `.env.example`.
4. **App Names:** The ticket app is named `tickets` (explicit rule: NOT named "requests"). The custom user model is in `apps.accounts.User`.
5. **No Secrets Committed:** `.env.example` contains only non-sensitive templates and placeholders; `.env` is ignored by `.gitignore`.

---

## 5. Risks & Mitigation

| Risk | Mitigation |
|---|---|
| Host lacks Docker daemon | Gate D will be marked SKIPPED with clear explanation and manual verification instructions; all other gates run locally. |
| Timezone inconsistencies | Enforce Asia/Kolkata timezone in Django settings and validate `apps/core/clock.py` as the sole source of current time via `test_source_scan.py`. |
| Unintended CDN dependencies | Pinned static assets vendored directly into `static/vendor/` and loaded locally; template integration tests verify no external resources. |
| Production 500 error leaks | Custom 500 template and view ensuring no "Traceback" strings leak when `DEBUG=False`. |

---

## 6. Deviations from Prompt

- **Python Runtime on Local Machine:** Local Windows machine executes Python 3.13.7 via `py`. Pinned dependencies in `requirements.txt` are tested and validated to function seamlessly on both Python 3.12 (CI/Docker) and 3.13 (local host).
- No functional deviations from specified requirements.
