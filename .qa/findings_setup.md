# QA findings — setup

Generated against http://127.0.0.1:8000

## F-SETUP-001: Over-long values crash the save with HTTP 500 (no maxlength / server-side length check)
- **Severity:** high
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/customers | /setup/services | /setup/equipment | /setup/vendors | /setup/personnel`
- **Steps:**
1. Open any Setup tab and type a value longer than the DB column (e.g. 200 chars into Customer name; the inputs have no maxlength attribute)
2. Press Add/Save changes
- **Expected:** 303 redirect + friendly flash (length exceeded), nothing written
- **Actual:** HTTP 500 (uncaught sqlalchemy.exc.DataError: 1406 "Data too long for column ...") on every affected tab: customers.name(128), services.code(32), equipment.tag1(64), vendors.name(128), personnel.first_name(64)
- **Evidence:** .qa/evidence/setup_customers_long_name.txt, .qa/evidence/setup_services_long_code.txt, .qa/evidence/setup_equipment_long_tag1.txt, .qa/evidence/setup_vendors_long_name.txt, .qa/evidence/setup_personnel_long_first_name.txt, .qa/evidence/server_log_setup.txt
- **Suspected cause:** app/routers/setup.py:105 (customers commit), 287 (equipment), 349 (services), 401 (vendors), 458 (personnel) — no length validation

## F-SETUP-002: Renaming a record to an existing unique value crashes with HTTP 500 (duplicate guard only on insert)
- **Severity:** high
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/customers | /setup/services | /setup/vendors with <id> + an already-used name/code`
- **Steps:**
1. Edit a customer/service/vendor via ?edit=<id>
2. Change the name/code to one already used by another record
3. Press Save changes
- **Expected:** 303 redirect + friendly '... already exists.' flash, record unchanged
- **Actual:** HTTP 500 (uncaught sqlalchemy.exc.IntegrityError 1062 Duplicate entry) for customers.name, services.code, vendors.name. The row is left unchanged (rollback works) but the user sees a raw 500
- **Evidence:** .qa/evidence/setup_customers_dupupdate.txt, .qa/evidence/setup_services_dupupdate.txt, .qa/evidence/setup_vendors_dupupdate.txt
- **Suspected cause:** app/routers/setup.py:98, 342, 394 — the UPDATE branch commits without the duplicate check that the INSERT branch has (lines 101, 345, 397)

## F-SETUP-003: Deleting a Field or Customer silently cascade-deletes its dependents instead of refusing
- **Severity:** high
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/fields/{id}/delete (field with locations, no equipment) and POST /setup/customers/{id}/delete (customer with field+location, no equipment)`
- **Steps:**
1. Create a customer with one field and one location (no equipment)
2. Press Delete on the customer row
3. Or: create a field with a location and no equipment and press Delete on the field row
- **Expected:** 303 + flash 'Cannot delete ...: it still has dependent records.' (as _safe_delete does when equipment blocks the FK); the child rows survive
- **Actual:** 303 + flash '... deleted.' — the field AND its location (and for a customer, the field and location too) are deleted from the DB with no warning. Silent data loss; the user is never told dependents were removed
- **Evidence:** .qa/evidence/setup_field_delete_cascade.html, .qa/evidence/server_log_setup.txt
- **Suspected cause:** app/models.py:44-46 (Customer.fields cascade='all, delete-orphan') and 59-61 (Field.locations cascade='all, delete-orphan') make the ORM delete children before _safe_delete's IntegrityError handler (app/routers/setup.py:60-68) can fire. The refusal only triggers when an Equipment FK blocks the cascade

## F-SETUP-004: Unvalidated numeric overflow in Services crashes with HTTP 500
- **Severity:** high
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/services with frequency_weeks/estimated_hours out of range`
- **Steps:**
1. Services tab → Frequency (weeks): 99999999999  (or Est. hours: 1e400)
2. Press Add service
- **Expected:** 303 redirect + friendly flash that the number is out of range
- **Actual:** HTTP 500 (pymysql DataError 1264 'Out of range value for column frequency_weeks' / estimated_hours=inf). The form's min=1/step=0.5 are client-side only and do not bound the upper end
- **Evidence:** .qa/evidence/setup_services_freq_huge.txt
- **Suspected cause:** app/routers/setup.py:332-333 (_int/_float accept any value) then commit at :349

