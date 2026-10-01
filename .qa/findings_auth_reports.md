# QA findings — authentication, account, user admin, reports, static/routing

Generated against **http://127.0.0.1:8000** (live container `pmsys-app-1`, DB `pmsys-db-1`),
admin session `admin`/`admin`, test users prefixed `QA-AUTH-`.

## ⚠️ Deployment note (read first)

The **running container is stale relative to the working tree**. The container has been
up ~25 h; `app/main.py`, `app/routers/reports.py` and `app/templates/login.html` were
modified on disk afterwards and **not deployed** (I did not rebuild/restart, per the brief):

| file | disk vs container |
|---|---|
| `app/main.py` | DIFF — tree adds an HTML `error.html` handler + `RequestValidationError` handler |
| `app/routers/reports.py` | DIFF — tree adds `"scheduled": False/True` and 404 guards for missing `wo_no`/`cm_no` |
| `app/templates/login.html` | DIFF — tree renders flashes/errors on the login card |
| `app/routers/auth.py`, `app/dependencies.py`, `base.html`, `users.html`, `account.html`, `reports/plan_print.html` | SAME |

**Consequence:** F-AUTH-001, F-AUTH-002, F-REPORT-001, F-REPORT-002, F-REPORT-003 and
F-AUTH-006 are **already addressed in the working tree** and will disappear on the next
image build. Verify against the live container only, otherwise you will "fix" fixed code.
**F-AUTH-003, F-AUTH-004, F-AUTH-005 and F-REPORT-004 still exist in the working tree.**

All results below are the behaviour of the **live container as tested**.

## F-AUTH-001: Blank form fields return FastAPI's raw 422 JSON instead of a friendly page
- **Severity:** medium
- **Area:** auth
- **Status:** confirmed
- **Action:** `POST /login with empty username/password`
- **Steps:**
1. POST /login with data {'username':'','password':''}
2. POST /login with data {'username':'admin'} (password field omitted)
3. POST /users with {'username':'', ...} and POST /account/password with {}
- **Expected:** The login page re-renders with a human-readable error (e.g. 'Username and password are required.'), or an HTML error page — never a JSON API envelope.
- **Actual:** HTTP 422, content-type application/json, body {"detail":[{"type":"missing","loc":["body","username"],"msg":"Field required","input":null}, ...]}. Same for POST /users and POST /account/password. Note the app's own empty-value guards never fire: the wire body is `username=&password=x`, yet FastAPI 0.142 treats an empty string as a MISSING field, so `if not username:` in create_user is unreachable for '' (only reachable via whitespace, which does flash correctly).
- **Evidence:** .qa/evidence/auth_login_blank_both.json, auth_login_no_fields.json, auth_login_missing_password.json, auth_account_blank_422.json
- **Suspected cause:** app/main.py:36 (no RequestValidationError handler; the only app exception handler emits JSONResponse for every non-401)

## F-AUTH-002: Non-admin hitting /users gets raw JSON 403 (no HTML error page); same handler leaks raw JSON 404/405
- **Severity:** medium
- **Area:** auth
- **Status:** confirmed
- **Action:** `GET and POST /users, POST /users/1/toggle, POST /users/1/reset-password as a role=user account`
- **Steps:**
1. Create QA-AUTH-user-1 with role=user and log in as it
2. GET /users
3. POST /users {username: QA-AUTH-should-not-exist, role: admin}
4. POST /users/1/toggle and POST /users/1/reset-password
- **Expected:** An HTML error page such as 'Not allowed — you do not have permission to open that page.', or a redirect back with a flash.
- **Actual:** HTTP 403, content-type application/json, body {"detail":"Admin access required"} for all four requests. No admin data is leaked and nothing is written (verified in DB), so this is a UX/API-shape defect, not an auth bypass. Root cause is shared: any StarletteHTTPException other than 401 is serialised as JSON, so GET /logout -> 405 {"detail":"Method Not Allowed"}, unknown URLs -> 404 {"detail":"Not Found"} and a non-integer id -> 422 JSON. The nav correctly hides 'Users' from non-admins and admin/the account stay intact.
- **Evidence:** .qa/evidence/auth_nonadmin_users_403.json, auth_nonadmin_users_post_403.json, auth_nonadmin_home_nav.html, report_unknown_404.json, report_get_logout_405.json
- **Suspected cause:** app/main.py:36 (JSONResponse fallback in the StarletteHTTPException handler)

