# Static contract matrix — PMSyS form field ↔ endpoint ↔ handler

Auditor: QA contract subagent. Repo: `/home/mcb/Agents/PMSyS/pmsys`.
Live target: `http://127.0.0.1:8000` (container `pmsys-app-1`), admin/admin.

## Revision note (read this first)

The working tree was rewritten **during** this audit (17:04–17:05) by a parallel
fix pass, while the running container kept serving the **pre-17:04 build image**
(`docker-compose.yml` has no source bind-mount, so the container only changes on
rebuild). Two column-sets therefore appear below:

| label | meaning |
|---|---|
| **LIVE** | behaviour observed over HTTP against `pmsys-app-1` = the code as originally read (the audited revision) |
| **TREE** | the working tree as of the last hash snapshot in `coverage_contract.md` |

Everything marked *confirmed live* was reproduced by a real request to the
running instance and its raw response is in `.qa/evidence/`.

## 1. Full cross-reference: `<form>` → handler

39 `<form>` elements are rendered across 14 pages (the `logout` form appears on
every page and is listed once). "Fields posted" = every named control inside the
form, i.e. what a browser can actually send. `Form(...)` params are as declared
in the handler signature.

| # | template | form action | fields posted | handler | `Form()` params expected | mismatch? (LIVE → TREE) |
|---|---|---|---|---|---|---|
| 1 | `base.html:35` | `POST /logout` | — | `auth.logout` (`auth.py:38`) | none | ok |
| 2 | `login.html:15` | `POST /login` | username, password | `auth.login` (`auth.py:19`) | `username: str = Form(...)`, `password: str = Form(...)` | ok (browser `required` covers both) |
| 3 | `account.html:8` | `POST /account/password` | current_password, new_password, confirm_password | `auth.change_password` (`auth.py:51`) | same 3 × `Form(...)` | ok |
| 4 | `users.html:8` | `POST /users` | username, display_name, password, role | `auth.create_user` (`auth.py:81`) | username `Form(...)`, display_name `Form("")`, password `Form(...)`, role `Form("user")` | ok |
| 5 | `users.html:34` | `POST /users/{id}/toggle` | — | `auth.toggle_user` (`auth.py:112`) | path param only | ok (form not rendered for self) |
| 6 | `users.html:38` | `POST /users/{id}/reset-password` | password | `auth.reset_password` (`auth.py:123`) | `password: str = Form(...)` | ok; but missing target id → **silent no-op** (F-CONTRACT-004) |
| 7 | `setup/customers.html:9` | `POST /setup/customers` | name (+customer_id when editing) | `setup.customer_save` (`setup.py:82`) | `name Form(...)`, `customer_id int = Form(0)` | ok |
| 8 | `setup/customers.html:28` | `POST /setup/customers/{id}/delete` | — | `customer_delete` (`setup.py:110`) | path param | ok (delete blocked by FK → flash) |
| 9 | `setup/fields.html:9` | `POST /setup/fields` | customer_id, name (+field_id) | `field_save` (`setup.py:130`) | `name Form(...)`, `customer_id int = Form(...)`→TREE `Form(0)`, `field_id Form(0)` | LIVE: `customer_id=""` → 422 JSON; TREE: `Form(0)` + existence check → flash |
| 10 | `setup/fields.html:35` | `POST /setup/fields/{id}/delete` | — | `field_delete` (`setup.py:157`) | path param | ok |
| 11 | `setup/locations.html:9` | `POST /setup/locations` | field_id, name (+location_id) | `location_save` (`setup.py:177`) | `field_id int = Form(...)`→TREE `Form(0)` | same as #9 |
| 12 | `setup/locations.html:35` | `POST /setup/locations/{id}/delete` | — | `location_delete` (`setup.py:204`) | path param | ok |
| 13 | `setup/equipment.html:9` | `POST /setup/equipment` | customer_id, field_id, location_id, tag1, tag2, description, equipment_type, manufacturer, model, serial_no, parts_list_no, instruction_no, is_active, (+equipment_id) | `equipment_save` (`setup.py:239`) | 13 params; LIVE `customer_id/field_id` `Form(...)`, `location_id Form(0)`, `is_active Form("on")`; TREE all `Form(0)`/`Form("")` + customer/field/location chain validation | **LIVE: 3× HTTP 500** (`customer_id=0`, `field_id=0`, `location_id=0`) → TREE: flash + redirect (fixed) |
| 14 | `setup/equipment.html:69` | `POST /setup/equipment/{id}/delete` | — | `equipment_delete` (`setup.py:292`) | path param | ok (missing id → silent no-op) |
| 15 | `setup/services.html:9` | `POST /setup/services` | code, name, frequency_weeks, estimated_hours, discipline, description (+service_id) | `service_save` (`setup.py:311`) | `code/name Form(...)`, freq/estimated as `str` | ok — `str` typing avoids the numeric-422 class |
| 16 | `setup/services.html:36` | `POST /setup/services/{id}/delete` | — | `service_delete` (`setup.py:354`) | path param | ok |
| 17 | `setup/vendors.html:9` | `POST /setup/vendors` | name, contact_name, phone, email (+vendor_id) | `vendor_save` (`setup.py:373`) | `name Form(...)`, 3 × `Form("")` | ok; missing vendor_id → **silent no-op** (F-CONTRACT-004) |
| 18 | `setup/vendors.html:33` | `POST /setup/vendors/{id}/delete` | — | `vendor_delete` (`setup.py:406`) | path param | ok |
| 19 | `setup/personnel.html:9` | `POST /setup/personnel` | first_name, last_name, position, discipline, is_active (+personnel_id) | `personnel_save` (`setup.py:425`) | 4 × `Form(...)`/`Form("")`, `is_active Form("on")`→TREE `Form("")` | **LIVE: unchecked Active ignored** → TREE: persists False (fix verified, F-CONTRACT-003) |
| 20 | `setup/personnel.html:34` | `POST /setup/personnel/{id}/delete` | — | `personnel_delete` (`setup.py:463`) | path param | ok |
| 21 | `planning/draft.html:11` | `POST /planning/draft/add` | service_id, equipment_ids(0..n), proposed_date_override | `draft_add` (`planning.py:103`) | LIVE `service_id int = Form(...)`, `equipment_ids: list[int] = Form(...)`; TREE `Form(0)`, `Form([])` | **LIVE: no equipment ticked → raw 422 JSON**, dead flash guard at `planning.py:117` → TREE: flash |
| 22 | `planning/draft.html:47` | `GET /planning/draft` | from, to | `draft` (`planning.py:81`) | query params, tolerant parse | ok |
| 23 | `planning/draft.html:62` | `POST /planning/schedule` | schedule_date, vendor_id, personnel_id, auto_assign, plan_ids(0..n) | `schedule` (`planning.py:158`) | LIVE `plan_ids list[int]=Form(...)`, `schedule_date str=Form(...)`; TREE `Form([])`, `Form("")` | **LIVE: zero ticks → raw 422 JSON** (lead-confirmed); TREE: flash |
| 24 | `planning/draft.html:77` (`formaction`) | `POST /planning/draft/delete` | same form body (plan_ids may be absent) | `draft_delete` (`planning.py:143`) | LIVE `plan_ids: list[int] = Form(...)`; TREE `Form([])` | **LIVE: zero ticks → raw 422 JSON** (lead-confirmed); TREE: "Deleted 0 item(s)" |
| 25 | `planning/final.html:10` | `POST /planning/closeout` | actual_date, actual_vendor_id, actual_personnel_id, plan_ids(0..n) | `closeout` (`planning.py:217`) | LIVE `plan_ids Form(...)`, `actual_date str=Form(...)`; TREE `Form([])`, `Form("")` | **LIVE: zero ticks → raw 422 JSON** (lead-confirmed); TREE: flash |
| 26 | `history.html:7` | `GET /history` | customer_id, from, to | `history.history` (`history.py:23`) | `customer_id: int = 0` + query params | ok; `customer_id=abc` → 422 JSON LIVE / HTML TREE |
| 27 | `reports/plan_print.html:11` | `GET /planning/draft/print` | (`?format=pdf` from link) | `print_draft` (`reports.py:65`) | query `format` | LIVE: `scheduled` never passed → Final Plan print silently dropped its Schedule/Vendor/Technician/WO columns (F-CONTRACT-005) → TREE: `scheduled` False/True added |
| 28 | `reports/work_order.html:11` | `GET /reports/work-order/{id}` | (`?format=pdf`) | `work_order` (`reports.py:108`) | path param, `format` | `id=999999` → raw JSON 404 LIVE / HTML TREE |
| 29 | `reports/calibration.html:11` | `GET /reports/calibration/{id}` | (`?format=pdf`) | `calibration` (`reports.py:141`) | path param, `format` | same as #28 |

