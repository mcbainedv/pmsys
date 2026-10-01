# PMSyS — Preventive Maintenance System (modern rebuild)

A browser-based re-implementation of the original Windows PMSyS application.
Containerized Python backend, HTML browser interface, and MariaDB persistence.
No Visual Basic anywhere.

- **Backend:** FastAPI + SQLAlchemy 2.x + Alembic (Python 3.12)
- **Frontend:** server-rendered Jinja2 pages + a dash of HTMX (no JS build step)
- **Database:** MariaDB 11
- **Deployment:** Docker Compose (two services: `db` + `app`)

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:8000>. Default credentials:

| Username | Password |
|----------|----------|
| `admin`  | `admin`  |

> Create your own users under **Setup → Users** (admin only) and change your own
> password under **Account**. Change the default password immediately in production.

On first start the app runs migrations, seeds the default admin account, and
(only on an empty database) loads a small demo dataset modeled on the original
example: a "Secure Energy" customer with fields, locations, equipment, service
codes, vendors and technicians.

## The planning workflow

1. **Setup** — define Customers → Fields → Locations → Equipment, plus Service
   Codes (with a frequency in *weeks*), Service Vendors, and Technicians.
2. **Draft Plan** — select equipment and a service to add items; the proposed
   date is computed from the scheduling rule below. Print the draft for review.
3. **Schedule** — approve and schedule items (assign a vendor and technician, or
   auto-assign evenly). Items move to the Final Plan with generated Work Order
   and Calibration report numbers.
4. **Final Plan** — print the final plan or open / print the Work Order and
   Calibration report for each item.
5. **Close out** — record the actual completion date/vendor/technician; this
   feeds the next scheduling cycle.
6. **History** — browse completed and cancelled work.

### The scheduling rule

```
Last Completed Date + Service Frequency (weeks) = Next Proposed Date
```

## Local development (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///./dev.db   # or point at a local MariaDB
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

WeasyPrint (PDF export) needs GTK/Pango system libraries; HTML reports and
browser print-to-PDF work regardless.

## Running tests

```bash
pytest          # unit tests (scheduling logic) + API integration tests (SQLite)
```

`tests/test_regressions.py` holds one regression test per defect found by the live QA pass
below. CI (`.github/workflows/ci.yml`) runs the suite on every push.

## QA and known issues

The rebuild was audited against a live instance on **port 8000**: four test passes (Setup
CRUD, the planning loop and History, auth/users/reports, and a static form ↔ route contract
audit) followed by two independent verification passes. The findings, their root causes and
the fixes are documented in [BUG_REPORT.md](BUG_REPORT.md); the per-area reports and
verification logs are under [`.qa/`](.qa/) with the shared live-test harness in
[`.qa/qa.py`](.qa/qa.py).

To re-run the live harness the app must be running at <http://127.0.0.1:8000> (see Quick
start), then:

```bash
.venv/bin/python .qa/qa.py forms /planning/draft   # inspect a page's forms and buttons
.venv/bin/python .qa/qa.py db "select count(*) from plans;"
```

## Enabling PDF export

The Docker image already installs the required libraries. Locally, install
WeasyPrint's system dependencies (`libpango`, `libcairo`, etc.) before
`pip install weasyprint`.

## Project layout

```
app/
  main.py           FastAPI app, middleware, route registration
  config.py         settings (pydantic-settings, .env)
  database.py       engine / session / Base
  models.py         SQLAlchemy models (all tables)
  services.py       pure scheduling business logic (unit-tested)
  auth.py           bcrypt hashing
  dependencies.py   get_db / current_user / require_admin
  seed.py           idempotent first-run seed
  routers/          auth, setup (CRUD), planning, history, reports
  templates/        Jinja2 templates
  static/           CSS + vendored HTMX
alembic/            migrations (initial schema is created from the models)
tests/              pytest suite
```