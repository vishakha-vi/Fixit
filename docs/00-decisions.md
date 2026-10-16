# 00. Architecture Decisions and Context

## Project Setting

- **Product:** FixIt — Home and campus maintenance request management platform.
- **Context:** A residential university campus comprising:
  - Hostel Blocks (e.g., Hostel Block A, Hostel Block B)
  - Academic Building (e.g., Main Academic Complex)
  - Mess / Dining Hall (e.g., Central Campus Mess)
- **Roles:**
  - `requester`: Students, faculty, and residents submitting requests, adding notes, confirming repairs, or reopening requests.
  - `technician`: Campus maintenance technicians performing repairs, pausing for parts/access, and submitting repair reports.
  - `admin`: Facility managers triaging, assigning, reassigning, overriding priority, or handling exceptions.

## Core Product Thesis

> *"FixIt measures whether things actually got fixed, not whether tickets got closed."*

The UI must never show a repair as complete merely because a technician marked it as fixed. The repair reaches `REPORTED_FIXED` (amber) when the technician reports work complete. It transitions to `VERIFIED_FIXED` (green) only when confirmed by the requester or via an on-site completion code provided by the requester.

## Architecture and Technology Choices

| Decision | Selection | Rationale |
|---|---|---|
| **Backend Framework** | Django 5.2 LTS (Python 3.12+ compatible) | Built-in ORM, auth, form validation, admin interface, robust migration system, long-term stability. |
| **Database** | PostgreSQL (Prod/CI), SQLite (Local dev/test) | `dj-database-url` and `psycopg[binary]` enable identical ORM models with lightweight zero-setup local developer velocity and robust production transactions. |
| **Frontend Strategy** | Server-rendered Django templates + HTMX + Bootstrap | Interactive, SPA-like feel without client-side build pipelines, complex bundles, or node runtime dependencies. |
| **Asset Delivery** | Vendored static files via WhiteNoise | Complete offline independence; no external runtime CDN dependencies. Zero CDN latency or downtime vulnerability. |
| **Time Management** | Centralized `apps/core/clock.py` (`now()`) | Deterministic testing and realistic demo-clock simulation. Direct calls to `datetime.now()` or `timezone.now()` outside `apps/core/clock.py` are strictly banned. |
| **Deployment Platform** | Render + Docker | Reproducible Linux container environment running Gunicorn, automated database migrations, WhiteNoise static collection, and declarative `render.yaml`. |
| **Testing & Linting** | pytest, pytest-django, ruff | Fast, modern linting, strict code hygiene, declarative fixtures, and regression safety. |

## Non-Goals

1. **No IoT or Hardware Dependencies:** FixIt relies on human verification and interaction, not hardware sensors or smart locks.
2. **No AI/LLM Magic:** Triage and priority scoring follow deterministic, explainable, and audit-friendly business rules (see `02-priority-rules.md`).
3. **No Premature Feature Creep in Phase 0:** Phase 0 strictly builds scaffolding, config, health checks, clock control, base authentication views, and architectural contracts. Ticket workflows are deferred to Phase 1+.
4. **No Runtime CDNs:** All vendor CSS/JS libraries must be vendored into `static/vendor/` and served locally.
5. **No Secret Leaks:** All configuration passes through environment variables. `SECRET_KEY` must never be hardcoded and must fail startup if missing in production.

## TODO(user): Replace Placeholder Building Names with Real Ones

Before campus deployment, replace the following placeholder location data with official university facilities:
- `Hostel Block A` -> Real dormitory/hostel name (e.g., *Nilgiri Hostel*, *Banyan Hall*)
- `Hostel Block B` -> Real dormitory/hostel name (e.g., *Aravali Hostel*, *Cedar Hall*)
- `Main Academic Complex` -> Real academic building (e.g., *Aryabhatta Academic Block*)
- `Central Campus Mess` -> Real mess/dining hall (e.g., *Annapurna Dining Facility*)
- `Campus Health Center` -> Real medical unit name
- `Central Laboratories` -> Real laboratory complex name
