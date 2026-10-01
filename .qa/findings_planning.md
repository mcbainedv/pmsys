# QA findings — planning

Generated against http://127.0.0.1:8000

## F-PLAN-001: Auto-assign on Schedule is completely broken — HTTP 500 TypeError ('str' object is not callable)
- **Severity:** high
- **Area:** planning
- **Status:** confirmed
- **Action:** `POST /planning/schedule with auto_assign=on`
- **Steps:**
1. Log in, ensure active technicians exist (personnel ids 1,2,3 all is_active=1).
2. POST /planning/schedule with plan_ids=<my draft ids 4,8,9>, schedule_date=2026-10-20, auto_assign=on.
3. Observe HTTP 500 'Internal Server Error' (text/plain); nothing is scheduled, the plans stay draft.
4. docker logs pmsys-app-1 shows: File "/app/app/routers/planning.py", line 184, in schedule / grouping = auto_assign(plans, active_personnel) / TypeError: 'str' object is not callable.
- **Expected:** The selected draft items are round-robin assigned to active technicians and scheduled (flash 'Scheduled 3 item(s).').
- **Actual:** HTTP 500 for every request that sets auto_assign=on, regardless of whether technicians exist. The Form parameter `auto_assign: str = Form("")` shadows the imported `app.services.auto_assign` function, so the call at planning.py:184 invokes the string. The `except ValueError` branch (friendly 'No active technicians available to auto-assign.') is unreachable dead code — the TypeError is raised before the try block can ever convert it. The 'Auto-assign evenly' checkbox can never succeed.
- **Evidence:** .qa/evidence/planning_schedule_autoassign_500.txt (500 body) + server traceback quoted above; DB after: plans 4/8/9 still status=draft, personnel_id NULL.
- **Suspected cause:** app/routers/planning.py:158-187 (parameter `auto_assign` shadows `from app.services import auto_assign`; call site line 184)

## F-PLAN-002: Scheduling/closing out with a vendor or technician id that does not exist → HTTP 500 (FK IntegrityError)
- **Severity:** high
- **Area:** planning
- **Status:** confirmed
- **Action:** `POST /planning/schedule vendor_id=999999 | personnel_id=999999; POST /planning/closeout actual_vendor_id=999999 | actual_personnel_id=999999`
- **Steps:**
1. POST /planning/schedule with a draft plan_id plus vendor_id=999999 → HTTP 500.
2. POST /planning/schedule with a draft plan_id plus personnel_id=999999 → HTTP 500.
3. POST /planning/closeout with a scheduled plan_id plus actual_vendor_id=999999 → HTTP 500.
4. POST /planning/closeout with a scheduled plan_id plus actual_personnel_id=999999 → HTTP 500.
5. docker logs: `pymysql.err.IntegrityError: (1452, 'Cannot add or update a child row: a foreign key constraint fails (`pmsys`.`plans`, CONSTRAINT `plans_ibfk_3` FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`id`))')` raised from planning.py:199 (schedule commit) and planning.py:242 (closeout commit).
- **Expected:** A friendly flash ('Unknown vendor/technician') and no HTTP 500.
- **Actual:** Raw HTTP 500 'Internal Server Error' (text/plain). The FK ids are never validated. No partial write happens (the row stays draft/scheduled), so the failure is loud but not corrupting.
- **Evidence:** .qa/evidence/planning_schedule_badvendor_500.txt, planning_schedule_badpersonnel_500.txt, planning_closeout_badvendor_500.txt, planning_closeout_badpersonnel_500.txt
- **Suspected cause:** app/routers/planning.py:192-199 and :234-242 (no Vendor/Personnel existence check before commit)