Every `GET` "Filter"/"Reset" control is an `<a>` or `type=submit` inside the GET
form; all resolve against real routes.

### Field-level notes

* **Every list-valued parameter is a checkbox group** (`equipment_ids`,
  `plan_ids`). Unchecked checkboxes are simply absent from the body, so
  `list[int] = Form(...)` receives *nothing* and FastAPI raises a 422
  `{"loc":["body","equipment_ids"],"type":"missing"}` **before** the handler's
  own `if not equipment_ids:` guard can flash. `Form([])` (TREE) is the correct
  declaration; `Form(...)` is only safe if the client always sends at least one
  value.
* **`location_id` in `setup/equipment.html`** was the only placeholder select
  whose server parameter carried `int = Form(0)` **and** no guard: `0` is not a
  valid FK, so the placeholder meant a 500. TREE now marks the select `required`
  (line 28) *and* validates the customer→field→location chain server-side.
* All remaining placeholder selects (`customer_id`, `field_id` in fields /
  locations / equipment) use `value=""` with the `required` attribute; a browser
  refuses to submit them, and a scripted `""` produces the raw 422 described
  above. They cannot submit the literal placeholder text (all use an explicit
  `value=""`).
* No form posts a field the handler does not consume; no handler declares a
  non-defaulted `Form(...)` that no form can supply, after the TREE fixes.
