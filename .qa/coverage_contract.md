# Coverage — static contract audit

Scope: `app/templates/**` × `app/routers/*.py` × `app/main.py` for the PMSyS
rebuild. Live target `http://127.0.0.1:8000` (container `pmsys-app-1`,
admin/admin). Raw evidence in `.qa/evidence/contract_*`.

**Audit revision.** The working tree was patched by a parallel fix pass while
this audit ran (file mtimes 17:04–17:07). The container serves the pre-17:04
image and `docker-compose.yml` has no source bind-mount, so the running app is
frozen at the code that was originally read: the audit's **LIVE** column. The
**TREE** column is the working tree at the last hash snapshot
(`main.py` 956c572f, `planning.py` dde3258a, `setup.py` 486743d3,
`reports.py` b45de1df, `equipment.html` 70c0a00f, `personnel.html` 0e8d20b5,
`plan_print.html` c26fd04f) and was re-verified in-process against a throwaway
SQLite DB where noted. Nothing in the app was edited by this auditor.

## Checks

| check | result | note |
|---|---|---|
| Every `<form>` in `app/templates/**` enumerated | pass | 39 `<form>` elements (12 unique pages + the `logout` form on all 14 pages); table in `contract_matrix.md` |
| Every form action mapped to a registered route | pass | all 29 distinct actions resolve to a handler in `main.py`/`routers/*`; no dead endpoint |
| Every form field consumed by its handler | pass | no orphan field; `schedule`/`closeout` input names cover all `Form()` params |
| Every non-defaulted `Form()` param supplied by a form | **fail (LIVE)** | `draft_add.equipment_ids`, `draft_delete.plan_ids`, `schedule.plan_ids`+`schedule_date`, `closeout.plan_ids`+`actual_date`, `equipment.customer_id`/`field_id`, `fields.customer_id`, `locations.field_id` — all `Form(...)`. Fixed to defaults in TREE |
| `list[int] = Form(...)` + unchecked checkboxes | **fail (LIVE), confirmed** | `POST /planning/draft/add` with no equipment ticked → raw JSON 422; guard at `planning.py:117` unreachable. F-CONTRACT-001 |
| Required-but-empty `<select>` (`value=""`) vs `int = Form(...)` | **fail (LIVE), confirmed** | `customer_id`/`field_id` blank → 422 JSON; `location_id` placeholder `value="0"` → HTTP 500. F-CONTRACT-002 |
| `<select>` placeholder that is a non-nullable FK (`location_id=0`) | **fail (LIVE), confirmed** | 500 on `db.commit()`; TREE adds `required` + chain validation. F-CONTRACT-002 |
| Checkbox `is_active: str = Form("on")` can never persist False | **fail (LIVE), confirmed** | create-with-box-omitted → `is_active=1`; edit-with-box-omitted → still `1`. TREE verified persisting False on all four paths. F-CONTRACT-003 |
| Jinja names vs. router render context (all 20 templates) | 1 gap, **confirmed** | `reports/plan_print.html:24,37` branches on `scheduled`, never supplied → Final Plan print silently loses its scheduled columns. F-CONTRACT-005. TREE supplies it |
| Attribute chains that can be `None` | 20 unguarded chains listed | all map to NOT NULL FKs; guarded: `vendor`, `personnel`, `*.field`, `*.location`, `edit_obj`. Unguarded `plan.equipment.*` / `plan.service.*` / `*.customer.name` in draft, final, history, home and all three reports |
| `|fmt_date` / filter precedence | pass | `(x|fmt_date) if x else ''` parses as intended; `p.actual_date|fmt_date or '—'` correct; no `UndefinedError` risk from filters |
| `{% set %}` / `{% include %}` correctness | pass | `base.html:42` session `pop` writes no HTTP response (verified flash still renders); `setup/_tabs.html` and `reports/_doc_style.html` only use names their parents provide |
| Every `<button>` / `<a class="btn">` target route exists | pass | all nav, tab, list-action, print and report links resolve |
| Every inline `onclick` / `onchange` / `onsubmit` / `formaction` handler defined | pass | `ToggleAll` defined on both pages that call it (`draft.html:113`, `final.html:64`); `confirm` and `window.print` are native |
| `ToggleAll` data-target wiring | pass | `draft.html:24` intentionally omits `data-target` → defaults to `equipment_ids`; table headers pass `plan_ids` |
| Docs claim "browse completed **and cancelled** work" | **fail** | `Plan.CANCELLED` (`models.py:140`) has no writer anywhere; only read by `history.py:40`. F-CONTRACT-006 |
| Every writer of `Plan.status` enumerated | pass | exactly three: `planning.py:134` DRAFT, `:193` SCHEDULED, `:236` COMPLETED |
| Raw JSON `403` / `404` / `422` vs. `401` redirect | **fail (LIVE), confirmed** | `main.py:32-36` (audited) returned `JSONResponse` for all non-401; `401 → /login` worked. TREE renders `error.html` for all of them (re-verified in-process). F-CONTRACT-009 |
| Invalid-input POST lands somewhere useful | **pass in TREE** | global `RequestValidationError` handler redirects with a flash that survives the 303 (`Set-Cookie: session=…` carries `_flash`); container still returns raw JSON |
| Unhandled exceptions use the app's error page | **fail** | no handler for generic `Exception`; 500s are Starlette's plain-text `Internal Server Error`. F-CONTRACT-007 |
| Cross-site `Referer` cannot choose the landing path | **fail** | `safe_back` keeps the foreign referer's path (`/phish`). No host escape (not an open redirect). F-CONTRACT-008 |
| "Updated." flash for a missing record | **fail** | `auth.py:131-137` silently no-ops; Setup saves use `if obj:` with no `else` flash. F-CONTRACT-004 |
| Record creation with a blank *required* text field | pass | browser `required` blocks it; a scripted blank is rejected by `Form(...)` before any DB write (0 rows created in all four probes) |
| Test-data hygiene | pass | all records created for this audit deleted (`QA-CONTRACT-*` equipment/personnel/fields/locations, temporary non-admin user); the one temporarily scheduled plan was restored to `draft` with schedule fields NULL; admin password and `admin` user untouched (login as admin/admin re-verified after the probes) |

## Evidence index (contract)

| file | shows |
|---|---|
| `contract_422_draft_add_no_equipment.json` | 422 raw JSON for "Add to PM" with nothing ticked |
| `contract_500_equipment_{customer0,field0,location0}.txt` | three HTTP 500 variants of the equipment FK bug |
| `contract_verify_checkbox_current_tree.txt` | `is_active` now persists False on create *and* edit, personnel *and* equipment (current tree, SQLite) |
| `contract_final_print_missing_scheduled_cols.html` | Final Plan print with only the 8 common columns |
| `contract_404_*.json`, `contract_403_*.json`, `contract_422_*.json`, `contract_401_login_bad_pw.html` | raw-JSON/HTML error bodies on the audited revision |
| `contract_work_order_after_schedule.html` | work order renders for the temporarily scheduled plan |

## Limitations

* Findings are tied to the frozen container image (pre-17:04 revision) plus the
  working tree at the stated hashes. The tree was still changing after the
  snapshot (e.g. `main.py` 17:06, `auth.py` 17:07, `setup.py` 17:07), so TREE
  claims are "current at the cited hash", not "current now".
* Live confirmation of the TREE fixes is impossible without a rebuild, which
  this audit was not permitted to do; those verifications used
  `TestClient` against the working tree with a throwaway SQLite DB and a
  dependency override, never the live MariaDB.
* `?format=pdf` (WeasyPrint) paths were not exercised; only the HTML report
  paths were requested.