## F-SETUP-005: Equipment accepts a Customer/Field/Location combination that is not a valid hierarchy
- **Severity:** high
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/equipment with mismatched customer_id / field_id / location_id`
- **Steps:**
1. Add equipment, choose Field = Brazeau but Location = 10-03-57-23W5 (a Wild River location) → saved
2. Or create customer C with field F, then add equipment with Customer = Secure Energy but Field = F → saved
- **Expected:** Rejected with a flash naming the inconsistent selection
- **Actual:** Saved: equipment stores a field from one customer with a location from another; the list renders a contradictory 'Customer / Field' + 'Location' pair. Silent data corruption that planning/scheduling then inherits
- **Evidence:** .qa/evidence/setup_equipment_crosslocation_list.html, .qa/evidence/setup_equipment_hierarchy_mismatch.html
- **Suspected cause:** app/routers/setup.py:239-289 equipment_save stores the three ids with no consistency validation

## F-SETUP-006: Non-existent parent id (from a stale/tampered select) crashes the save with HTTP 500
- **Severity:** high
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/fields | /setup/locations | /setup/equipment with a bogus FK id`
- **Steps:**
1. Submit a Setup form whose parent select holds an id that no longer exists (parent deleted in another tab/session)
2. e.g. POST /setup/fields customer_id=999999, /setup/locations field_id=999999, /setup/equipment customer_id=999999 / field_id=999999 / location_id=999999
- **Expected:** 303 redirect + friendly flash naming the missing parent
- **Actual:** HTTP 500 (uncaught IntegrityError 1452 FK constraint fails) on all five combinations — a NEW variant of the confirmed F-002 (which only covered equipment location_id=0); fields/locations/equipment customer_id/field_id are also unguarded
- **Evidence:** .qa/evidence/setup_fields_fk_customer_id.txt, .qa/evidence/setup_locations_fk_field_id.txt, .qa/evidence/setup_equipment_fk_customer_id.txt, .qa/evidence/setup_equipment_fk_field_id.txt, .qa/evidence/setup_equipment_fk_location_id.txt
- **Suspected cause:** app/routers/setup.py:151 (fields insert), 198 (locations insert), 286-287 (equipment insert) commit before checking the FK target exists

## F-SETUP-007: Blank required text field returns raw JSON 422 — the friendly 'is required' guards are dead code
- **Severity:** medium
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/{tab} with a required text field empty`
- **Steps:**
1. Submit any Setup form with a required text input empty
2. customers.name, fields.name, locations.name, equipment.tag1, services.code, services.name, vendors.name, personnel.first_name, personnel.last_name
- **Expected:** 303 redirect + the intended flash ('Customer name is required.' etc.); the handlers contain exactly that guard
- **Actual:** HTTP 422 application/json {"detail":[{"type":"missing",...}]} before the handler runs, so the guard is unreachable. (Equipment tag1 is the one exception — it is declared Form("") instead of Form(...), so it flashes correctly. whitespace-only input also flashes correctly.) The HTML `required` attribute hides this from normal browser users, but any non-browser client, autofill quirk or JS-disabled page hits it
- **Evidence:** .qa/evidence/setup_customers_blank_name.json, .qa/evidence/setup_services_blank_code.json, .qa/evidence/setup_personnel_blank_last.json
- **Suspected cause:** app/routers/setup.py:85,133,180,314,315,376,428,429 use `str = Form(...)`; FastAPI rejects the empty string before the `if not name` guard

## F-SETUP-008: Empty '— Customer —'/'— Field —' select placeholder returns raw JSON 422 on a second route family
- **Severity:** medium
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/fields | /setup/locations | /setup/equipment with customer_id/field_id=''`
- **Steps:**
1. Submit the Fields add form with the Customer select left on '— Customer —'
2. Same for Locations (field_id) and Equipment (customer_id or field_id)
- **Expected:** 303 redirect + friendly flash, as the handlers' `if not name or not customer_id` guard intends
- **Actual:** HTTP 422 application/json {"detail":[{"type":"missing","loc":["body","customer_id"]...}]} — `int = Form(...)` rejects the empty placeholder before the guard at setup.py:140/187/261 can run
- **Evidence:** .qa/evidence/setup_fields_empty_customer_id.json, .qa/evidence/setup_locations_empty_field_id.json, .qa/evidence/setup_equipment_empty_customer_id.json, .qa/evidence/setup_equipment_empty_field_id.json
- **Suspected cause:** app/routers/setup.py:134, 181, 242, 243 (`int = Form(...)`)

