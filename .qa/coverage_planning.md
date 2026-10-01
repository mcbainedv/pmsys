# Coverage — Planning loop & History

Area: Draft Plan → Schedule → Final Plan → Closeout → History, dashboard, print/report surfaces.
Target: http://127.0.0.1:8000 (containers `pmsys-app-1`, `pmsys-db-1`), admin/admin, system date **2026-10-01**.
Findings: see [findings_planning.md](findings_planning.md). Raw responses: `.qa/evidence/planning_*`.

## Scheduling-math verification (actual, observed dates)

Formula checked against `app/services.py: proposed_date(last_completed, frequency_weeks) = last_completed + timedelta(weeks=frequency_weeks)`.

| # | input (equipment / service / override) | expected by formula | observed in DB | match |
|---|---|---|---|---|
| 1 | QA-PLAN-EQ-1 + SCJ020 (26 wks), no override, no prior completion | last_completed = today **2026-10-01**, proposed = 2026-10-01 + 26 wks = **2027-04-01** | plan 4: last_completed 2026-10-01, proposed **2027-04-01** | ✅ |
| 2 | QA-PLAN-EQ-2 + SCJ020 (26 wks), no override | last_completed **2026-10-01**, proposed **2027-04-01** | plan 5: 2026-10-01 → **2027-04-01** | ✅ |
| 3 | QA-PLAN-EQ-3 + SCJ020, override **2026-12-25** | override wins: proposed **2026-12-25** | plan 6: last_completed 2026-10-01, proposed **2026-12-25** | ✅ |
| 4 | QA-PLAN-EQ-1 + SCJ010 (12 wks) | 2026-10-01 + 12 wks = **2026-12-24** | plan 9: **2026-12-24** | ✅ |
| 5 | duplicate submits of #1 (same eq+service) | one row (ideally) | plans 4, 7, 8 — **3 identical rows** → F-PLAN-003 | ❌ |
| 6 | completion of plan 5 with actual_date **2026-10-06**, then a new draft for EQ-2 + SCJ020 | last_completed = previous actual_date **2026-10-06**, proposed = 2026-10-06 + 26 wks = **2027-04-06** | plan 10: last_completed **2026-10-06**, proposed **2027-04-06** | ✅ |
| 7 | seeded baseline plans 1-3 (last_completed 2026-09-30, 26 wks) | 2026-09-30 + 26 wks = 2027-03-31 (pre-existing data, not mine) | 2027-03-31 | ✅ |
| 8 | schedule date supplied 2026-10-05 for plans 5 & 6 | schedule_date 2026-10-05, wo_no = WO-0005/WO-0006, cm_no = CM-0005/CM-0006 | exactly that (checked against `work_order_no()` / `calibration_no()`) | ✅ |
| 9 | schedule date supplied 2026-10-20 for plan 4 | schedule_date 2026-10-20 | 2026-10-20, WO-0004, CM-0004 | ✅ |

Cross-check: `app.services.proposed_date(date(2026,10,1), 26)` returns `2027-04-01` and `proposed_date(date(2026,10,6), 26)` returns `2027-04-06` — identical to what the live app stored.

## Checks

