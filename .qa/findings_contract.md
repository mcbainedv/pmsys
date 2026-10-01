# QA findings — contract audit

Area: `contract` · auditor: QA contract subagent · target `http://127.0.0.1:8000` (container `pmsys-app-1`).

**Revision note.** The working tree was patched (17:04–17:05) by a parallel fix
pass *after* the evidence below was captured. The container serves the
pre-17:04 image and has no source bind-mount, so every "confirmed live" item
below is real HTTP evidence for the audited revision. Where the current tree now
differs, that is stated explicitly. Already reported by the lead and **not**
re-reported as new: `/planning/schedule`, `/planning/draft/delete`,
`/planning/closeout` with no checkbox; `POST /setup/equipment` with
`location_id=0`; unchecking "Active".

## F-CONTRACT-001: Selecting no equipment and clicking "Add to PM" returns raw JSON 422

- **Severity:** high (user action broken) · **Status:** confirmed live (audited revision)
- **Area:** contract
- **Action:** `POST /planning/draft/add`
- **Steps:**
  1. Sign in and open `/planning/draft`.
  2. Choose a service but leave every equipment checkbox unticked (this is the natural state — nothing is ticked by default).
  3. Click **Add to PM**.
- **Expected:** the handler's own guard at `planning.py:117` flashes "Select at least one equipment item." and redirects to the draft list.
- **Actual:** HTTP 422 with body `{"detail":[{"type":"missing","loc":["body","equipment_ids"],"msg":"Field required","input":null}]}` — dead-end raw JSON. The guard is unreachable because `equipment_ids: list[int] = Form(...)` is resolved (and rejected) before the function body runs.
- **Evidence:** `.qa/evidence/contract_422_draft_add_no_equipment.json`
- **Suspected cause:** `app/routers/planning.py:107` (audited revision) — `equipment_ids: list[int] = Form(...)` should be `Form([])`, since an untouched checkbox group posts nothing.
- **Fix status:** current tree changed this to `Form([])` (`planning.py:107`) and added the global validation handler in `main.py:70-76`; predicted fixed, not re-verified live (container not rebuilt). Same class as the lead-confirmed trio, but this is a **fourth endpoint and a different template button** (`planning/draft.html:41`).

## F-CONTRACT-002: `POST /setup/equipment` 500s on two more bogus-FK variants (`field_id=0`, `customer_id=0`)

- **Severity:** high (HTTP 500) · **Status:** confirmed live (audited revision); instances additional to the lead-confirmed `location_id=0`
- **Area:** contract
- **Action:** `POST /setup/equipment`
- **Steps:**
  1. POST the equipment form with a valid `tag1` and `customer_id=0, field_id=1, location_id=1` → 500.
  2. POST with `customer_id=1, field_id=0, location_id=1` → 500.
  3. POST with `customer_id=1, field_id=1, location_id=0` → 500 (lead-confirmed; reproduced for evidence).
- **Expected:** a flash explaining which reference must be chosen, then redirect.
- **Actual:** `HTTP 500 Internal Server Error` (plain text) for all three; the NOT NULL FK columns reject `0` / a non-existent id at `db.commit()`.
- **Evidence:** `.qa/evidence/contract_500_equipment_customer0.txt`, `contract_500_equipment_field0.txt`, `contract_500_equipment_location0.txt` (all `HTTP 500`, body `Internal Server Error`); no partial rows were written (`select count(*) from equipment where tag1 like 'QA-CONTRACT%'` → 0)
- **Suspected cause:** `app/routers/setup.py:242-244` (audited revision) declared `customer_id`/`field_id` as `int = Form(...)` and `location_id` as `int = Form(0)` with no existence check before `db.add(Equipment(**fields))` at `setup.py:286`.
- **Fix status:** current tree validates the whole customer→field→location chain and flashes instead (`setup.py:270-283`), and marks the Location select `required` (`setup/equipment.html:28`). **This is the mechanism behind the lead's `location_id=0` finding: the Location dropdown's `— Location —` placeholder carries `value="0"`, and the template never marked the select `required`, so the placeholder was the default submission.**

## F-CONTRACT-003: Unchecking "Active" cannot deactivate a technician or a piece of equipment

- **Severity:** high (silent data corruption: the record stays active) · **Status:** confirmed live (audited revision); fix verified on current tree
- **Area:** contract
- **Action:** `POST /setup/personnel`, `POST /setup/equipment`
- **Steps:**
  1. Add a technician with the Active box unchecked (field omitted from the body) → DB shows `is_active = 1`.
  2. Edit that technician, leave Active unchecked → DB still `is_active = 1`.
  3. Same for equipment: create with the box omitted → `is_active = 1`; edit with the box omitted → still `1`.
