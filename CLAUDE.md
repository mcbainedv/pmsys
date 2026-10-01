# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A FastAPI + Jinja2 + HTMX (server-rendered) rebuild of the legacy Windows PMSyS
preventive-maintenance app. Python only, MariaDB storage, Dockerized. See
`README.md` for the product workflow and quick start.

## Commands

```bash
# Run tests (SQLite, no DB service required) — always run after changes
pytest

# Local dev server (needs a DATABASE_URL; SQLite is fine for smoke testing)
export DATABASE_URL=sqlite:///./dev.db
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload

# Full stack (the real target — MariaDB in Docker)
cp .env.example .env && docker compose up --build

# Create a new migration after editing app/models.py:
#   - edit the initial migration idiom is NOT used for schema diffs; instead:
alembic revision --autogenerate -m "describe change"   # then `alembic upgrade head`
```

## Architecture map (the big picture)

- **`app/models.py`** — all SQLAlchemy models in one place. The central one is
  `Plan`: its `status` field (`draft` → `scheduled` → `completed`) is what drives
  which tab a row appears in (Draft Plan / Final Plan / History). `wo_no`/`cm_no`
  are stamped at schedule time.
- **`app/services.py`** — pure business logic (no DB): the scheduling formula
  `last_completed + frequency_weeks = proposed_date`, work-order/calibration
  numbering, and round-robin auto-assign. This is the unit-tested correctness core.
- **`app/routers/`** — one router per area: `auth` (login/users), `setup` (CRUD
  for all reference tables), `planning` (draft→schedule→closeout), `history`,
  `reports` (printable HTML + WeasyPrint PDF).
- **`app/database.py` / `app/dependencies.py`** — `get_db` is defined in
  `database.py` and re-exported through `dependencies.py`; tests override it via
  `app.dependency_overrides[get_db]`, so **always import `get_db` from
  `app.dependencies`** (or `app.database`) — never redefine it.
- **`app/seed.py`** — idempotent first-run seed: default `admin`/`admin` user and
  demo data. Runs automatically on container start.
- **Auth** — Starlette `SessionMiddleware` (signed cookie) + bcrypt. `current_user`
  / `require_admin` deps raise `HTTPException(401/403)`; a handler in `main.py`
  redirects 401 → `/login`. Templates read `request.url.path` to highlight nav.
- **`alembic/versions/0001_initial.py`** — creates the whole schema from
  `Base.metadata`; later migrations should be `--autogenerate`d.

## Gotchas

- **Reports vs. web styling**: report templates (`templates/reports/*`) inline
  their CSS via `reports/_doc_style.html` rather than linking `/static/css/app.css`,
  because WeasyPrint renders from an HTML string with no base URL and would drop
  an external stylesheet.
- **Report templates are rendered with `templates.env.get_template(...).render(ctx)`**
  — not `TemplateResponse` — so they do **not** get `request` auto-injected; pass
  `"request": request` in the context explicitly (see `app/routers/reports.py`).
- **`.env` and `tests/` are excluded** from the Docker image (`.dockerignore`), so
  don't rely on tests or secrets being present inside a container.
- **IntegrityError on delete** of a customer/field/location/equipment/service that
  has dependent rows is caught and surfaced via flash (see `_safe_delete` in
  `app/routers/setup.py`).
- Password hashing uses bcrypt directly (`app/auth.py`), not `passlib`.