## F-SETUP-009: Non-integer ids in URLs return raw JSON 422 on all seven tabs
- **Severity:** medium
- **Area:** setup
- **Status:** confirmed
- **Action:** `GET /setup/{tab}?edit=abc  and  POST /setup/{tab}/abc/delete`
- **Steps:**
1. Open any Setup tab with a non-numeric or empty ?edit= value (stale bookmark / truncated link)
2. Or trigger a delete URL whose id is not an integer
- **Expected:** The tab renders normally (add form) and the delete redirects back with an error flash
- **Actual:** HTTP 422 application/json {"detail":[{"type":"int_parsing"...}]} on all 7 tabs for ?edit=abc and ?edit=; POST /setup/customers/abc/delete likewise 422
- **Evidence:** .qa/evidence/setup_edit_abc.json, .qa/evidence/setup_delete_nonint_id.json
- **Suspected cause:** app/routers/setup.py:74,121,168,215,303,365,417 (`edit: int = 0`) and :111 etc. (`cid: int` path param)

## F-SETUP-010: Negative frequency_weeks is accepted and stored as-is
- **Severity:** medium
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/services frequency_weeks=-21`
- **Steps:**
1. Services tab → Frequency (weeks): -21 (the input's min=1 is client-side only)
2. Press Add service
- **Expected:** Rejected with a flash (frequency must be >= 1 week)
- **Actual:** Saved with frequency_weeks=-21 and flash 'Service ... added.'; the scheduling formula last_completed + frequency_weeks then proposes a date in the past (silent data corruption)
- **Evidence:** .qa/evidence/setup_services_negative_freq.html
- **Suspected cause:** app/routers/setup.py:332 `_int(frequency_weeks, 4)` accepts any integer

## F-SETUP-011: 'Save changes' with a record id that no longer exists is a silent no-op
- **Severity:** medium
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/{tab} with <tab>_id=999999`
- **Steps:**
1. Edit a record, wait for it to be deleted elsewhere, press Save changes (or replay the form)
2. customers, fields, locations, equipment, services, vendors, personnel all behave the same
- **Expected:** Flash 'record not found' so the user knows nothing was saved
- **Actual:** 303 redirect with an empty flash: no success and no error message; the user believes the edit was saved
- **Evidence:** (no rendered error to capture — flash is empty; verified via DB: 0 rows created)
- **Suspected cause:** app/routers/setup.py:96, 145, 192, 280, 339, 391, 451 — the `if obj:` branch has no else

## F-SETUP-012: Services numeric inputs are silently coerced instead of validated
- **Severity:** low
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/services with non-numeric/empty frequency_weeks or estimated_hours`
- **Steps:**
1. Services → clear Frequency (weeks), or type 'abc'
2. Or type 'abc' into Est. hours
3. Press Add service
- **Expected:** Flash naming the invalid field
- **Actual:** 303 + 'added' flash: frequency_weeks silently becomes 4 (the hard-coded fallback) and estimated_hours silently becomes NULL. The user's input is discarded without notice
- **Evidence:** .qa/evidence/setup_services_freq_huge.txt (same form)
- **Suspected cause:** app/routers/setup.py:332-333 `_int(frequency_weeks, 4)` / `_float(estimated_hours)` swallow conversion errors

## F-SETUP-013: Delete redirect follows an arbitrary off-site Referer header (open redirect)
- **Severity:** low
- **Area:** setup
- **Status:** confirmed
- **Action:** `POST /setup/customers/{id}/delete with Referer: https://evil.example/phish`
- **Steps:**
1. Send a delete POST with a forged off-site Referer header
- **Expected:** Only same-site referers are honoured, otherwise redirect to the tab
- **Actual:** 303 Location: https://evil.example/phish
- **Evidence:** (header-only; see steps)
- **Suspected cause:** app/routers/setup.py:68 `RedirectResponse(request.headers.get('referer', '/'))`

## F-SETUP-014: GET on a delete URL returns raw JSON 405
- **Severity:** low
- **Area:** setup
- **Status:** confirmed
- **Action:** `GET /setup/customers/1/delete`
- **Steps:**
1. Navigate to a delete URL in the address bar (or follow a mis-typed link)
- **Expected:** HTML 405 page or redirect to the tab; the row must not be touched
- **Actual:** HTTP 405 application/json {"detail":"Method Not Allowed"} (seeded row untouched — no data risk)
- **Evidence:** (JSON body captured in cov)
- **Suspected cause:** app/main.py:32-36 returns JSONResponse for every StarletteHTTPException