- **Expected:** an omitted checkbox means `is_active = False`.
- **Actual:** the value is always True. `is_active: str = Form("on")` substitutes `"on"` when the field is absent, so `is_active == "on"` is always true. The "Active" checkbox is effectively write-only-true, and the UI's "Active/Inactive"/filter-by-active behaviour can never be changed from equipment/personnel CRUD.
- **Evidence:** live DB reads `personnel id=5 … is_active=1` and `equipment id=17 QA-CONTRACT-NOACTIVE is_active=1`; **current-tree verification (all four paths persist False):** `.qa/evidence/contract_verify_checkbox_current_tree.txt`
- **Suspected cause:** `app/routers/setup.py:254` and `app/routers/setup.py:432` (audited revision) — `is_active: str = Form("on")`. The template default is correct (`setup/equipment.html:44`, `setup/personnel.html:15`), so only the server default was wrong.
- **Fix status:** current tree uses `Form("")`; verified in-process on the current revision (create-False, edit-False, equipment create/edit-False, and the edit form renders the box un-checked for an inactive row). Test records were deleted afterwards.

## F-CONTRACT-004: "Success" flash for an edit of a record that does not exist (silent no-op)

- **Severity:** medium (misleading feedback) · **Status:** confirmed live at the user-reset endpoint; same code shape still present in the current tree
- **Area:** contract
- **Action:** `POST /users/{user_id}/reset-password` (and the same `if obj:` shape in Setup saves)
- **Steps:**
  1. Sign in as admin, open `/users`.
  2. POST `/users/424242/reset-password` with a 6+ character password (a stale tab, a double-submit after the row was deleted, or a replayed request all reach this).
  3. Follow the redirect to `/users`.
- **Expected:** an error flash such as "User not found."
- **Actual:** HTTP 303 with **no flash at all** for the reset endpoint (`target and len(...)` is falsy and the `elif target:` branch is skipped). For the Setup edits the inverse happens — `vendor_save`, `personnel_save`, `customer_save`, `field_save`, `location_save`, `equipment_save` and `service_save` guard with `if obj:` and, when the object is missing, fall through to `RedirectResponse` having flashed **nothing**, or (for `equipment`/`customer`) still flash `"… updated."`. So a mis-typed/edited `*_id` silently does nothing while the UI can report success.
- **Evidence:** `POST /users/424242/reset-password -> 303 /users`, flash `''` (empty); see "silent success" block in the coverage log
- **Suspected cause:** `app/routers/auth.py:131-137` and the `if obj:` branches at `app/routers/setup.py:389-395` (vendor), `449-455` (personnel), plus the same pattern in the other saves — `db.get(Model, id)` returning `None` is treated as "nothing to say".
- **Note:** `draft/delete` and `schedule` behave correctly here (they flash "Deleted 0 item(s)" / "Select at least one draft item …"), so the inconsistency is not universal.

## F-CONTRACT-005: Final Plan print silently omits the scheduled columns (missing `scheduled` context variable)

- **Severity:** medium (wrong/incomplete output on a real user flow) · **Status:** confirmed live on the audited revision (with a reversible live test)
- **Area:** contract
- **Action:** `GET /planning/final/print`
- **Steps:**
  1. Schedule a draft item (it moves to the Final Plan with WO/CM numbers).
  2. Open `/planning/final` and click **Print final plan** (or open `/planning/final/print`).
  3. Compare its columns with `/planning/draft/print`.
- **Expected:** the Final Plan table shows Schedule date, Vendor, Technician and Work order alongside the common columns — `reports/plan_print.html:24` was written for exactly that (`{% if scheduled %}…{% endif %}`).
- **Actual:** both prints render the *same* eight columns (`Equipment Tag 1, Tag 2, Service, Customer, Field, Location, Last completed, Proposed date`). The scheduled block never renders because `scheduled` is not in the render context; `{% if scheduled %}` on a Jinja default-undefined name is silently falsy (no `UndefinedError`, so this is *not* a 500 — it is invisible data loss on a printed document). The Final Plan print therefore omits the vendor, technician, schedule date and work-order number that scheduling just produced.
- **Evidence:** `.qa/evidence/contract_final_print_missing_scheduled_cols.html` (header cells: the 8 common columns only; probes for "Schedule date"/"Work order"/"Vendor"/"Technician" all False), captured with one plan temporarily scheduled; the plan row was then restored to `status='draft'` with all schedule fields NULL
- **Suspected cause:** `app/routers/reports.py:78-87` and `96-105` (audited revision) pass `request, user, plans, title, printed_by, today, format` but not `scheduled`, while the shared template branches on it (`app/templates/reports/plan_print.html:24,37`).
- **Fix status:** current tree adds `"scheduled": False` / `True` (`reports.py:83,102`) — predicted fixed.

