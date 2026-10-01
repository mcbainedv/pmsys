# QA findings — write-flow verification (independent falsification pass)

Generated against http://127.0.0.1:8000

## V-FLOW-001: Duplicate draft row still creatable in one request (repeated equipment id)
- **Severity:** low
- **Area:** planning
- **Status:** confirmed
- **Action:** `POST /planning/draft/add service_id=4 equipment_ids=[43,43]`
- **Steps:**
1. Create equipment QA-VERIFY-EQ-DUP2 (customer 1 / field 1 / location 1).
2. POST /planning/draft/add with service_id=4 and equipment_ids repeated twice for the same id.
3. Response: 303, flash 'Added 2 item(s) to the draft plan.'
4. DB: select id,equipment_id,service_id,status from plans -> ids 24 and 25, both 43/4/draft.
- **Expected:** Only one plan row for the equipment+service pair, with the extra selection skipped.
- **Actual:** Two identical draft rows are created when the same equipment id is repeated inside one submission. The already_open set is computed before the insert loop, so it cannot see rows added earlier in the same request. Not reachable from the rendered form (each active equipment renders exactly one checkbox); the two-submission trigger is fixed.
- **Evidence:** .qa/evidence/verify_item10_inrequest_duplicate.html
- **Suspected cause:** app/routers/planning.py:140-168 (already_open snapshot taken before the loop)

## V-FLOW-002: 500 on passwords longer than bcrypt's 72-byte limit (cross-cutting; observed in logs)
- **Severity:** medium
- **Area:** auth (outside the 13 assigned items)
- **Status:** confirmed
- **Action:** `POST /users (and /account/password, /users/{id}/reset-password) with a >72-byte password`
- **Steps:**
1. A concurrent verifier posted passwords longer than 72 bytes.
2. Server logged HTTP 500 with ValueError from app/auth.py:6 hash_password.
3. Timestamps: 12:11:13Z / 12:11:14Z (pre-existing), 12:13:52Z (x3), 12:15:25Z.
- **Expected:** 303 + a friendly flash, or at least no unhandled 500.
- **Actual:** ValueError: password cannot be longer than 72 bytes, truncate manually if necessary -> HTTP 500. Confirmed from the timestamped server tracebacks; not reproduced by this pass (its own POST /users calls all returned 303), so the log carries no traceback caused by this verification run.
- **Evidence:** .qa/evidence/verify_logs_tracebacks.txt
- **Suspected cause:** app/auth.py:6 hash_password() has no length guard; bcrypt rejects >72 bytes.