| check | action | result | note |
|---|---|---|---|
| Create own equipment 1 | POST /setup/equipment tag1=QA-PLAN-EQ-1 (customer 1/field 1/location 1) | PASS | row id 8, is_active=1 |
| Create own equipment 2,3 | POST /setup/equipment tag1=QA-PLAN-EQ-2/-3 | PASS | rows id 9, 10 |
| Draft add (computed date) | POST /planning/draft/add service 7, equipment [8,9] | PASS | plans 4,5; flash "Added 2 item(s)"; math row 1-2 ✅ |
| Draft add (explicit override) | POST /planning/draft/add service 7, equipment [10], override 2026-12-25 | PASS | plan 6 proposed 2026-12-25 |
| Draft add (different frequency) | POST /planning/draft/add service 4 (12 wks), equipment [8] | PASS | plan 9 proposed 2026-12-24 |
| Draft add duplicate equipment+service | POST /planning/draft/add same eq+svc 3× | **BUG** | F-PLAN-003: 3 identical draft rows, no dedupe guard |
| Draft add no service_id | POST /planning/draft/add without service_id | **BUG** | F-PLAN-009: raw JSON 422 (new variant of lead F-001) |
| Draft add service_id="" (placeholder) | POST service_id="" | **BUG** | F-PLAN-009: same 422 |
| Draft add service_id=999999 | POST service_id=999999 | PASS | flash "Please choose a service." |
| Draft add no equipment checked | POST /planning/draft/add without equipment_ids | **BUG** | F-PLAN-009: raw JSON 422 |
| Draft add equipment_ids=abc | POST equipment_ids=abc | **BUG** | F-PLAN-009: 422 int_parsing |
| Draft add bogus equipment id | POST equipment_ids=[999999] | **BUG** | F-PLAN-008: success flash "Added 0 item(s)" |
| Draft add mixed bogus+valid | POST equipment_ids=[999999,10] | **BUG** | F-PLAN-008: 999999 dropped silently |
| Draft add garbage override | POST override "not-a-date" | **BUG** | F-PLAN-006: silently stored computed 2027-04-01 |
| Draft add impossible date | POST override "2026-02-30" | **BUG** | F-PLAN-006: silently stored 2027-04-01 |
| Schedule happy path (vendor+tech) | POST /planning/schedule [5,6] date 2026-10-05 vendor 2 personnel 2 | PASS | status=scheduled, WO-0005/6, CM-0005/6 |
| Scheduled item leaves Draft | GET /planning/draft after schedule | PASS | ids 5,6 no longer present |
| Scheduled item appears in Final | GET /planning/final | PASS | rows 5,6 with WO/CM, vendor "VEN 01", tech "Jason Bilyk" |
| Final Plan "Work order" link | GET /reports/work-order/5 | PASS | 200, contains WO-0005, tag, service, customer |
| Final Plan "Calibration" link | GET /reports/calibration/5 | PASS | 200, contains CM-0005 |
| Schedule double-submit (idempotency) | POST /planning/schedule [5] again | PASS | flash "Select at least one draft item to schedule."; schedule_date/wo_no/updated_at unchanged |
| Schedule already-scheduled id only | POST [5] | PASS | rejected with flash, no re-stamp |
| Schedule non-existent id | POST [999999] | PASS | flash "Select at least one draft item to schedule." |
| Schedule missing schedule_date | POST without schedule_date | **BUG** | F-PLAN-009: raw JSON 422 |
| Schedule empty schedule_date | POST schedule_date="" | **BUG** | F-PLAN-009: raw JSON 422 |
| Schedule garbage schedule_date | POST schedule_date="garbage" | **BUG** | F-PLAN-006: silently scheduled for today (2026-10-01) |
| Schedule vendor_id=abc | POST vendor_id=abc | **BUG** | F-PLAN-009: 422 int_parsing |
| Schedule vendor_id=999999 | POST vendor_id=999999 | **BUG** | F-PLAN-002: HTTP 500 FK IntegrityError (`plans_ibfk_3`), planning.py:199 |
| Schedule personnel_id=999999 | POST personnel_id=999999 | **BUG** | F-PLAN-002: HTTP 500 FK IntegrityError, planning.py:199 |
| Schedule auto_assign=on | POST /planning/schedule [4,8,9] auto_assign=on | **BUG** | F-PLAN-001: HTTP 500 `TypeError: 'str' object is not callable`, planning.py:184; nothing scheduled |
| auto_assign when no active technicians | deactivate the 3 seeded technicians then auto_assign=on | BLOCKED | F-PLAN-001 raises the TypeError before the `except ValueError` branch, so the friendly "No active technicians" flash is dead code; the destructive deactivate/restore was deliberately skipped as it could not change the outcome or observe anything new (would have been reverted exactly). |
| Draft delete happy path | POST /planning/draft/delete [7] (draft) | PASS | row deleted, flash "Deleted 1 item(s)." |
| Draft delete non-draft id | POST /planning/draft/delete [11] (plan 11 was status=scheduled) | PASS | flash "Deleted 0 item(s)."; `select id,status from plans where id=11` still returns `11  scheduled` — scheduled rows are protected |
| Draft delete non-existent id | POST [999999] | PASS | flash "Deleted 0 item(s)." |
| Draft delete plan_ids=abc | POST plan_ids=abc | **BUG** | F-PLAN-009: 422 int_parsing |
| Draft delete nothing selected | POST without plan_ids | **BUG** | lead-confirmed **F-001** (raw JSON 422) — not re-reported |
| Closeout happy path | POST /planning/closeout [5] actual 2026-10-06 vendor 3 tech 3 | PASS | status=completed, actual_date 2026-10-06, vendor/tech replaced, redirect /history |
| Closeout double-submit | POST /planning/closeout [5] again | PASS | flash "Select at least one item to close out."; actual_date unchanged |
| Closeout draft id (wrong status) | POST /planning/closeout [9] | PASS | flash "Select at least one item to close out." |
| Closeout non-existent id | POST [999999] | PASS | flash "Select at least one item to close out." |
| Closeout missing actual_date | POST without actual_date | **BUG** | F-PLAN-009: raw JSON 422 |
| Closeout garbage actual_date | POST actual_date="31/12/2026" | **BUG** | F-PLAN-006: silently completed with actual_date = today |
| Closeout actual_vendor_id=999999 | POST actual_vendor_id=999999 | **BUG** | F-PLAN-002: HTTP 500 FK IntegrityError, planning.py:242 |
| Closeout actual_personnel_id=999999 | POST actual_personnel_id=999999 | **BUG** | F-PLAN-002: HTTP 500 FK IntegrityError, planning.py:242 |
| Closeout nothing selected | POST without plan_ids | **BUG** | lead-confirmed **F-001** — not re-reported |
| History shows completed item | GET /history after closeout | PASS | plan 5 listed with 2026-10-06, WO-0005, CM-0005, vendor/tech, chip "completed" |
| History chain for next PM | new draft for EQ-2+SCJ020 after closeout | PASS | last_completed = 2026-10-06 (actual date), proposed 2027-04-06 |
| History customer filter | GET /history?customer_id=1 / 6 / 999999 | PASS | 1 → rows 4,5,6; other customers → 0 rows (filter is applied) |
| History from/to filter | GET /history?to=2026-10-01 ; ?from=2026-10-06&to=2026-10-06 | PASS | 1 row each, the expected plan |
| History empty filter / Reset link | GET /history | PASS | all completed rows, no filter applied |
| History reversed range | GET /history?from=2026-10-06&to=2026-10-01 | **BUG** | F-PLAN-007: shows "No history records yet." — indistinguishable from genuinely empty |
| History garbage dates | GET /history?from=garbage&to=alsobad | **BUG** | F-PLAN-007: filters silently ignored, unfiltered rows shown |
| History customer_id=abc | GET /history?customer_id=abc | **BUG** | F-PLAN-009: raw JSON 422 |
| Draft filter + Reset | GET /planning/draft?from=…&to=… ; GET /planning/draft | PASS | filters select the right rows (2026-12-01..31 → plan 9; 2027-04-01 → 8,12,13,14,15) |
| Draft filter reversed/garbage | GET /planning/draft?from=2027-12-31&to=2027-01-01 ; ?from=garbage | **BUG** | F-PLAN-007: empty-state message / filter silently ignored |
| Dashboard renders | GET / | PASS | due-soon table + 3 stat tiles |
| Dashboard stats vs DB | compare tiles with `select status,count(*)` | PASS | draft 11 / scheduled 1 / completed 3 matched exactly |
| Dashboard due-soon window | draft with override 2026-10-15 (plan 16) | PASS | listed under "Due soon (next 30 days)"; only row in window |
| Draft plan print | GET /planning/draft/print | PASS | 200 HTML, title DRAFT PLAN, all draft rows |
| Draft print from/to filter | GET /planning/draft/print?from=2026-12-01&to=2026-12-31 | PASS | only plan 9's equipment printed |
| Draft print garbage filter | GET /planning/draft/print?from=not-a-date | **BUG** | F-PLAN-007: filter ignored, whole plan printed |
| Final plan print columns | GET /planning/final/print | **BUG** | F-PLAN-004: no Schedule date / Vendor / Technician / Work order columns, no `WO-` anywhere, although plan 11 (WO-0011) is scheduled |
| PDF export — draft print | GET /planning/draft/print?format=pdf | PASS | real PDF (`%PDF-`, 14 976 bytes, application/pdf) |
| PDF export — final print | GET /planning/final/print?format=pdf | PASS | real PDF (11 078 bytes) but inherits F-PLAN-004's missing columns |
| PDF export — work order / calibration | GET /reports/work-order/15?format=pdf ; /reports/calibration/15?format=pdf | PASS | real PDFs (13 981 / 13 371 bytes) |
| format casing / unknown format | ?format=PDF ; ?format=xml | PASS | both fall back to the printable HTML page (no error, no PDF) — cosmetic only |
| Work order report content | GET /reports/work-order/{scheduled id} | PASS | 200; contains WORK ORDER, tag, service, customer, "Performed by" block |
| Calibration report content | GET /reports/calibration/{scheduled id} | PASS | 200; contains CALIBRATION, tag, customer |
| Work order for unscheduled plan | GET /reports/work-order/1 (draft, wo_no NULL) | **BUG** | F-PLAN-005: 200 with `<title>Work Order None</title>` |
| Calibration for unscheduled plan | GET /reports/calibration/1 | **BUG** | F-PLAN-005: 200 with `<title>Calibration None</title>` |
| Report with missing id | GET /reports/work-order/999999 ; /reports/calibration/999999 | **BUG** | F-PLAN-010: clean 404 but raw JSON body `{"detail":"Work order not found"}` |
| Report with id 0 / -1 | GET /reports/work-order/0 ; /-1 | **BUG** | F-PLAN-010: 404 raw JSON |
| Report with non-int id | GET /reports/work-order/abc | **BUG** | F-PLAN-009/010: 422 raw JSON int_parsing |
| Cancelled records browsable | grep for a route setting status='cancelled' | **GAP** | F-PLAN-011: no such route; `/history?status=cancelled` is ignored; count(status=cancelled)=0 |
| Cancel affordance in planning UI | inspect Draft/Final/History controls | **GAP** | F-PLAN-011: only Schedule / Delete-draft / Close out; a wrongly scheduled item cannot be cancelled or un-scheduled |
| Back/navigation affordances | links on /planning/final, /history, /planning/draft | PASS | global nav (Home / Draft Plan / Final Plan / History) plus post-action redirects; no dead-end page found |
| Other testers' data untouched | only QA-PLAN-* rows created/modified | PASS | never scheduled/deleted plans 1-3 (seeded equipment); only plans pointing at QA-PLAN-EQ-* equipment were touched |
| Data hygiene / cleanup | delete my plans (SQL) then POST /setup/equipment/{8,9,10}/delete | PASS | after cleanup: `select status,count(*) from plans` = draft 3 (the seeded rows 1-3), equipment = ids 1-5 only, personnel 1-3 all is_active=1; `QA-PLAN-%` matches 0 rows |

## Environment / limitations

* Only one seeded customer (id 1, "Secure Energy") owns my equipment, so the History *customer* filter could be verified
  only as "matching customer → rows, other customer ids → 0 rows"; a second customer with completed work was not created
  (other testers' QA-SETUP customers had no history rows I could legitimately complete).
* The `auto_assign` + no-active-technician branch is unreachable because of F-PLAN-001; deliberately no deactivation of the
  seeded technicians was performed.
* Dates were supplied through the API. Browser `<input type=date>` cannot submit garbage, so F-PLAN-006/007 need a non-browser
  (or hand-crafted URL) client — noted per finding.
* Concurrency: other testers were hitting /planning/* during this run; all assertions above were made against rows/ids I created
  (QA-PLAN-EQ-1..3) plus the lead-confirmed F-001 behaviour.