## F-CONTRACT-006: `Plan.CANCELLED` is modelled but nothing ever sets it, so "cancelled work" cannot exist

- **Severity:** medium (declared capability not implemented) · **Status:** confirmed by exhaustive static search; live DB corroborates
- **Area:** contract (docs vs. implementation)
- **Action:** `GET /history` (documented as the cancelled-work browser)
- **Steps:**
  1. Search every writer of `Plan.status` in `app/`: `planning.py:134` (`DRAFT`), `planning.py:193` (`SCHEDULED`), `planning.py:236` (`COMPLETED`). Nothing writes `Plan.CANCELLED`.
  2. Confirm the constant exists (`models.py:140`) and is only ever *read*: `history.py:40` filters `Plan.status.in_([Plan.COMPLETED, Plan.CANCELLED])`.
  3. Confirm no route, button or template offers "cancel" for a plan; the only "Cancel" controls in the app are the Setup edit-form "back to list" links.
  4. Live DB: `select distinct status from plans` → `completed, draft, scheduled` (no `cancelled` row is reachable).
- **Expected:** per `README.md:46` ("History — browse completed and cancelled work") and `history.html:4` ("Completed and cancelled service records."), a user can cancel a scheduled/draft item and then find it in History.
- **Actual:** the feature does not exist. The History filter and the `chip-cancelled` CSS rule (`app/static/css/app.css:221`) are permanently dead code; there is no cancel button anywhere, so a planned item can only be deleted (draft only) or closed out — scheduled work that will not happen has no cancellation path and disappears neither from the Final Plan nor into History.
- **Evidence:** static writer search above (3 status writers, none `CANCELLED`); live `select distinct status from plans` → 3 statuses only
- **Suspected cause:** no cancellation endpoint was implemented in `app/routers/planning.py` (the Draft/Final/History loop has no cancel step), while `app/models.py:140`, `app/routers/history.py:40` and the README claim one.

## F-CONTRACT-007: Unhandled errors answer with plain-text 500, not the app's error page

- **Severity:** low (cosmetic/consistency; only reachable via an unexpected server error) · **Status:** confirmed live; still true of the current tree
- **Area:** contract (error handling)
- **Action:** any endpoint that raises an unhandled exception (e.g. the audited `POST /setup/equipment` FK failure)
- **Steps:**
  1. Trigger an unhandled server-side exception (the FK-violation POSTs of F-CONTRACT-002 do this reliably).
  2. Observe the response body.
- **Expected:** the styled `error.html` page the fix pass added, or at least a friendly message.
- **Actual:** `HTTP 500` with body `Internal Server Error` — Starlette's bare `ServerErrorMiddleware` response. `main.py` registers handlers only for `StarletteHTTPException` and `RequestValidationError`, so 500s bypass `error.html` entirely while 403/404/422 get the styled page.
- **Evidence:** `.qa/evidence/contract_500_equipment_location0.txt` (`HTTP 500`, body `Internal Server Error`)
- **Suspected cause:** `app/main.py:62-76` — no handler for generic `Exception` / `ServerErrorMiddleware`, so `templates/error.html` is unreachable for 500-class failures.

## F-CONTRACT-008: Cross-site `Referer` is turned into an in-app redirect path

