# QA findings — independent regression verification (V-REGR)

Generated against http://127.0.0.1:8000 · container `pmsys-app-1` · DB `pmsys-db-1`
Container image built **2026-10-01 17:10:01 +05:00**, container started **17:10:28**.
Verifier: read-only sweep; all created rows prefixed `QA-REGR-` and removed afterwards.

Every request made by this sweep returned a **non-JSON** body; **0 raw-JSON
responses** were observed (see `coverage_verify_regression.md`).

## Headline: the running container predates three source edits

`docker exec pmsys-app-1` differs from the working tree for exactly three files,
all modified **after** the image was built:

| file | local mtime | in image? | effect |
|---|---|---|---|
| `app/auth.py` | 17:11:20 | no | `password_too_long()` helper absent |
| `app/routers/auth.py` | 17:11:24 | no | bcrypt >72-byte guard absent → **HTTP 500** |
| `app/routers/history.py` | 17:11:59 | no | `?customer_id=` tolerance absent → **HTTP 422** |

The two live bugs below (V-REGR-001, V-REGR-002) are the user-visible symptom of
that gap: the fixes exist in source but are **not deployed**. A rebuild/redeploy
of `pmsys-app-1` is required before those two can be re-verified green.

## V-REGR-001: Live app still 500s on a password longer than 72 bytes (fix present in source, not deployed)
- **Severity:** high
- **Area:** auth/deployment
- **Status:** confirmed
- **Action:** `POST /users · POST /users/{id}/reset-password · POST /account/password with a >72-byte password`
- **Steps:**
1. Log in as admin/admin.
2. POST /users with username=QA-REGR-u-longpw, password='p'*100, role=user → HTTP 500.
3. POST /users/7/reset-password with password='q'*100 → HTTP 500.
4. Logged in as a normal user, POST /account/password with a correct current password and a 100-byte new password → HTTP 500.
- **Expected:** 303 redirect with a friendly flash ('Password must be 72 bytes or fewer.'); the record must not be written.
- **Actual:** HTTP 500 with the styled error page. Server traceback ends: `ValueError: password cannot be longer than 72 bytes, truncate manually if necessary (e.g. my_password[:72])` at `app/auth.py`, `return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())`. 5 occurrences in the log window (2 of them at 12:11:13Z from another session), all the same ValueError.
- **Evidence:** .qa/evidence/regr_500_longpw_traceback.txt, regr_500_page.html, regr_create_long_pw.html, regr_reset_long_pw.html, regr_account_long_pw.html
- **Suspected cause:** The running image does not contain the working-tree fix. `app/auth.py` (local mtime 17:11:20, adds `password_too_long`) and `app/routers/auth.py` (17:11:24, guards create/reset/change) are NEWER than the image build (17:10:01); `docker exec pmsys-app-1 cat /app/app/auth.py` has no `password_too_long`. Rebuild/redeploy `pmsys-app-1`, then re-test.

## V-REGR-002: Live /history?customer_id=abc returns 422 (tolerance fix present in source, not deployed)
- **Severity:** medium
- **Area:** history/deployment
- **Status:** confirmed
- **Action:** `GET /history?customer_id=abc  ·  GET /history?customer_id=`
- **Steps:**
1. Log in as admin/admin.
2. GET /history?customer_id=abc → HTTP 422.
3. GET /history?customer_id= (empty value) → HTTP 422.
- **Expected:** HTTP 200: the route tolerates a stale/garbage `?customer_id=` and falls back to 'all customers'.
- **Actual:** HTTP 422 with the styled error page ('The link you followed contained an invalid value.'). It is HTML, not JSON, so the form-submission contract holds — but the page is still broken for a stale filter link. `/history?from=bad&to=bad` on the same page correctly returns 200 and flashes a warning, so the date half of the same tolerance fix IS working.
- **Evidence:** .qa/evidence/regr_form_GET_history_customer_id_abc.html, regr_form_GET_history_customer_id_.html
- **Suspected cause:** Same undeployed-fix gap as V-REGR-001: `app/routers/history.py` (local mtime 17:11:59) changes the signature to `customer_id: str = ""` and adds a try/int() guard; `docker exec pmsys-app-1 sed -n 23,30p /app/app/routers/history.py` still shows `customer_id: int = 0`. Rebuild/redeploy, then re-test.

