# PMSyS — Bug report from live QA of the port-8000 build

**Application:** `pmsys/` modern rebuild (FastAPI + Jinja2 + MariaDB, Dockerized)
**Target under test:** `http://127.0.0.1:8000` — container `pmsys-app-1`, database `pmsys-db-1`
**Build tested:** the image that had been running for ~25 h (pre-fix revision of `app/`)
**Test date:** 2026-10-01
**Method:** four parallel test subagents, each with a disjoint area, driving the real HTTP
server on port 8000 (live MariaDB, real cookies, real redirects()) plus a 39-form static
template↔route contract audit. All actions were reproduced with raw HTTP; evidence bodies
are saved under `pmsys/.qa/evidence/` and the raw per-tester logs are in
`pmsys/.qa/findings_*.md` / `pmsys/.qa/coverage_*.md`.

| Area | Checks | PASS | BUG | GAP |
|---|---|---|---|---|
| Setup CRUD (7 tabs) | 133 | 61 | 53 | 19 |
| Planning loop + History | 78 | 41 | 34 | 2 |
| Auth / users / account / reports / static | 90 | 61 | 24 | 4 |
| Static contract audit (39 forms, 29 actions, 40 handlers, 20 templates) | 39 forms | — | 9 | 2 |

**Headline:** the app's happy paths largely work (full draft → schedule → final → closeout →
history loop verified, scheduling maths correct, users/passwords/reports/PDF fine), but
**32 confirmed defects** were found — 11 high severity, including **8 distinct HTTP 500
crash paths** and one silent data-loss bug:
the "Auto-assign evenly" button crashed 100 % of the time, adding equipment without a
Location crashed, over-long text and rename-to-duplicate crashed, and every empty-selection
or empty-required-field submission dumped raw FastAPI JSON (422) on the user. Deleting a
customer/field silently cascade-deleted its children, cancelled work had no way to be
created, and the printed Final Plan was missing its schedule/vendor/technician/work-order
columns. All of these are now fixed and verified on the live server; see “Fixes applied” and
“Verification” below.

---

## 1. Confirmed defects and their status

Severity: **high** = button broken / HTTP 500 / silent data loss or corruption;
**medium** = wrong or misleading behaviour; **low** = cosmetic or hardening.