## F-PLAN-003: Duplicate draft items are created for the same equipment + service (no de-duplication)
- **Severity:** medium
- **Area:** planning
- **Status:** confirmed
- **Action:** `POST /planning/draft/add (same equipment_ids + service_id, submitted repeatedly)`
- **Steps:**
1. POST /planning/draft/add service_id=7 equipment_ids=[8] → plan id 4 created.
2. POST the identical request again twice → plan ids 7 and 8 created with identical equipment/service/dates.
3. SELECT count(*) FROM plans WHERE equipment_id=8 AND service_id=7 → 3 identical draft rows.
4. Both duplicates can then be checked in the same Schedule POST, producing two work orders / two calibration numbers for one PM.
- **Expected:** Either the duplicate is rejected with a flash ('already in the draft plan') or it is silently merged.
- **Actual:** Every submit creates another row: the draft table accumulates identical lines and the flash says 'Added 1 item(s) to the draft plan.' with no warning. There is no unique constraint and no pre-insert check.
- **Evidence:** Phase-1 transcript: plans 4,7,8 all 'equipment_id 8 / service_id 7 / last_completed 2026-10-01 / proposed 2027-04-01'; SQL count returned 3.
- **Suspected cause:** app/routers/planning.py:121-138 (loop inserts unconditionally)