- **Severity:** medium (misleading redirect; bounded, **not** an open redirect) · **Status:** confirmed in-process against the current tree (the container's audited revision had a different, unconditional version)
- **Area:** contract (error handling)
- **Action:** any POST that fails validation (the new global handler)
- **Steps:**
  1. Sign in.
  2. POST a form that fails validation (e.g. `POST /setup/customers` with an empty body) sending `Referer: http://evil.example.com/phish`.
  3. Observe the `Location` header.
- **Expected:** an off-site referer is discarded and the user is sent to a known same-app page (e.g. `/`), or to a whitelisted route such as `/setup/customers`.
- **Actual:** `303` with `Location: /phish`. `_safe_back` keeps the foreign referer's **path** (`urlsplit(ref).path`) without checking that it maps to a route in this app, so the attacker-controlled path becomes the post-error landing page (a 404 page in the error-page wrapper). No host escape, so this is not an open redirect, but the destination is attacker-influenced and can also be a side-effecting GET route such as `/logout`.
- **Evidence:** in-process run on the current revision: `cross-site Referer -> 303 location: /phish` (same-site referer correctly gave `/setup/customers`; absent referer correctly gave `/`)
- **Suspected cause:** `safe_back` returns any path that starts with `/`. It moved during the fix pass: the audited revision had it as `_safe_back` at `app/main.py:52-59`, the current tree has it at `app/templating.py:24-31` (`return ref if ref.startswith("/") else default`); `app/main.py:60-66` then redirects to it.

## F-CONTRACT-009: Raw JSON error bodies for browser navigation (403 / 404 / 422)

- **Severity:** medium (dead-end UX on a normal admin/URL path) · **Status:** confirmed live (audited revision) · **fixed in the current tree**
- **Area:** contract (error handling)
- **Action:** `GET /no-such-page`, `GET /reports/work-order/999999`, `GET /reports/calibration/999999`, `GET /reports/work-order/abc`, `GET /setup/customers?edit=abc`, `GET /history?customer_id=abc`, `GET /users` (as non-admin), `POST /login` (empty body)
- **Steps:**
  1. As admin (or with no session for `/no-such-page`) request each URL above.
  2. Note the `Content-Type` and body.
  3. For the 403: create a temporary non-admin user, sign in as them, open `/users` directly.
- **Expected:** a rendered page the user can navigate away from (the fix pass added `error.html` for exactly this).
- **Actual (audited revision):** `application/json` bodies — `{"detail":"Not Found"}`, `{"detail":"Work order not found"}`, `{"detail":"Calibration report not found"}`, `{"detail":"Admin access required"}`, and FastAPI's validation array for `?edit=abc` / `/reports/work-order/abc` / empty `/login`. `main.py`'s handler mapped **401 → redirect**, everything else → `JSONResponse`. A user who opens a bookmarked `/users` as a non-admin, follows a stale work-order link, or gets a truncated report URL lands on raw JSON with no way back.
- **Evidence:** `.qa/evidence/contract_404_unknown_url.json`, `contract_404_reports_work-order_999999.json`, `contract_404_reports_calibration_999999.json`, `contract_404_nonint_id.json`, `contract_403_users_nonadmin.json`, `contract_403_post_users_nonadmin.json`, `contract_422_nonint_path.json`, `contract_422_customers_empty.json`, `contract_422_login_empty.json`, `contract_422_equipment_blank_customer.json`, `contract_422_equipment_blank_field.json`, `contract_422_closeout_empty_date.json`, `contract_422_schedule_empty_date.json`, `contract_401_login_bad_pw.html`
- **Suspected cause:** `app/main.py:32-36` (audited revision) `return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)`.
- **Fix status / verification of the fix:** current tree renders HTML for all of these, verified in-process on the 17:04 revision — 404 → HTML "Not found", 403 → HTML "Not allowed", 401 → 303 `/login`, invalid POST → 303 + a flash that **does** survive on the redirect (`Set-Cookie: session=…` carries the message), GET with a validation failure → HTML 422. Status codes are preserved for non-browser clients (401/403/404/422), but the body media type changed from JSON to HTML for them.

## Predicted but **not** confirmed / not reproducible as defects

| item | why it is not a finding |
|---|---|
| `POST /setup/fields` with `customer_id=""` → 422 | browser `required` on the select blocks it; only a script can send `""`. LIVE raw-422 evidence exists (`contract_422_equipment_blank_customer.json`), but no user path reaches it. Marked **theoretical**. |
| Equipment form's Location/Field lists are globally unfiltered | a same-tab mismatch is now caught server-side (`setup.py:278-283`); on the audited revision it stored an inconsistent chain, but no live inconsistency exists in the seeded DB (FK-joined check returned 0 rows). Cross-record corruption requires a deliberate mismatch. Marked **theoretical** (latent). |
| `chip-cancelled` CSS never used | a consequence of F-CONTRACT-006, not an independent defect. |
| `ToggleAll` "Select all" behaviour | correct on both pages: `draft.html:24` omits `data-target` and correctly defaults to `equipment_ids`; the table header checkboxes pass `data-target="plan_ids"`. No dead JS. |
| `{{ from_d|fmt_date if from_d else '' }}` precedence | parses as intended; no misuse found anywhere. |
| `{% set f = request.session.pop('_flash', None) %}` in `base.html:42` | a Jinja-side `pop` does not remove the key from the real session object, and it does not write an HTTP response; measured flash still appears on the redirect target. No defect. |