| # | Sev | Defect | Repro | Root cause | Status |
|---|---|---|---|---|---|
| 1 | high | **"Auto-assign evenly" always 500s** (`TypeError: 'str' object is not callable`) | Draft → tick items → tick Auto-assign evenly → Schedule selected | `planning.py` form field `auto_assign: str` shadowed the imported `services.auto_assign` function | **Fixed** |
| 2 | high | **Add equipment without a Location → HTTP 500** (FK violation) | Setup → Equipment → leave Location at “— Location —” → Add | `location_id=0` written to a NOT NULL FK; no validation | **Fixed** |
| 3 | high | **Unchecking “Active” is ignored** (equipment *and* technicians, create *and* edit) | Untick Active → Save → row is still Active | `is_active: str = Form("on")` — an absent checkbox took the default “on” | **Fixed** |
| 4 | high | **Over-long text → HTTP 500** (`DataError 1406`) | Paste >128 chars into Customer name / >32 into Service code / >64 into Tag 1, Vendor name, First name → Save | No length validation; forms had no `maxlength` | **Fixed** |
| 5 | high | **Rename to an existing unique name/code → HTTP 500** (`IntegrityError 1062`) | Edit a customer/service/vendor and set a name already used by another row → Save changes | Duplicate check existed only in the INSERT branch | **Fixed** |
| 6 | high | **Non-existent FK parent id → HTTP 500** (`IntegrityError 1452`) | POST a Setup form with a stale/tampered `customer_id` / `field_id` / `location_id` | Inserts committed without checking the parent exists | **Fixed** |
| 7 | high | **Invalid schedule/closeout vendor or technician → HTTP 500** (`plans_ibfk_3`) | Schedule or close out with a `vendor_id` / `personnel_id` that no longer exists | Ids written to FK columns unvalidated | **Fixed** |
| 8 | high | **Deleting a Customer or Field silently cascade-deletes children** (data loss) | Create customer → field → location, then Delete the customer/field | `cascade="all, delete-orphan"` on `Customer.fields` / `Field.locations` deleted children *before* `_safe_delete` could refuse | **Fixed** |
| 9 | high | **Equipment accepted an impossible Customer/Field/Location combination** (silent corruption) | Pick Customer A + a Field of Customer B, or a Location of another Field → Save | No consistency validation | **Fixed** |
| 10 | high | **Services out-of-range numbers → HTTP 500** (`DataError 1264`) | `frequency_weeks=99999999999` or `estimated_hours=1e400` | Numeric input only loosely coerced | **Fixed** |
| 11 | medium | **Every empty-selection / empty-required submission returned raw JSON 422** — “Schedule selected”, “Delete selected”, “Close out selected”, “Add to PM” with nothing ticked; empty Customer/Field/Location/Service selects; blank login/account/users fields; `?edit=abc`; `/setup/customers/abc/delete` | Click those buttons with no checkbox ticked | `list[int] = Form(...)` / `int = Form(...)` / `str = Form(...)` made FastAPI reject before the handlers' friendly `if not …` guards could run (the guards were dead code) | **Fixed** |
| 12 | medium | **Final Plan print silently dropped Schedule date / Vendor / Technician / Work order** | Final Plan → Print final plan | `print_final()` never passed `scheduled`; the template gates those columns on `{% if scheduled %}` | **Fixed** |
| 13 | medium | **PDF link dropped the active filters** | Draft Plan → Filter → Print draft plan → Download PDF | PDF link used `request.url.path`, discarding the query string | **Fixed** |
| 14 | medium | **Cancelled work was unreachable** — `Plan.CANCELLED` had no writer anywhere, yet History says “Completed and cancelled service records”; no way to un-schedule a mistakenly scheduled item | — | Feature never wired up | **Fixed** (new “Cancel selected” action on Final Plan) |
| 15 | medium | **Raw JSON 403/404/405 pages** for non-admin `/users`, unknown URLs, missing report ids, `GET` on a delete URL | Open `/users` as a non-admin; open `/nope` | The HTTP-exception handler returned `JSONResponse` for every non-401 status | **Fixed** (styled `error.html`) |
| 16 | medium | **Duplicate draft rows for the same equipment + service** could be created and then scheduled into two work orders | Add the same equipment+service twice | No duplicate check | **Fixed** (skipped + reported in the flash) |
| 17 | medium | **Invalid dates were silently replaced** with today/the computed date while flashing success | `schedule_date=garbage`, `actual_date=31/12/2026`, bad `proposed_date_override` | Lenient date parsing fell back to a default | **Fixed** (validation flash) |
| 18 | medium | **Work order / calibration report rendered for un-scheduled plans** as “Work Order None” | Open `/reports/work-order/<draft id>` | No status guard | **Fixed** (clean 404) |
| 19 | medium | **Negative service frequency accepted** (scheduling ran backwards) | `frequency_weeks=-21` | No range check | **Fixed** (1–520) |
| 20 | medium | **“Save changes” with a stale id was a silent no-op** with no message (all 7 tabs + reset-password) | POST an edit with a deleted row's id | `if obj:` with no `else` | **Fixed** (“… not found” flash) |
| 21 | low | **Unhandled 500s returned plain text** and bypassed the styled error page | — | No handler for `Exception` | **Fixed** |
| 22 | low | **Open-redirect / attacker-chosen landing page** via a forged `Referer` on delete and on validation errors | `Referer: https://evil.example/phish` | Referer used verbatim | **Fixed** (same-host only) |
| 23 | low | **Invalid filter dates silently showed unfiltered rows** as if filtered | `/history?from=not-a-date` | Lenient parsing, no feedback | **Fixed** (flash notice) |
| 24 | low | **Bogus `equipment_id` on Add-to-PM was silently skipped** while the flash said “Added 0 item(s)” | — | Silent `continue` | **Fixed** (skipped count in the flash) |
| 25 | low | **`/favicon.ico` 404**, and `/account` had no active-nav highlight | — | Missing asset / missing class | **Fixed** (`/static/favicon.svg`, nav class) |
| 26 | low | **Authenticated `GET /login` still rendered the sign-in form** | — | No session check | **Fixed** (redirect to `/`) |
| 27 | high | **A password longer than 72 bytes → HTTP 500** on Add user, Reset password and Change password | Paste a 100-character password into any of those forms | bcrypt 4.x raises `ValueError: password cannot be longer than 72 bytes`; nothing validated byte length | **Fixed** (found by the Lead while probing the error-page work; friendly "72 bytes or fewer" flash) |

### 1b. Defects found by the post-fix verification pass (all fixed and re-verified)

