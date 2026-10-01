# QA coverage — authentication, account, user admin, reports, static/routing

Target: **http://127.0.0.1:8000** (live container `pmsys-app-1`; not rebuilt/restarted).
Result ∈ PASS / BUG / GAP / BLOCKED. Every BUG row names its finding id in
[`findings_auth_reports.md`](findings_auth_reports.md).

> **Deployment caveat:** the container is stale vs the working tree (see the note at the
> top of the findings file). F-AUTH-001/002/006 and F-REPORT-001/002/003 are *already fixed
> on disk*; F-AUTH-003/004/005 and F-REPORT-004 still exist in the tree.

**Totals: 90 checks — 61 PASS / 24 BUG / 4 GAP / 1 BLOCKED.**
24 BUG rows map to 10 distinct findings (6 auth, 4 reports); 5 findings are live-only
(already fixed on disk), 4 are still present in the working tree, and F-AUTH-006 is fixed
on disk only as a side effect of the new error-page handler (still no favicon asset).

| # | check | action | result | note |
|---|---|---|---|---|
| 1 | wrong password rejected with friendly page | `POST /login` admin/wrong | PASS | 401 + `login.html` with "Invalid username or password." (not JSON) |
| 2 | blank username+password | `POST /login` `username=&password=` | BUG | **F-AUTH-001** — 422 raw JSON `{"detail":[{"type":"missing"...}]}` |
| 3 | omitted password field | `POST /login` `username=admin` | BUG | **F-AUTH-001** — 422 raw JSON |
| 4 | no fields at all | `POST /login` `{}` | BUG | **F-AUTH-001** — 422 raw JSON |
| 5 | nonexistent username | `POST /login` `QA-AUTH-nobody` | PASS | 401 + friendly page |
| 6 | over-long password (bcrypt 72-byte limit) | `POST /login` pw 73 / 500 chars | PASS | 401, no 500 — `verify_password` swallows `ValueError` |
| 7 | over-long username on login | `POST /login` username 500 chars | PASS | 401, no 500 |
| 8 | deactivated user cannot log in | toggle off → `POST /login` | PASS | 401 friendly page; `is_active` honoured |
| 9 | reactivated user can log in again | toggle on → `POST /login` | PASS | 303 → `/` |
| 10 | logout clears the session | `POST /logout` then `GET /` | PASS | 303 → `/login`; cookie jar empty afterwards |
| 11 | session survives normal navigation | `GET /` `/setup/equipment` `/account` | PASS | all 200 on one client |
| 12 | session cookie flags | inspect `Set-Cookie` | PASS | `httponly; samesite=lax; Max-Age=1209600` (`secure` off — plain HTTP dev) |
| 13 | login page renders unauthenticated | `GET /login` | PASS | 200 HTML, form present |
| 14 | unauth `/setup/equipment` | `GET` no session | PASS | 303 → `/login` |
| 15 | unauth `/planning/draft` | `GET` no session | PASS | 303 → `/login` |
| 16 | unauth `/account` | `GET` no session | PASS | 303 → `/login` |
| 17 | unauth `/users` | `GET` no session | PASS | 303 → `/login` |
| 18 | unauth `/`, `/planning/final/print`, `/reports/work-order/1` | `GET` no session | PASS | all 303 → `/login` |
| 19 | already-authenticated `GET /login` | `GET` with session | GAP | renders the sign-in form instead of redirecting to `/`; not raised as a finding (harmless) |
| 20 | deactivation kills a live session | deactivate user, reuse its session | PASS | 303 → `/login` on `/` and `/account` |
| 21 | users list | `GET /users` admin | PASS | 200, table of accounts |
| 22 | create account | `POST /users` `QA-AUTH-user-1` | PASS | 303 + flash "User 'QA-AUTH-user-1' created."; row present in DB |
| 23 | duplicate username | `POST /users` same name again | PASS | flash "Username ... already exists." |
| 24 | short password on create | `POST /users` pw `12345` | PASS | flash "Password must be at least 6 characters."; no row created |
| 25 | blank username on create | `POST /users` `username=` | BUG | **F-AUTH-001** — 422 raw JSON (the app's `if not username` guard is unreachable for `''`) |
| 26 | whitespace-only username | `POST /users` `username='   '` | PASS | flash "Username is required." |
| 27 | toggle user inactive | `POST /users/2/toggle` | PASS | `is_active=0` confirmed via `q.db` |
| 28 | toggle back active | `POST /users/2/toggle` | PASS | `is_active=1`; login works |
| 29 | reset password short | `POST /users/2/reset-password` `123` | PASS | flash "Password must be at least 6 characters." |
| 30 | reset password valid | `POST /users/2/reset-password` | PASS | flash success; old pw 401, new pw 303 |
| 31 | reset password nonexistent id | `POST /users/999999/reset-password` | BUG | **F-AUTH-004** — 303 with no flash at all (silent no-op) |
| 32 | toggle own admin id | `POST /users/1/toggle` | PASS | no-op; admin `is_active=1`, `role=admin`, still logged in and can re-login |
| 33 | toggle nonexistent id | `POST /users/999999/toggle` | PASS | harmless 303 no-op |
| 34 | role value coercion | `POST /users` `role=superadmin` | PASS | stored as `user` |
| 35 | over-long username on create | `POST /users` username 99 chars | BUG | **F-AUTH-003** — HTTP 500, `DataError ... 'username'` |
| 36 | over-long display name on create | `POST /users` display_name 200–300 chars | BUG | **F-AUTH-003** — HTTP 500, `DataError ... 'display_name'` |
| 37 | GET on POST-only user route | `GET /users/2/toggle` | BUG | **F-AUTH-002** — 405 raw JSON `{"detail":"Method Not Allowed"}` |
| 38 | non-admin `GET /users` | login role=user, `GET /users` | BUG | **F-AUTH-002** — 403 raw JSON `{"detail":"Admin access required"}` |
| 39 | non-admin `POST /users` | role=user, create admin | BUG | **F-AUTH-002** — 403 raw JSON; user **not** created (verified in DB) |
| 40 | non-admin toggle / reset-password | `POST /users/1/toggle`, `/users/1/reset-password` | BUG | **F-AUTH-002** — 403 raw JSON; admin untouched |
| 41 | nav hides Users for non-admin | `GET /` as role=user | PASS | no `href="/users"`; admin's page does contain it |
| 42 | non-admin reaches other areas by URL | `/setup/*`, `/planning/*`, `/history`, `/account` | PASS | all 200; only `/users` is admin-gated |
| 43 | setup CRUD open to role=user | code + URL check | GAP | `app/routers/setup.py` uses `current_user`, not `require_admin`, so any logged-in user can edit reference data; appears intentional (nav shows Setup to all) — noted, not filed |
| 44 | admin account intact after non-admin attempts | `q.db` + `POST /login` admin/admin | PASS | `is_active=1`, `role=admin`, login 303 |
| 45 | account page shows identity | `GET /account` as test user | PASS | 200, username rendered, no Jinja leftovers |
| 46 | wrong current password | `POST /account/password` | PASS | flash "Current password is incorrect." |
| 47 | new password too short | `POST /account/password` | PASS | flash "New password must be at least 6 characters." |
| 48 | confirm mismatch | `POST /account/password` | PASS | flash "New passwords do not match." |
| 49 | failed changes leave password intact | `POST /login` with old pw | PASS | still 303 |
| 50 | successful password change | `POST /account/password` | PASS | flash "Password updated."; old 401, new 303 |
| 51 | blank account-password fields | `POST /account/password` `{}` | BUG | **F-AUTH-001** — 422 raw JSON |
| 52 | admin password untouched by all of the above | `POST /login` admin/admin | PASS | admin/admin still 303 at the end of the run |
| 53 | account page nav highlight | `GET /account` | BUG | **F-AUTH-005** — no `class="active"` anywhere |
| 54 | session invalidation of other sessions on password change | not exercised | GAP | sessions key on `uid` only, so a change/reset does not log other sessions out; not tested (would need a second live session) |
| 55 | CSRF protection on state-changing POSTs | code + form inspection | GAP | no CSRF token in any form; relies on `SameSite=Lax` (mitigates cross-site POST but not same-site XSS); not filed |
| 56 | work order HTML for a scheduled plan | `GET /reports/work-order/6` | PASS | 200, 4455 B, WO-0006 present, no `{{`/Undefined |
| 57 | calibration HTML for a scheduled plan | `GET /reports/calibration/6` | PASS | 200, 4329 B, CM-0006 present, no `{{`/Undefined |
| 58 | work order for a draft (wo_no NULL) | `GET /reports/work-order/1` | BUG | **F-REPORT-003** — 200, `<title>Work Order None</title>`, literal "None" printed |
| 59 | nonexistent plan id (work order) | `GET /reports/work-order/999999` | BUG | **F-REPORT-002** — 404 raw JSON `{"detail":"Work order not found"}` |
| 60 | nonexistent plan id (calibration) | `GET /reports/calibration/999999` | BUG | **F-REPORT-002** — 404 raw JSON |
| 61 | non-integer plan id | `GET /reports/work-order/abc` | BUG | **F-REPORT-002** — 422 raw JSON `int_parsing` |
| 62 | work order PDF | `GET /reports/work-order/6?format=pdf` | PASS | 200 `application/pdf`, 14533 B, `%PDF-` magic, attachment filename |
| 63 | calibration PDF | `GET /reports/calibration/6?format=pdf` | PASS | 200 `application/pdf`, 13814 B, `%PDF-` |
| 64 | draft plan print HTML | `GET /planning/draft/print` | PASS | 200, all draft plans, no placeholders |
| 65 | draft plan print PDF | `GET /planning/draft/print?format=pdf` | PASS | 200 `application/pdf`, 14976 B, `%PDF-` |
| 66 | final plan print HTML | `GET /planning/final/print` | BUG | **F-REPORT-001** — scheduled-only columns absent; contains no `WO-` |
| 67 | final plan print PDF | `GET /planning/final/print?format=pdf` | BUG | **F-REPORT-001** — valid 11078 B PDF, but same missing columns |
| 68 | draft print `from` filter | `?from=2029-01-01` | PASS | 200, 0 rows (vs 11 unfiltered) |
| 69 | draft print `to` filter | `?to=2026-12-31` | PASS | 200, 1 row |
| 70 | draft print invalid dates | `?from=not-a-date&to=also-bad` | PASS | 200, filters ignored gracefully (no 500) |
| 71 | PDF link keeps active filters | read href on filtered draft print | BUG | **F-REPORT-004** — href is `/planning/draft/print?format=pdf`, drops `from`/`to` |
| 72 | PDF fallback path (`pdf_unavailable`) | force WeasyPrint failure | BLOCKED | WeasyPrint 70.0 + system libs are installed in the image, so every `?format=pdf` produced a real PDF; the HTML-fallback branch was never reachable |
| 73 | app stylesheet | `GET /static/css/app.css` | PASS | 200 `text/css`, 8774 B |
| 74 | htmx bundle | `GET /static/js/htmx.min.js` | PASS | 200 `text/javascript`, 48101 B |
| 75 | favicon | `GET /favicon.ico` | BUG | **F-AUTH-006** — 404 `application/json`, no asset |
| 76 | missing static asset | `GET /static/nope.css` | BUG | **F-AUTH-006** (same class) — 404 raw JSON |
| 77 | static path traversal | `GET /static/js/htmx.min.js/../../app/main.py` | PASS | 404, no source leak |
| 78 | unknown URL | `GET /totally-unknown`, `/admin`, `/api`, `/users/1`, `/setup/nope`, `/planning/nope` | BUG | **F-AUTH-002** — all 404 raw JSON `{"detail":"Not Found"}` instead of an HTML page |
| 79 | `/static` mount root | `GET /static` | PASS | 307 → `/static/` (StaticFiles behaviour) |
| 80 | nav link Home | `GET /` | PASS | 200 |
| 81 | nav links — 7 Setup tabs | customers, fields, locations, equipment, services, vendors, personnel | PASS | all 200 |
| 82 | nav link Draft Plan | `GET /planning/draft` | PASS | 200 |
| 83 | nav link Final Plan | `GET /planning/final` | PASS | 200 |
| 84 | nav link History | `GET /history` | PASS | 200 |
| 85 | nav link Users (admin) | `GET /users` | PASS | 200 |
| 86 | nav link Account | `GET /account` | PASS | 200 |
| 87 | nav action Log out | `POST /logout` | PASS | 303 → `/login` |
| 88 | nav highlighting matches tab | `/`, `/setup/customers`, `/setup/equipment`, `/planning/draft`, `/planning/final`, `/history`, `/users` | PASS | exactly the expected anchor has `class="active"` |
| 89 | nav highlighting on Account | `GET /account` | BUG | **F-AUTH-005** — no active item |
| 90 | data hygiene — throwaway users removed | `q.db("select id,username,role,is_active from users")` | PASS | ends with exactly the original `admin` (id 1, role admin, active) |