* Type compatibility: `frequency_weeks` and `estimated_hours` are declared
  `str` and coerced with `_int`/`_float`, so a blank or junk number cannot 422;
  `name="x" value=""` posting into `int = Form(...)` was the only incompatible
  pattern and only on the parameter sets listed above.

## 2. Handler signature inventory (`Form(...)` parameters by endpoint)

| handler | required (`Form(...)`) | defaulted | list-typed |
|---|---|---|---|
| `customer_save` | name | customer_id | — |
| `field_save` | name, **customer_id (LIVE)** | field_id | — |
| `location_save` | name, **field_id (LIVE)** | location_id | — |
| `equipment_save` | **customer_id, field_id (LIVE)** | location_id, 10 text fields, is_active, equipment_id | — |
| `service_save` | code, name | frequency_weeks, estimated_hours, discipline, description, service_id | — |
| `vendor_save` | name | contact_name, phone, email, vendor_id | — |
| `personnel_save` | first_name, last_name | position, discipline, is_active, personnel_id | — |
| `create_user` | username, password | display_name, role | — |
| `reset_password` | password | — | — |
| `change_password` | current_password, new_password, confirm_password | — | — |
| `login` | username, password | — | — |
| `draft_add` | **service_id, equipment_ids (LIVE)** | proposed_date_override | equipment_ids |
| `draft_delete` | **plan_ids (LIVE)** | — | plan_ids |
| `schedule` | **plan_ids, schedule_date (LIVE)** | vendor_id, personnel_id, auto_assign | plan_ids |
| `closeout` | **plan_ids, actual_date (LIVE)** | actual_vendor_id, actual_personnel_id | plan_ids |

Bold = supplied by a form in a way a user action can legitimately omit or
blank out. Every bold entry became a raw-JSON 422 or a 500 on the audited
revision.

## 3. Button / JS wiring

| control | target | defined? |
|---|---|---|
| `base.html` nav + dropdown (7 Setup links, Draft/Final/History/Users/Account/Home) | all routes exist (`main.py:86`, `auth.py:44,73`, `planning.py:81,204`, `history.py:23`, each `setup.py` GET) | ok |
| `planning/draft.html:6` "Print draft plan" → `/planning/draft/print` | `reports.print_draft` | ok |
| `planning/draft.html:24` "Select all" `onchange="ToggleAll(this)"` | `ToggleAll` defined at `draft.html:113`, defaults to `equipment_ids` | ok |
| `planning/draft.html:41` "Add to PM" | `POST /planning/draft/add` | ok (LIVE 422 when nothing ticked) |
| `planning/draft.html:56/57` Filter / Reset | GET `/planning/draft` | ok |
| `planning/draft.html:76` "Schedule selected" | `POST /planning/schedule` | ok |
| `planning/draft.html:77` "Delete selected" (`formaction`, `onclick=confirm`) | `POST /planning/draft/delete` | ok; submits `schedule_date` too — harmless because the handler ignores it |
| `planning/draft.html:84` header select-all `data-target="plan_ids"` | `ToggleAll` | ok |
| `planning/final.html:6` "Print final plan" | `reports.print_final` | ok (report body was incomplete, F-CONTRACT-005) |
| `planning/final.html:23` "Close out selected" | `POST /planning/closeout` | ok |
| `planning/final.html:30` select-all + `ToggleAll` (`final.html:64`) | `data-target="plan_ids"` | ok |
| `planning/final.html:50,51` Work order / Calibration | `reports.work_order` / `reports.calibration` | ok |
| `history.html:46,47` Work order / Calibration | same | ok |
| all `onsubmit="return confirm(...)"` on delete forms | native | ok |
| all `onclick="window.print()"` in report templates | native | ok |
| all "Cancel" links in Setup edit forms | back to the list route | ok |
| all `?edit={{ r.id }}` links | `edit: int = 0` GET param | ok; `?edit=abc` → 422 JSON LIVE, HTML TREE |