| # | Sev | Defect | Repro | Root cause | Status |
|---|---|---|---|---|---|
| 28 | medium | **`GET /setup/personnel?edit=abc` still returned a 422** while the other six Setup tabs were tolerated | Open `/setup/personnel?edit=abc` | The first pass missed this seventh handler | **Fixed** |
| 29 | low | **The wrong-credentials page had no way back home** | Log in with a wrong password | `login.html` lacked a Home link | **Fixed** |
| 30 | low | **A delete POST without a `Referer` redirected to `/setup`, which is not a route** (landed on a 404) | POST any `…/delete` with no Referer header | `_safe_delete` fallback was a non-existent path | **Fixed** (falls back to the entity's own tab) |
| 31 | low | **Deleting or toggling a row that no longer exists was a silent 303** with no message | POST `/setup/services/424242/delete`, `/users/424242/toggle` | `if obj is None:` with no flash | **Fixed** ("not found" flash) |
| 32 | low | **A single crafted request repeating the same equipment id created duplicate draft rows** | `POST /planning/draft/add` with `equipment_ids=43&equipment_ids=43` | The duplicate snapshot was taken before the insert loop | **Fixed** (id marked as open inside the loop) |

Full per-finding detail (steps, exact evidence file, suspected line) is in
`.qa/findings_setup.md`, `.qa/findings_planning.md`, `.qa/findings_auth_reports.md`,
`.qa/findings_contract.md`.

## 2. What was verified working (no defect)

* Full planning loop end-to-end, tab transitions, and the scheduling rule
  `last_completed + frequency_weeks = proposed_date`
  (2026-10-01 + 26 weeks = 2027-04-01; after a completion on 2026-10-06 the next draft
  correctly used 2027-04-06), plus deterministic `WO-000n` / `CM-000n` numbering.
* Dashboard counters and the “due soon (30 days)” window match the DB.
* History filters (customer / completed-from / completed-to) and double-submit safety.
* Add / edit-prefill / save / delete DB round-trips on all 7 Setup tabs; all 75 links on
  those tabs resolve; dependency refusal works when Equipment blocks a delete; names are
  HTML-escaped.
* Login (wrong password → friendly 401 page, deactivated user blocked), logout, account
  password change (wrong current / too short / mismatch / success), user create, duplicate
  and short-password handling, disable/enable, admin self-protection.
* All four report surfaces in HTML **and** as real PDFs via WeasyPrint
  (`%PDF-` bytes, correct attachment filenames); static CSS/JS 200; no path traversal.

## 3. Known gaps deliberately not changed

* **No CSRF tokens** anywhere (mitigated by `SameSite=Lax` cookies). A production
  hardening item, not a regression.
* **Setup CRUD is available to `role=user`** (`current_user`, not `require_admin`); the
  navigation shows Setup to everyone, so this looks intentional.
* **Changing your password does not invalidate other sessions** (sessions hold only
  `uid`).
* `/favicon.ico` itself still 404s; pages declare `/static/favicon.svg`, which browsers use.
* Invalid date filters on the *print* endpoints are ignored without a notice (the flash
  cannot be shown on a printable document).
* The Equipment form lists every Field and Location rather than filtering them by the
  selected Customer. Mismatched combinations are now rejected with a clear message, but the
  dropdowns are not yet dynamically filtered.

---

## 4. Fixes applied

All changes are in `pmsys/app/` plus 32 new regression tests in
`pmsys/tests/test_regressions.py`. `python -m pytest` → **43 passed**.

| Fix | Files |
|---|---|
| Auto-assign shadowing: import aliased as `auto_assign_personnel` | `app/routers/planning.py` |
| FK validation for vendor/personnel on schedule + closeout; strict date parsing; duplicate draft suppression; skipped-count flash; new `POST /planning/cancel` | `app/routers/planning.py` |
| Customer/Field/Location chain validation, column-length limits, duplicate checks on UPDATE, `Form("")` for optional/blankable params, tolerant `?edit=`, "not found" flashes, numeric range checks, safe delete redirect | `app/routers/setup.py` |
| `scheduled` flag for the final print; 404 for un-scheduled report requests | `app/routers/reports.py` |
| Username/display-name length limits, "User not found" flash, authenticated `/login` redirect, 72-byte password guard | `app/routers/auth.py`, `app/auth.py` |
| Invalid filter-date notices; tolerant `?customer_id=` | `app/routers/history.py` |
| `error.html` page; handlers for `HTTPException`, `RequestValidationError` and unhandled `Exception`; no more JSON error bodies | `app/main.py`, `app/templates/error.html` |
| No implicit child deletion on customer/field delete | `app/models.py` |
| `safe_back()` same-host referer handling (shared) | `app/templating.py` |
| Length/max guards in all Setup forms, required Location select, final-plan Cancel button, PDF links keep filters, Account nav highlight, favicon | `app/templates/**`, `app/static/favicon.svg` |

## 5. Verification

* `pytest` (SQLite, in-process): **51 passed** — including one regression test per defect
  above (auto-assign success + no-technician flash, FK/date validation, cascade refusal,
  checkbox persistence, duplicate skip, cancel→history, HTML error pages, cross-site
  referer rejection, 500 page, 72-byte password guard, stale `?edit=`, missing-row flashes).
* **Independent verification 1 — write-flow falsification** (fresh subagent, live port 8000):
  **FIXED 12 / STILL BROKEN 1 / REGRESSION 0**. The single counterexample was a crafted
  request repeating the same `equipment_ids` value, which bypassed the duplicate snapshot;
  fixed and re-verified.
* **Independent verification 2 — broad regression sweep** (fresh subagent): **292 requests,
  52 scored checks, 45 PASS / 7 BUG, and 0 raw-JSON error bodies**. Its 6 findings
  (bcrypt >72-byte 500, `/history?customer_id=` 422, `/setup/personnel?edit=` 422, missing
  Home link on the 401 page, no-Referer delete landing on `/setup`, silent missing-row
  delete/toggle) were all fixed and rebuilt.
* **Lead final end-to-end run** on the fully rebuilt image: **19/19 live checks pass**,
  `docker logs` shows **0 tracebacks / 0 HTTP 500s**, and the database is back to its seeded
  baseline with no test rows. Full detail: `.qa/verify_live.md`, with per-tester evidence in
  `.qa/findings_*.md`, `.qa/verify_*.md` and `.qa/evidence/`.

The image in `docker compose` (`pmsys-app:latest`) and the container on port 8000 now match
the working tree (md5-verified for every changed file).
