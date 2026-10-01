# Coverage — independent regression verification (V-REGR)

Target: http://127.0.0.1:8000 (container `pmsys-app-1`, image built 2026-10-01 17:10:01 +05:00).
292 individual request-level checks were executed across 7 sweeps; the table below
aggregates them into 52 scored checks.

| check | result | note |
|---|---|---|
| Crawl every link from / (BFS) | PASS | 98 URLs reached; all 200/303; 0 dead links |
| All 7 Setup tabs load | PASS | customers, fields, locations, equipment, services, vendors, personnel |
| Draft / Final / History / Users / Account load | PASS | all 200 |
| Every ?edit=<id> link on Setup pages loads | PASS | all 200 |
| Print + report links all load | PASS | draft/final print + 5 work-order + 5 calibration, all 200 |
| No 404/405/500 anywhere in the crawl | PASS | 0 unexpected statuses |
| No Jinja markers in any page | PASS | no `{{`, `Undefined`, `Traceback` |
| No raw-JSON body anywhere in the crawl | PASS | 0 application/json responses |
| Form inventory on main pages | PASS | 19 forms + 32 row delete/toggle forms enumerated |
| Empty submit of every create/action form (14) | PASS | all 303 + friendly flash, never JSON |
| Delete/toggle with non-existent id | PASS | 303 HTML, nothing deleted (silent flash — V-REGR-006) |
| Delete/toggle with non-numeric id | PASS | 303 HTML validation redirect, never JSON |
| Create with dummy data (7 Setup entities) | PASS | 303 + flash, row rendered |
| Round-trip + ?edit pre-fill of every field | PASS | 7/7 entities, 0 fields silently discarded |
| Update via the ?edit form | PASS | 7/7 saved and re-rendered |
| Delete own created rows via their own buttons | PASS | 7/7 removed; no seeded row touched |
| GET /history filter form | BUG | /history?customer_id=abc and ?customer_id= → 422 (V-REGR-002) |
| GET /planning/draft filter form | PASS | ?from/?to valid and garbage both 200 |
| POST /logout | PASS | 303 → /login; subsequent GET / → 303 /login |
| GET /login while logged in | PASS | 303 → / |
| Anon GET /planning/draft | PASS | 303 → /login |
| POST /login wrong password | PASS | 401 HTML with friendly message (no Home link — V-REGR-004) |
| POST /login blank / missing password | PASS | 401 HTML, not JSON |
| Unknown URL /nope | PASS | 404 HTML + working Home link (also when anon) |
| GET /logout | PASS | 405 HTML + working Home link |
| GET /reports/work-order/nope, /reports/calibration/nope | PASS | 422 HTML + working Home link |
| GET /setup/customers?edit=abc and ?edit= | PASS | 200 |
| GET /setup/{fields,locations,equipment,services,vendors}?edit=abc / ?edit= | PASS | 200 (5 tabs × 2 forms) |
| GET /setup/personnel?edit=abc and ?edit= | BUG | 422 — only tab not using the tolerance helper (V-REGR-003) |
| Static assets favicon.svg / css/app.css / js/htmx.min.js | PASS | 200 with image/svg+xml, text/css, text/javascript |
| Every error page has a working Home link | BUG | 403/404/405/422/500 yes; 401 login page no (V-REGR-004) |
| GET /planning/draft/print (+ filtered) | PASS | 200, plausible, no None, no {{ |
| GET /planning/final/print | PASS | Schedule date / Work order / Vendor / Technician columns present |
| ?format=pdf for draft/final/work-order/calibration | PASS | 4/4 application/pdf with %PDF- bytes |
| Filtered draft print 'Download PDF' link | PASS | href keeps from=2026-01-01&to=2027-01-01 |
| Work order/calibration for a scheduled plan | PASS | plans 17-21 → 200 |
| Work order/calibration for an unscheduled draft | PASS | clean HTML 404 |
| Create QA-REGR normal user + log in | PASS | 303, session works |
| Non-admin GET /users | PASS | 403 HTML with Home link (was JSON before the fix) |
| Non-admin POST /users | PASS | 403 HTML with Home link |
| Non-admin Home / Account / Draft | PASS | all 200 |
| Account change with wrong current password | PASS | 303 + 'Current password is incorrect.' |
| Admin password unchanged after wrong-current attempt | PASS | admin/admin still logs in; rejected new password does not |
| Password >72 bytes (create / reset / change) | BUG | 3/3 HTTP 500 bcrypt ValueError (V-REGR-001) |
| Username / display-name over-length on create | PASS | 303 + friendly flash, no 500 |
| Duplicate username | PASS | 303 + 'Username ... already exists.' |
| Nav active tab (Home, 7 Setup, Draft, Final, History, Users, Account) | PASS | 13/13 |
| Setup dropdown contains all 7 tabs | PASS | 0 missing |
| Non-admin nav hides Users, keeps Setup | PASS | as designed |
| Delete of a non-existent id (flash feedback) | BUG | silent 303, no flash (V-REGR-006) |
| Setup delete redirect fallback target | BUG | /setup is not a route → 404 (V-REGR-005) |
| Deployed image matches working tree | BUG | 3 files newer than the image build (V-REGR-001/002) |
| **TOTAL** | **45 PASS / 7 BUG** | **52 checks — 45 passed, 7 failed** |

### Request-level counts

| sweep | requests | failures | JSON bodies |
|---|---|---|---|
| link crawl (step 1) | 98 | 0 | 0 |
| error surfaces (step 3) | 31 | 2 (`/setup/personnel?edit=abc`, `?edit=`) | 0 |
| form submissions (step 2) | 58 | 18 (17 silent-flash UX + `/history?customer_id=abc`) | 0 |
| auth flows + password edges (step 5) | 27 | 4 (3 bcrypt 500s + 401 Home link) | 0 |
| reports (step 4) | 12 | 0 | 0 |
| navigation (step 6) | 22 | 0 | 0 |
| side effects / ?edit pre-fill (step 7) | 44 | 0 | 0 |
| **total** | **292** | **24** | **0** |

**Total JSON-body responses encountered: 0.**

Note on the form-sweep failure count: 17 of the 18 are the same low-severity
UX issue (silent 303 with no flash when deleting a non-existent id, V-REGR-006)
reported once; the 18th is V-REGR-002.