## V-REGR-003: /setup/personnel?edit=abc returns 422 while the other six Setup tabs return 200
- **Severity:** medium
- **Area:** setup
- **Status:** confirmed
- **Action:** `GET /setup/personnel?edit=abc  ·  GET /setup/personnel?edit=`
- **Steps:**
1. Log in as admin/admin.
2. GET /setup/personnel?edit=abc → HTTP 422.
3. GET /setup/personnel?edit= → HTTP 422.
4. GET /setup/customers?edit=abc, /setup/fields?edit=abc, /setup/locations?edit=abc, /setup/equipment?edit=abc, /setup/services?edit=abc, /setup/vendors?edit=abc (and `?edit=`) → all HTTP 200.
- **Expected:** 200, consistent with the stale-`?edit=` tolerance deliberately added to the other six tabs.
- **Actual:** 422 for the Technicians tab only. A bookmarked/stale `?edit=` link to the Technicians tab dead-ends on the error page instead of rendering the list.
- **Evidence:** .qa/evidence/regr_edit_bad__setup_personnel_edit_abc.html, regr_edit_bad__setup_personnel_edit_.html
- **Suspected cause:** Incomplete fix: `app/routers/setup.py` defines `_edit_id()` with the docstring 'Tolerate a stale/garbage ?edit= value instead of returning a 422' and uses `edit: str = ""` + `_edit_id(edit)` for customers(96), fields(155), locations(212), equipment(269), services(391) and vendors(477) — but personnel(546) still declares `edit: int = 0` and uses `edit` directly. This is present in the running image AND in the working tree, so a rebuild alone will not fix it; `app/routers/setup.py:546` needs the same treatment.

## V-REGR-004: The 401 bad-credentials error page has no Home link
- **Severity:** low
- **Area:** error-pages
- **Status:** confirmed
- **Action:** `POST /login with username=admin, password=wrong (logged out)`
- **Steps:**
1. Log out / use a fresh client.
2. POST /login with wrong credentials → HTTP 401 text/html.
3. Search the body for an `<a href="/">` Home link → none.
- **Expected:** Every error page carries a working Home link (the requirement verified green for 403/404/405/422/500).
- **Actual:** The 401 response renders `login.html`, which has no Home link (only the login form). The friendly message 'Invalid username or password.' is present, so it is not a JSON leak — only the Home link is missing. All other error pages (403, 404, 405, 422, 500) do contain a Home link that returns 200.
- **Evidence:** .qa/evidence/regr_401_login_page.html, regr_login_wrong_pw_401.html, regr_login_blank_401.html, regr_login_missing_pw_401.html
- **Suspected cause:** `app/routers/auth.py` login renders `login.html` for 401; `app/templates/login.html` has no Home anchor (only `error.html` does).

## V-REGR-005: Setup delete falls back to a non-existent /setup redirect target
- **Severity:** low
- **Area:** setup/dead-link
- **Status:** confirmed
- **Action:** `POST /setup/{customers|fields|locations|equipment|services|vendors|personnel}/{id}/delete with no Referer header`
- **Steps:**
1. Log in as admin/admin.
2. POST /setup/customers/<own row id>/delete with httpx (no Referer header) → 303 Location: /setup.
3. Follow the redirect: GET /setup → HTTP 404.
- **Expected:** The post-delete redirect should land on a real page (the tab the user came from), or at worst a 200 page.
- **Actual:** `_safe_delete` calls `safe_back(request, "/setup")`; with no Referer it returns the default `/setup`, which is **not a registered route** → the user lands on a 404. Reproduced for all 7 setup entities (7/7). In a normal browser the same-origin Referer is sent, so this is latent rather than routine — but it is a dead redirect target and any `Referrer-Policy: no-referrer` client hits it.
- **Evidence:** .qa/evidence/regr_form_delete_own_customers_id_15.html (0-byte 303), regr_form_delete_own_equipment_id_38.html; GET /setup → 404 (regr_unknown_url_404.html shows the 404 shape)
- **Suspected cause:** `app/routers/setup.py:90` — `return RedirectResponse(safe_back(request, "/setup"), status_code=303)`; the fallback string `/setup` is not a route (the tabs are `/setup/customers` etc.).

## V-REGR-006: Delete/toggle of a non-existent id redirects silently with no flash
- **Severity:** low
- **Area:** setup/users
- **Status:** confirmed
- **Action:** `POST /setup/customers/999999/delete · POST /users/999999/toggle`
- **Steps:**
1. Log in as admin/admin.
2. POST /setup/customers/999999/delete → 303 → /setup/customers with no flash message.
3. POST /setup/{fields,locations,equipment,services,vendors,personnel}/999999/delete → same (7/7).
4. POST /users/999999/toggle → 303 → /users with no flash message.
5. Contrast: POST /users/999999/reset-password correctly flashes 'User not found.'
- **Expected:** Some feedback, e.g. 'That record no longer exists.' — as the sibling reset-password route does.
- **Actual:** Silent 303 with no flash. Nothing is deleted or changed (correct), but the user sees the page reload with no explanation. This is a 'flash that never appears'.
- **Evidence:** .qa/evidence/regr_form_nonexistent_delete_setup_customers_999999_delete.html, regr_form_nonexistent_toggle_users_999999_toggle.html
- **Suspected cause:** The delete routes and `users_toggle` `return RedirectResponse(...)` without calling `flash()` when `db.get(...)` is None (`app/routers/setup.py` delete handlers, `app/routers/auth.py:119` toggle).