No dead route, no dead JS function, no button that submits a form missing a
field it cannot supply. The only "unsupplied required field" cases are the
unconditional `Form(...)` list/select parameters in §1, driven by *user
selection*, not by the button.

## 4. Jinja variable contract

Templates reach names from `TemplateResponse(request, name, ctx)` (auto-injects
`request`) or, for reports, `templates.env.get_template(name).render(ctx)`
(no auto-injection — `reports.py` passes `request` explicitly; `base.html` is
not extended there).

| template | names used | supplied by router? |
|---|---|---|
| `base.html` | `request`, `user` | yes (every context) |
| `home.html` | `user`, `due_soon`, `stats`, `today` | yes (`main.py:109`) |
| `setup/*.html` | `user`, `rows`, `edit_obj` (+ option lists) | yes (`setup.py` GETs) |
| `planning/draft.html` | `user`, `plans`, `services`, `equipment`, `vendors`, `personnel`, `from_d`, `to_d`, `today` | yes (`_form_context` + `draft`) |
| `planning/final.html` | `user`, `plans`, `vendors`, `personnel`, `today` | yes |
| `history.html` | `user`, `plans`, `customers`, `customer_id`, `from_d`, `to_d` | yes (`history.py:54`) |
| `reports/*.html` | `request`, `user`/`plan`/`plans`, `title`, `printed_by`, `today`, `format` | yes in TREE; **`scheduled` was missing in the audited revision** (`reports.py` old lines 78-105) → F-CONTRACT-005 |
| `reports/_doc_style.html` | none | n/a (included) |

Guarded vs. unguarded attribute chains:

* Guarded correctly everywhere: `p.vendor`, `p.personnel`, `equipment.field`,
  `equipment.location` (`x if x else '—'` / `if x`), and `edit_obj` in every
  Setup form (`edit_obj.name if edit_obj else ''`).
* **Unguarded (would 500 on a broken FK):** `plan.equipment.*` and
  `plan.service.*` in `planning/draft.html:94-99`, `planning/final.html:40,41`,
  `history.html:36,37`, `home.html:32-34`, `reports/work_order.html:21-44`,
  `reports/calibration.html:21-33`, `reports/plan_print.html:31-33`;
  `p.equipment.customer.name` at `planning/draft.html:98`,
  `planning/final.html:43`, `history.html:39`, `home.html` (via service),
  `reports/*`; `r.customer.name` at `setup/equipment.html:65`;
  `r.field.customer.name` at `setup/locations.html:32`; `r.customer.name` at
  `setup/fields.html:32`; `e.customer.name` at `planning/draft.html:29`.
  All of these map to NOT NULL FKs, so they are safe *only* while the FK chain
  is enforced — which is exactly what the `location_id=0` 500 defeat of the
  audited revision showed was not true of every write path.
* Filter precedence: `{{ from_d|fmt_date if from_d else '' }}` parses as
  `(from_d|fmt_date) if from_d else ''` — correct, no misuse. Same for
  `p.actual_date|fmt_date or '—'`.
* `{% set f = request.session.pop('_flash', None) %}` in `base.html:42` writes
  nothing to the HTTP response, so it cannot clobber a route-set flash on the
  same render (verified: the invalid-POST flash survives the handler's redirect).
* `error.html` uses `status`, `title`, `message` — all passed by `_error_page`.

## 5. Coverage of the requested checks

| check | result |
|---|---|
| forms extracted / handlers cross-referenced | 39 forms / 40 handler entry points |
| list-valued `Form(...)` behaviour | 3 endpoints raw-422 on empty selection (LIVE), all defaulted in TREE |
| required-but-empty selects | `location_id` 500 (LIVE, fixed in TREE); others 422 JSON (LIVE, fixed in TREE) |
| checkbox defaults | LIVE `is_active` ignored; TREE verified persisting False both ways |
| Jinja variable contract | 1 missing context var (F-CONTRACT-005, fixed in TREE); ~20 unguarded FK chains listed above |
| button / JS wiring | no dead route, link, or JS function |
| docs vs. implementation | `Plan.CANCELLED` has no writer (F-CONTRACT-006) |
| error-handling statuses | 403/404/422 JSON + 500 plain text on LIVE; all HTML in TREE except 500 |