## F-PLAN-004: "Final Plan" printout drops the schedule/work-order columns (template tests an undefined `scheduled` variable)
- **Severity:** medium
- **Area:** planning
- **Status:** confirmed
- **Action:** `GET /planning/final/print`
- **Steps:**
1. Schedule an item (plan 11 → WO-0011) so it appears on /planning/final with Work order and Calibration links.
2. GET /planning/final/print and inspect the table headers.
3. Headers are ['Equipment Tag 1','Tag 2','Service','Customer','Field','Location','Last completed','Proposed date'] — no Schedule date / Vendor / Technician / Work order columns; the body contains no 'WO-' token at all.
4. The scheduled row (QA-PLAN-EQ-3) is printed but its work-order number is invisible.
- **Expected:** The Final Plan print lists Schedule date, Vendor, Technician and Work order for each scheduled item.
- **Actual:** Identical column set to the draft print. reports.print_final never puts 'scheduled' in the context, so `{% if scheduled %}` in reports/plan_print.html is always false and the whole block is skipped.
- **Evidence:** .qa/evidence/planning_final_print_no_wo.html, planning_final_print_headers.html (note: the lead's contract sweep already captured contract_final_print_missing_scheduled_cols.html — likely the same defect)
- **Suspected cause:** app/routers/reports.py:96-105 (missing context key) + app/templates/reports/plan_print.html:26

## F-PLAN-005: Work-order / calibration reports render for any status, including unscheduled drafts ("Work Order None")
- **Severity:** medium
- **Area:** planning
- **Status:** confirmed
- **Action:** `GET /reports/work-order/{plan_id}, GET /reports/calibration/{plan_id} for a draft plan`
- **Steps:**
1. GET /reports/work-order/1 (plan 1 is status=draft, wo_no NULL) → HTTP 200.
2. Page <title> is 'Work Order None' and the header block prints the literal None twice.
3. GET /reports/calibration/1 → HTTP 200, <title> 'Calibration None'.
4. Same for draft plans 2 and 3; also true for my own drafts (e.g. /reports/work-order/15).
- **Expected:** 404 (or a friendly 'this item has not been scheduled yet' page) because the report cannot exist before scheduling.
- **Actual:** A fully rendered work order / calibration report with a blank (None) document number is produced for any plan id, so a user can print/PDF an official-looking work order with no number.
- **Evidence:** .qa/evidence/planning_wo_draft_1.html, planning_cal_draft_1.html (both contain 'None'), planning_wo_11.html (the valid one)
- **Suspected cause:** app/routers/reports.py:108-138 and :141-171 (no status check before rendering)

## F-PLAN-006: Invalid dates are silently replaced instead of rejected (override, schedule_date, actual_date)
- **Severity:** medium
- **Area:** planning
- **Status:** confirmed
- **Action:** `POST /planning/draft/add proposed_date_override=not-a-date; POST /planning/schedule schedule_date=garbage; POST /planning/closeout actual_date=31/12/2026`
- **Steps:**
1. POST /planning/draft/add service_id=7 equipment_ids=[10] proposed_date_override='not-a-date' → flash 'Added 1 item(s)', stored proposed_date is the computed 2027-04-01, the user's value is discarded silently.
2. POST /planning/draft/add ... proposed_date_override='2026-02-30' (impossible date) → same silent substitution.
3. POST /planning/schedule plan_ids=[11] schedule_date='garbage' → flash 'Scheduled 1 item(s)', schedule_date stored as 2026-10-01 (today).
4. POST /planning/closeout plan_ids=[6] actual_date='31/12/2026' → flash 'Closed out 1 item(s)', actual_date stored as today.
- **Expected:** A flash error naming the bad date, and no write.
- **Actual:** `_parse_date` swallows ValueError and the callers fall back to a default (`override or computed`, `_parse_date(...) or date.today()`), so the UI reports success while a different date than requested is stored. This is the class the brief calls 'wrong scheduled dates'. Note: unreachable through the browser's <input type=date>, but trivial for any scripted/API client.
- **Evidence:** Phase-3 transcript (proposed_date 2026-10-01→2027-04-01; schedule_date 2026-10-01; actual_date 2026-10-01) plus DB rows shown there
- **Suspected cause:** app/routers/planning.py:16-22 (_parse_date), used at :120/:127, :176, :234

## F-PLAN-007: History / Draft date filters swallow bad input and give no feedback on an empty (e.g. reversed) range
- **Severity:** low
- **Area:** planning
- **Status:** confirmed
- **Action:** `GET /history?from=garbage&to=alsobad; GET /history?from=2026-10-06&to=2026-10-01; GET /planning/draft?from=garbage`
- **Steps:**
1. GET /history?from=garbage&to=alsobad → HTTP 200, filters ignored, all rows shown (as if no filter was applied).
2. GET /history?from=2026-10-06&to=2026-10-01 (reversed) → HTTP 200, table shows 'No history records yet.' with the dates still in the boxes.
3. GET /planning/draft?from=2027-12-31&to=2027-01-01 (reversed) → 'No draft items.' message.
4. Same on /planning/draft/print?from=not-a-date → the whole unfiltered draft plan is printed.
- **Expected:** A validation message for unusable dates, and at least a hint that the range is empty because from > to.
- **Actual:** Invalid dates are silently dropped (unfiltered result presented as if filtered); an impossible/reversed range is indistinguishable from 'no data at all' — a user can print an unfiltered plan believing a filter applied.
- **Evidence:** Phase-3/4 transcripts; .qa/evidence/planning_filter__history_customer_id_abc.json (422 counterpart)
- **Suspected cause:** app/routers/history.py:14-22 and app/routers/planning.py:84-89 + app/routers/reports.py:35-42 (same swallow-and-ignore pattern)

## F-PLAN-008: Bogus equipment ids on draft/add are skipped while a green success flash claims items were added
- **Severity:** low
- **Area:** planning
- **Status:** confirmed
- **Action:** `POST /planning/draft/add service_id=7 equipment_ids=[999999, 10]`
- **Steps:**
1. POST /planning/draft/add with equipment_ids=[999999] only → flash (success) 'Added 0 item(s) to the draft plan.'
2. POST with equipment_ids=[999999, 10] → flash 'Added 1 item(s) to the draft plan.' and no mention that 999999 was dropped.
- **Expected:** An error/warning naming the unknown equipment, or at least a non-success flash when nothing was added.
- **Actual:** Non-existent ids are silently `continue`d; the flash is success-styled even for 'Added 0 item(s)', so the operator believes work was planned when the draft is empty.
- **Evidence:** Phase-3 transcript (flash 'Added 0 item(s) to the draft plan.'); mixed case added exactly 1 row while 2 were submitted.
- **Suspected cause:** app/routers/planning.py:124-125 (silent skip) and :139 (unconditional success flash)

## F-PLAN-009: Missing / non-integer fields other than plan_ids still return raw JSON 422 (new variants of F-001)
- **Severity:** low
- **Area:** planning
- **Status:** confirmed
- **Action:** `POST /planning/draft/add (no service_id or no equipment_ids); POST /planning/schedule (no schedule_date); POST /planning/closeout (no actual_date); GET /history?customer_id=abc`
- **Steps:**
1. POST /planning/draft/add with equipment_ids=[8] and no service_id → 422 {"detail":[{"type":"missing","loc":["body","service_id"]...}]}.
2. POST /planning/draft/add with service_id=7 and no equipment_ids → 422 (equipment_ids missing); equipment_ids=abc → 422 int_parsing.
3. POST /planning/schedule with plan_ids but no schedule_date → 422; schedule_date='' → 422.
4. POST /planning/closeout without actual_date → 422; plan_ids=abc → 422 int_parsing.
5. GET /history?customer_id=abc → 422 int_parsing on a GET form filter (the History Filter button can never produce this, but a bookmarked/hand-edited URL can).
- **Expected:** The same friendly flash behaviour the routes implement for missing checkboxes / unknown ids.
- **Actual:** Raw FastAPI JSON 422 with no HTML/flash. Because the app's exception handler returns JSONResponse for every non-401 HTTPException, these land on a bare JSON page inside the browser. (F-001 covers the plan_ids case; these are different routes/fields.) The lead's contract sweep already has equivalent captures (contract_422_draft_add_no_equipment.json, contract_422_schedule_empty_date.json, contract_422_closeout_empty_date.json) — flagged here only for area completeness.
- **Evidence:** .qa/evidence/planning_422_draft_add_without_service_id.json, planning_422_draft_add_without_equipment_ids.json, planning_422_schedule_without_schedule_date.json, planning_422_closeout_without_actual_date.json, planning_filter__history_customer_id_abc.json
- **Suspected cause:** app/main.py:33-38 (HTTPException handler always returns JSONResponse) + Form(...) declarations in app/routers/planning.py

## F-PLAN-010: Missing plan id on the report routes returns a raw JSON 404 body, not an HTML error page
- **Severity:** low
- **Area:** planning
- **Status:** confirmed
- **Action:** `GET /reports/work-order/999999, GET /reports/calibration/999999`
- **Steps:**
1. GET /reports/work-order/999999 → HTTP 404, content-type application/json, body {"detail":"Work order not found"}.
2. GET /reports/calibration/999999 → HTTP 404, body {"detail":"Calibration report not found"}.
3. GET /reports/work-order/abc → 422 JSON; /reports/work-order/0 and /-1 → 404 JSON.
- **Expected:** A clean 404 is fine, but as this is a browser-facing HTML report surface it should render the app shell / a friendly page.
- **Actual:** Status code is a clean 404 (as intended) but the body is bare JSON in a browser tab; there is no HTML 404 page anywhere in the app (any unknown URL behaves the same). The report button is only rendered for existing rows, so this needs a stale link/bookmark.
- **Evidence:** .qa/evidence/planning_missing_reports_work-order_999999.json, planning_missing_reports_calibration_999999.json
- **Suspected cause:** app/main.py:33-38 (JSONResponse for all non-401 HTTPExceptions)

## F-PLAN-011: No route can ever set status='cancelled'; History advertises cancelled records, and a scheduled item cannot be cancelled or un-scheduled
- **Severity:** medium
- **Area:** planning
- **Status:** confirmed
- **Action:** `Grepping every router for a cancel path / inspecting the Final Plan UI`
- **Steps:**
1. `grep -rn cancel app/` finds only history.py/_models.py references to Plan.CANCELLED and unrelated Setup 'Cancel' edit links.
2. GET /planning/cancel and /planning/draft/cancel → 404; /history?status=cancelled → 200 but the parameter is ignored.
3. SELECT count(*) FROM plans WHERE status='cancelled' → 0; app/templates/history.html renders a chip for p.status but no cancel control exists.
4. The Final Plan page offers only 'Close out selected'; there is no un-schedule/delete for a wrongly scheduled item, and the Schedule flash/redirect gives no undo.
- **Expected:** Per README/History copy ('Completed and cancelled service records.'), cancelled work should be recorded and browsable.
- **Actual:** The 'cancelled' state is unreachable: nothing in the UI or API can produce it, so the History page can never show a cancelled record and the CSS chip chip-cancelled is dead. Worse, a plan scheduled by mistake can only be removed by closing it out, which writes a false completed record into History (there is no un-schedule path). Reported as a GAP per the brief.
- **Evidence:** Phase-4 transcript: status counts, 404s, `grep -rn cancel` output; /planning/final rendered controls list
- **Suspected cause:** missing route (app/routers/planning.py has no cancel endpoint; Plan.CANCELLED at app/models.py:140 is never assigned)