## F-AUTH-003: POST /users with an over-long username or display name returns HTTP 500 (DataError)
- **Severity:** high
- **Area:** auth
- **Status:** confirmed — still present in the working tree (auth.py is byte-identical to the container)
- **Action:** `POST /users with username longer than 64 chars, or display_name longer than 128 chars`
- **Steps:**
1. As admin: POST /users {username: 'QA-AUTH-'+'Z'*90, display_name: 'ok', password: 'QApass123', role: 'user'}
2. As admin: POST /users {username: 'QA-AUTH-dn2', display_name: 'D'*200, password: 'QApass123', role: 'user'}
- **Expected:** A flash error telling the admin the value is too long (or a field maxlength), and no user created; at worst a friendly error page.
- **Actual:** HTTP 500 text/plain 'Internal Server Error'. Server log: `sqlalchemy.exc.DataError: (pymysql.err.DataError) (1406, "Data too long for column 'username' at row 1")` raised at `app/routers/auth.py:107  db.commit()`. The 300-char display_name likewise 500s at the same line. The create-user inputs in users.html have no maxlength and create_user performs no length validation, so an admin can trivially 500 the app.
- **Evidence:** .qa/evidence/auth_users_username_overflow_500.txt, auth_users_displayname_overflow_500.txt, auth_users_longname_error.html
- **Suspected cause:** app/routers/auth.py:107 (db.commit() with no length guard / IntegrityError-free DataError handling in create_user)

## F-AUTH-004: Reset-password for a nonexistent user id is a silent no-op
- **Severity:** low
- **Area:** auth
- **Status:** confirmed — still present in the working tree
- **Action:** `POST /users/999999/reset-password`
- **Steps:**
1. As admin: POST /users/999999/reset-password {password: 'Whatever123'}
2. Follow the 303 to /users and read the flash
3. Repeat with a too-short password
- **Expected:** A flash error such as "User not found."
- **Actual:** 303 to /users with no flash at all, in both the valid- and too-short-password cases. The handler has branches for `target and len>=6` and `elif target:` but none for `target is None`, so the admin gets no feedback that nothing happened. (POST /users/999999/toggle behaves the same but is harmless.)
- **Evidence:** .qa/evidence/auth_users_reset_missing_flash.html
- **Suspected cause:** app/routers/auth.py:131-139 (reset_password / toggle_user: no else branch for a missing target)