---

## What passed (prose summary)

**1. Page crawl — 98 URLs, all clean.** A BFS from `/` following every `<a href>`
reached 98 distinct URLs: Home, all 7 Setup tabs (plus every `?edit=<id>` link on
them), Draft Plan, Final Plan, History, Users, Account, the draft/final print
pages, `/planning/draft/print?format=pdf`, `/planning/final/print?format=pdf`,
the five scheduled work-order and five calibration reports (and their
`?format=pdf` variants) that the concurrent verifier's plans exposed, plus
`/static/css/app.css`, `/static/js/htmx.min.js` and `/static/favicon.svg`.
Every one returned **200 or 303**; there were **no 404/405/500** and **no Jinja
error markers** (`{{`, `Undefined`, `Traceback`) in any body. No dead link found.

**2. Forms — every button on the main pages.** Form inventory was taken with
`q.forms()` on Home, Account, Users, History, Draft, Final and all 7 Setup tabs
(19 forms + 32 row-level delete/toggle forms). 14 create/action forms were
submitted **empty** — all 14 landed on a 303 with a human-readable flash
(e.g. "Field name and customer are required.", "Please choose a service."),
never JSON. Delete and toggle routes were exercised with non-existent
(`/setup/customers/999999/delete`, `/users/999999/toggle`) and non-numeric
(`/setup/customers/abc/delete`) ids: all 303 HTML, never JSON, never a 500.
Seeded delete forms (customers 1, equipment 1–5, …) were **not** pressed.

**3. Create/read/update/delete round-trip.** For all 7 Setup entities a
`QA-REGR-…` row was created with distinctive values, confirmed on the list page,
opened with `?edit=<id>` (every field, including `<select>` options, pre-filled
with the stored value — no silent input loss), updated through the same form,
and deleted through its own delete button. 44/44 checks passed. No row was
silently discarded.

**4. Error surfaces.** `GET /login` while logged in → 303 `/`. Logged out,
`GET /planning/draft` → 303 `/login` (and `GET /` → 303 `/login`). Wrong
credentials → **401 HTML** with "Invalid username or password."; blank POST and
missing-password POST → **401 HTML**, not JSON. `/nope` → **404 HTML**;
`GET /logout` → **405 HTML**; `/reports/work-order/nope` and
`/reports/calibration/nope` → **422 HTML**; all carry a working Home link that
returns 200. `/setup/customers?edit=abc`, `?edit=`, and the same for fields,
locations, equipment, services and vendors all → **200**. Static assets return
200 with the right content types.

**5. Reports unchanged.** `/planning/draft/print`, `/planning/final/print`,
`/reports/work-order/17` and `/reports/calibration/17` → 200 with plausible
content, no `None`, no `{{`. Every `?format=pdf` variant returned
`application/pdf` **with `%PDF-` magic bytes** (WeasyPrint is working — no HTML
fallback). The Final Plan print contains the Schedule date / Work order /
Vendor / Technician columns. The "Download PDF" link on a filtered draft print
keeps `from`/`to`:
`/planning/draft/print?from=2026-01-01&to=2027-01-01&format=pdf`. Requesting a
work order for an unscheduled draft → clean HTML 404 (not 500/JSON).

**6. Auth flows.** A normal `QA-REGR-user-auth` user was created and logged in:
`GET /users` → **403 HTML with a Home link** (the previously-JSON 403 is fixed
live), `POST /users` → 403 HTML, Home/Account/Draft still render. Wrong current
password on `/account/password` flashes "Current password is incorrect." and the
admin password is unchanged — `admin`/`admin` still logs in and the rejected new
password does **not**. Short password, mismatched confirm and duplicate username
all flash friendly messages.

**7. Navigation.** The nav marks the right tab active on Home, each of the 7
Setup tabs, Draft, Final, History, Users and Account (13/13). The Setup dropdown
contains all 7 tabs. A non-admin's nav hides Users but keeps Setup.

### Observations (not scored as regressions)

* **Non-admin users can use Setup.** `app/routers/setup.py` uses
  `Depends(current_user)` 22 times and `require_admin` 0 times, so any
  authenticated user can CRUD customers/equipment/services/vendors/technicians
  (verified: non-admin `GET /setup/customers` → 200 and an empty non-admin
  `POST /setup/customers` → 303). This is identical in the running image and the
  working tree, so it is **pre-existing design, not new breakage** — but it is a
  privilege gap worth a product decision, because the nav is the only thing
  hiding Setup from normal users.
* **Delete of a non-existent id is silent** (303, no flash) — see V-REGR-006.