## F-AUTH-005: /account has no active nav highlight
- **Severity:** low
- **Area:** auth
- **Status:** confirmed — still present in the working tree
- **Action:** `GET /account`
- **Steps:**
1. GET /account and inspect the nav markup
2. Compare with /, /setup/*, /planning/draft, /planning/final, /history, /users which all set class="active"
- **Expected:** The Account tab/link is marked active, matching the current page as every other tab does.
- **Actual:** No element carries class="active"; the markup is `<a href="/account">Account</a>` with no class attribute, and it sits in .user-menu outside .app-nav. Every other nav target highlights correctly (verified for Home, all 7 setup tabs, Draft Plan, Final Plan, History, Users).
- **Evidence:** .qa/evidence/auth_account_page.html, auth_admin_home_nav.html
- **Suspected cause:** app/templates/base.html:34 (Account anchor has no active-class expression)

## F-AUTH-006: /favicon.ico is missing and 404s as JSON
- **Severity:** low
- **Area:** auth
- **Status:** confirmed
- **Action:** `GET /favicon.ico`
- **Steps:**
1. GET /favicon.ico
2. GET /static/nope.css (missing static asset)
- **Expected:** A favicon is served (200 image/x-icon), or at minimum a quiet 404.
- **Actual:** 404 application/json {"detail":"Not Found"}; there is no favicon route or asset. Browsers request it on every page load, so the tab shows the default icon and the console logs a JSON 404. /static/css/app.css (200 text/css, 8774 B) and /static/js/htmx.min.js (200 text/javascript, 48101 B) are both fine; a path-traversal probe /static/js/htmx.min.js/../../app/main.py correctly 404s.
- **Evidence:** .qa/evidence/report_static_favicon_ico.json, report_static_static_nope_css.json, report_unknown_404.json
- **Suspected cause:** app/main.py:31 (StaticFiles mount only; no /favicon.ico route or asset)

## F-REPORT-001: Final Plan print omits the Schedule date / Vendor / Technician / Work order columns
- **Severity:** medium
- **Area:** reports
- **Status:** confirmed live — already fixed in the working tree (adds "scheduled": False/True)
- **Action:** `GET /planning/final/print`
- **Steps:**
1. GET /planning/final/print and inspect <thead>
2. Grep the rendered HTML for 'Schedule date' and for the scheduled plan's work-order number (WO-0006)
- **Expected:** The Final Plan is the scheduled-plans view, so its printout should carry Schedule date, Vendor, Technician and Work order, exactly as plan_print.html intends.
- **Actual:** The thead is `<th>Equipment Tag 1</th><th>Tag 2</th><th>Service</th><th>Customer</th><th>Field</th><th>Location</th><th>Last completed</th><th>Proposed date</th>` — identical to the Draft Plan print. Body contains the 1 scheduled plan row but never the string 'WO-'; the work-order number and schedule date/vendor/technician are silently dropped from the printable final plan. The template gates them on `{% if scheduled %}` but print_final never puts `scheduled` in the context, so the Jinja variable is Undefined (falsy) and the branch is skipped.
- **Evidence:** .qa/evidence/report_final_print.html, report_draft_print.html
- **Suspected cause:** app/routers/reports.py:96-106 (print_final ctx lacks "scheduled": True, consumed by plan_print.html:24,37)

## F-REPORT-002: Report endpoints return raw JSON 404/422 instead of an HTML error page
- **Severity:** medium
- **Area:** reports
- **Status:** confirmed live — the HTML error-page part is already fixed in the working tree
- **Action:** `GET /reports/work-order/999999 and GET /reports/calibration/999999`
- **Steps:**
1. GET /reports/work-order/999999
2. GET /reports/calibration/999999
3. GET /reports/work-order/abc
- **Expected:** A clean 404 HTML page ('Not found — that page or record does not exist.') consistent with the rest of the server-rendered app.
- **Actual:** HTTP 404 application/json {"detail":"Work order not found"} / {"detail":"Calibration report not found"}; GET /reports/work-order/abc gives 422 JSON int_parsing. Same root cause as F-AUTH-002. The check itself is correct (no stack trace, no leak), only the body shape is wrong for a browser.
- **Evidence:** .qa/evidence/report_work_order_404.json, report_calibration_404.json, report_work_order_nonint.json
- **Suspected cause:** app/routers/reports.py:129,162 raising HTTPException + app/main.py:36 JSONResponse fallback

## F-REPORT-003: Work order / calibration report for an unscheduled plan prints 'None'
- **Severity:** low
- **Area:** reports
- **Status:** confirmed live — already fixed in the working tree (404 guards for missing wo_no/cm_no)
- **Action:** `GET /reports/work-order/1 (a draft plan whose wo_no/cm_no are NULL)`
- **Steps:**
1. GET /reports/work-order/1 on a draft plan (wo_no NULL)
2. Read <title> and the document header
- **Expected:** Either a 404/'not scheduled yet' message, or a blank placeholder — not the Python literal.
- **Actual:** HTTP 200 with `<title>Work Order None</title>` and the literal text 'None' in the printed header; the calibration report behaves the same for a NULL cm_no. The final-plan page only links these reports for scheduled plans, so this needs a hand-typed URL, but any plan id is accepted.
- **Evidence:** .qa/evidence/report_work_order_draft.html
- **Suspected cause:** app/routers/reports.py:109-140 (work_order/calibration accept any plan regardless of status; wo_no/cm_no are NULL until scheduling)

## F-REPORT-004: 'Download PDF' on a filtered Draft Plan drops the from/to filters
- **Severity:** medium
- **Area:** reports
- **Status:** confirmed — still present in the working tree
- **Action:** `GET /planning/draft/print?from=2026-01-01&to=2026-12-31 then follow the 'Download PDF' link`
- **Steps:**
1. GET /planning/draft/print?from=2026-01-01&to=2026-12-31 -> 1 plan row
2. Read the 'Download PDF' href in that page
3. GET that href and compare with the filtered HTML
- **Expected:** The PDF link preserves the active filter, e.g. /planning/draft/print?from=2026-01-01&to=2026-12-31&format=pdf.
- **Actual:** The href is hardcoded to `{{ request.url.path }}?format=pdf`, i.e. /planning/draft/print?format=pdf — the query string is discarded, so the downloaded PDF contains all 11 draft plans while the on-screen table shows 1. The user silently gets an unfiltered document. (HTML-only checks are otherwise OK: from=2029-01-01 -> 0 rows, to=2026-12-31 -> 1 row, and ?from=not-a-date&to=also-bad is ignored gracefully with 200.)
- **Evidence:** .qa/evidence/report_draft_print_filtered.html, report_draft_print_pdf.pdf, report_draft_print.html
- **Suspected cause:** app/templates/reports/plan_print.html:11 (href uses request.url.path, not request.url with its query string)
