# Independent verification of the write-flow fixes

* **Target:** http://127.0.0.1:8000 — container `pmsys-app-1`, DB `pmsys-db-1`
* **Run window (UTC):** 2026-10-01 12:11:22 – 12:15:40
* **Method:** every original trigger replayed against the running app through `.qa/qa.py`; HTTP
  status, the one-shot flash on the redirect target, and the MariaDB row state recorded for each.
  Raw responses saved under `.qa/evidence/`.
* **Scope guard:** no application code was edited; the admin password was not touched; no seeded
  demo row was modified or deleted. Between the checks, this pass created only `QA-VERIFY-`-prefixed
  rows and deleted all of them (§Cleanup).

## Verdict tally

| verdict | count |
|---|---|
| FIXED | 12 |
| STILL BROKEN | 1 |
| REGRESSION | 0 |

The single STILL BROKEN is **item 10**, and only for a crafted single request that repeats the same
equipment id; the documented two-submission trigger is fixed. Findings: **V-FLOW-001**
(duplicate draft row), **V-FLOW-002** (cross-cutting bcrypt long-password 500, not part of the 13
items).


---

## Item 1 — Auto-assign evenly

**Verdict: FIXED**

**Original trigger:** tick an item + “Auto-assign evenly” and POST `/planning/schedule`
with `auto_assign=on` — guaranteed HTTP 500 `TypeError: 'str' object is not callable`.

**Requests:** `POST /setup/equipment` (own equipment `QA-VERIFY-EQ-A`, customer 1 / field 1 /
location 1), `POST /planning/draft/add`, then `POST /planning/schedule` with `auto_assign=on`
for a single item and then for a batch of four items (services 2–5) in one request.

**Observed:** every request returned **303**, flash `Scheduled N item(s).` The single item landed on
`/planning/final` with `status=scheduled`, `personnel_id=1`, `wo_no=WO-0017`, `cm_no=CM-0017`,
`schedule_date=2026-10-01`. The batch of four was spread `plan18→p1, plan19→p2,
plan20→p3, plan21→p1`, i.e. exactly round-robin over the three active technicians in
`last_name` order (Bezruchak 1, Bilyk 2, Sinclair 3). No 500.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| create QA-VERIFY-EQ-A | `POST /setup/equipment customer_id=1 field_id=1 location_id=1 tag1=QA-VERIFY-EQ-A is_active=on` | 303 | Equipment 'QA-VERIFY-EQ-A' added. | equipment id=30 is_active=1 | **FIXED** | `.qa/evidence/verify_item1_equipment.html` |
| add to draft | `POST /planning/draft/add service_id=1 equipment_ids=30` | 303 | Added 1 item(s) to the draft plan. | plan id=17 status=draft | **FIXED** | `.qa/evidence/verify_item1_draft_add.html` |
| auto-assign one item | `POST /planning/schedule plan_ids=17 auto_assign=on` | 303 | Scheduled 1 item(s). | status=scheduled personnel_id=1 wo_no=WO-0017 cm_no=CM-0017 schedule_date=2026-10-01 | **FIXED** | `.qa/evidence/verify_item1_auto_assign.html` |
| round-robin 4 items / 3 active technicians | `POST /planning/schedule plan_ids=[18, 19, 20, 21] auto_assign=on` | 303 | Scheduled 4 item(s). | plan18->p1, plan19->p2, plan20->p3, plan21->p1 | **FIXED** | `.qa/evidence/verify_item1_roundrobin.html` |

---

## Item 2 — Auto-assign with no active technicians

**Verdict: FIXED**

**Original trigger:** the same auto-assign POST while no technician is active.

**Steps:** recorded the prior state of technicians 1/2/3 (all `is_active=1`), then deactivated all
three through the app's own `POST /setup/personnel` (omitting `is_active`) and confirmed
`is_active=['0','0','0']` in the DB before the test. Then created `QA-VERIFY-EQ-NOTA`, added it to
the draft plan (service 6) and posted auto-assign.

**Observed:** **303** with the friendly flash `No active technicians available to auto-assign.`
The plan stayed `draft` with `personnel_id=NULL`, `wo_no=NULL`, `schedule_date=NULL` — no
schedule, no 500. All three technicians were then restored to active through the endpoint and the
DB re-checked (`1,1,1`).


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| auto-assign with 0 active technicians | `POST /planning/schedule plan_ids=22 auto_assign=on (all 3 technicians inactive)` | 303 | No active technicians available to auto-assign. | plan status=draft personnel_id=NULL wo_no=NULL schedule_date=NULL | **FIXED** | `.qa/evidence/verify_item2_no_technicians.html` |
| restore 3 technicians to active | `POST /setup/personnel is_active=on x3` | 303 | restored | is_active=['1', '1', '1'] | **FIXED** | `.qa/evidence/verify_item2_personnel_restored.html` |

---

## Item 3 — Equipment without a Location / with an empty Customer or Field

**Verdict: FIXED**

**Original trigger:** `POST /setup/equipment` with a missing/invalid location or a broken
customer/field/location chain (HTTP 500, or raw JSON 422 for empty numeric fields).

**Requests:** seven variants — `location_id=0`, `location_id=""`, `customer_id=""`,
`field_id=999999`, `location_id=999999`, a field belonging to a *different* customer
(`customer=1, field=<field of QA-VERIFY-CUST-X>`), and a location belonging to a different field
(`field=1, location=2`). All used tag `QA-VERIFY-EQ-BAD`.

**Observed:** all seven returned **303** (never JSON), each with a friendly flash
(`Please choose a location/field that belongs to…`, `Please choose a customer.`). The empty-string
numeric cases were coerced cleanly instead of raising a raw 422. `select count(*) from equipment
where tag1='QA-VERIFY-EQ-BAD'` was `0` before and after every attempt — no row created.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| location_id=0 | `POST /setup/equipment {'customer_id': 1, 'field_id': 1, 'location_id': 0, 'tag1': 'QA-VERIFY-EQ-BAD'}` | 303 | Please choose a location that belongs to the selected field. | rows with tag QA-VERIFY-EQ-BAD=0 (before=0); content-type=''; location='/setup/equipment' | **FIXED** | `.qa/evidence/verify_item3_case1.html` |
| location_id='' (empty string -> int coercion) | `POST /setup/equipment {'customer_id': 1, 'field_id': 1, 'location_id': '', 'tag1': 'QA-VERIFY-EQ-BAD'}` | 303 | Please choose a location that belongs to the selected field. | rows with tag QA-VERIFY-EQ-BAD=0 (before=0); content-type=''; location='/setup/equipment' | **FIXED** | `.qa/evidence/verify_item3_case2.html` |
| customer_id='' (empty string -> int coercion) | `POST /setup/equipment {'customer_id': '', 'field_id': 1, 'location_id': 1, 'tag1': 'QA-VERIFY-EQ-BAD'}` | 303 | Please choose a customer. | rows with tag QA-VERIFY-EQ-BAD=0 (before=0); content-type=''; location='/setup/equipment' | **FIXED** | `.qa/evidence/verify_item3_case3.html` |
| field_id=999999 (non-existent) | `POST /setup/equipment {'customer_id': 1, 'field_id': 999999, 'location_id': 1, 'tag1': 'QA-VERIFY-EQ-BAD'}` | 303 | Please choose a field that belongs to the selected customer. | rows with tag QA-VERIFY-EQ-BAD=0 (before=0); content-type=''; location='/setup/equipment' | **FIXED** | `.qa/evidence/verify_item3_case4.html` |
| location_id=999999 (non-existent) | `POST /setup/equipment {'customer_id': 1, 'field_id': 1, 'location_id': 999999, 'tag1': 'QA-VERIFY-EQ-BAD'}` | 303 | Please choose a location that belongs to the selected field. | rows with tag QA-VERIFY-EQ-BAD=0 (before=0); content-type=''; location='/setup/equipment' | **FIXED** | `.qa/evidence/verify_item3_case5.html` |
| mismatched customer/field (customer=1, field=11 of customer 14) | `POST /setup/equipment {'customer_id': 1, 'field_id': '11', 'location_id': 1, 'tag1': 'QA-VERIFY-EQ-BAD'}` | 303 | Please choose a field that belongs to the selected customer. | rows with tag QA-VERIFY-EQ-BAD=0 (before=0); content-type=''; location='/setup/equipment' | **FIXED** | `.qa/evidence/verify_item3_case6.html` |
| mismatched field/location (field=1, location=2 belongs to field 2) | `POST /setup/equipment {'customer_id': 1, 'field_id': 1, 'location_id': 2, 'tag1': 'QA-VERIFY-EQ-BAD'}` | 303 | Please choose a location that belongs to the selected field. | rows with tag QA-VERIFY-EQ-BAD=0 (before=0); content-type=''; location='/setup/equipment' | **FIXED** | `.qa/evidence/verify_item3_case7.html` |

---

## Item 4 — Unchecked “Active” on create and edit

**Verdict: FIXED**

**Original trigger:** the “Active” checkbox was ignored on create *and* edit, so unticking
it did nothing.

**Equipment (`QA-VERIFY-EQ-INACT`, `QA-VERIFY-EQ-ACT`):** create with `is_active` absent → DB
`is_active=0`; create with `is_active=on` → `=1`; then `POST /setup/equipment` with
`equipment_id=<id>` and no `is_active` → DB flips to `0` and
`GET /setup/equipment?edit=<id>` re-renders **“Save changes”** with the `is_active` checkbox
**unticked** (`checked=False`, verified by parsing the input tag).

**Personnel (`QA-VERIFY-INACT`, `QA-VERIFY-ACT`):** identical three-step result — omitted → `0`,
`on` → `1`, edit omitting the box → `0` and the edit form shows “Save changes” with the
checkbox unticked.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| equipment create, is_active omitted | `POST /setup/equipment ... tag1=QA-VERIFY-EQ-INACT (no is_active)` | 303 | Equipment 'QA-VERIFY-EQ-INACT' added. | equipment id=36 is_active=0 | **FIXED** | `.qa/evidence/verify_item4_equipment_create.html` |
| equipment create, is_active=on | `POST /setup/equipment ... tag1=QA-VERIFY-EQ-ACT is_active=on` | 303 | Equipment 'QA-VERIFY-EQ-ACT' added. | equipment id=37 is_active=1 | **FIXED** | `.qa/evidence/verify_item4_equipment_create.html` |
| equipment edit, is_active omitted | `POST /setup/equipment equipment_id=37 (no is_active)` | 303 | Equipment 'QA-VERIFY-EQ-ACT' updated. | is_active=0; edit form 'Save changes'=True; is_active checkbox checked=False | **FIXED** | `.qa/evidence/verify_item4_equipment_edit.html` |
| personnel create, is_active omitted | `POST /setup/personnel first_name=QA-VERIFY-INACT last_name=TECH (no is_active)` | 303 | Technician 'QA-VERIFY-INACT TECH' added. | personnel id=8 is_active=0 | **FIXED** | `.qa/evidence/verify_item4_personnel_create.html` |
| personnel create, is_active=on | `POST /setup/personnel first_name=QA-VERIFY-ACT last_name=TECH is_active=on` | 303 | Technician 'QA-VERIFY-ACT TECH' added. | personnel id=9 is_active=1 | **FIXED** | `.qa/evidence/verify_item4_personnel_create.html` |
| personnel edit, is_active omitted | `POST /setup/personnel personnel_id=9 (no is_active)` | 303 | Technician 'QA-VERIFY-ACT TECH' updated. | is_active=0; edit form 'Save changes'=True; is_active checkbox checked=False | **FIXED** | `.qa/evidence/verify_item4_personnel_edit.html` |

---

## Item 5 — Over-long values

**Verdict: FIXED**

**Original trigger:** posting a value longer than its DB column raised
`Data too long for column` → HTTP 500.

**Requests (all expected 303 + friendly flash, no row):** customer/field/location/vendor name
129 chars; service code 33 chars; equipment tag1 65 chars; technician first name 65 chars; user
display name 129 chars. Additionally the other guarded columns: equipment tag2 65, description 256,
manufacturer 129; service name 129, discipline 65; vendor phone 65, email 136; technician position
33, discipline 65.

**Observed:** every over-long post returned **303** with an explicit
`<field> must be N characters or fewer.` flash, `content-type` was never JSON, and a
`count(*) … where <col>=<value>` immediately after every attempt was `0` — no partial row.

**Boundary controls (must *succeed*, not over-reject):** names/codes/tags exactly at the limit
(customer 128, field 128, location 128, vendor 128, service code 32, tag1 64, technician first
name 64, user display name 128) were all accepted and created (`rows=1`). The guard is not
off-by-one.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| customer name 129 chars | `POST /setup/customers {'name': 'AAAAAAAAAAAAAAAAAAAA…'}` | 303 | Customer name must be 128 characters or fewer. | customers matching rows before=0 after=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_case1.html` |
| field name 129 chars | `POST /setup/fields {'name': 'AAAAAAAAAAAAAAAAAAAA…', 'customer_id': 1}` | 303 | Field name must be 128 characters or fewer. | fields matching rows before=0 after=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_case2.html` |
| location name 129 chars | `POST /setup/locations {'name': 'AAAAAAAAAAAAAAAAAAAA…', 'field_id': 1}` | 303 | Location must be 128 characters or fewer. | locations matching rows before=0 after=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_case3.html` |
| vendor name 129 chars | `POST /setup/vendors {'name': 'AAAAAAAAAAAAAAAAAAAA…'}` | 303 | Vendor name must be 128 characters or fewer. | vendors matching rows before=0 after=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_case4.html` |
| service code 33 chars | `POST /setup/services {'code': 'CCCCCCCCCCCCCCCCCCCC…', 'name': 'QA-VERIFY-LONG'}` | 303 | Service code must be 32 characters or fewer. | services matching rows before=0 after=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_case5.html` |
| equipment tag1 65 chars | `POST /setup/equipment {'customer_id': 1, 'field_id': 1, 'location_id': 1, 'tag1': 'BBBBBBBBBBBBBBBBBBBB…', 'is_active': 'on'}` | 303 | Tag 1 must be 64 characters or fewer. | equipment matching rows before=0 after=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_case6.html` |
| technician first name 65 chars | `POST /setup/personnel {'first_name': 'BBBBBBBBBBBBBBBBBBBB…', 'last_name': 'QA-VERIFY-LONG', 'is_active': 'on'}` | 303 | First name must be 64 characters or fewer. | personnel matching rows before=0 after=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_case7.html` |
| user display name 129 chars | `POST /users username=QA-VERIFY-LONGUSER display_name=<129 chars> password=secret123` | 303 | Display name must be 128 characters or fewer. | users matching before=0 after=0 | **FIXED** | `.qa/evidence/verify_item5_user_display.html` |
| customer name exactly 128 | `POST /setup/customers (length exactly at the column limit)` | 303 | Customer 'QA-VERIFY-ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ' added. | customers.name rows=1 | **FIXED** | `.qa/evidence/verify_item5_bound1.html` |
| field name exactly 128 | `POST /setup/fields (length exactly at the column limit)` | 303 | Field 'QA-VERIFY-YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY' added. | fields.name rows=1 | **FIXED** | `.qa/evidence/verify_item5_bound2.html` |
| location name exactly 128 | `POST /setup/locations (length exactly at the column limit)` | 303 | Location 'QA-VERIFY-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX' added. | locations.name rows=1 | **FIXED** | `.qa/evidence/verify_item5_bound3.html` |
| vendor name exactly 128 | `POST /setup/vendors (length exactly at the column limit)` | 303 | Vendor 'QA-VERIFY-WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW' added. | vendors.name rows=1 | **FIXED** | `.qa/evidence/verify_item5_bound4.html` |
| service code exactly 32 | `POST /setup/services (length exactly at the column limit)` | 303 | Service 'QA-VERIFY-ZZZZZZZZZZZZZZZZZZZZZZ' added. | services.code rows=1 | **FIXED** | `.qa/evidence/verify_item5_bound5.html` |
| equipment tag1 exactly 64 | `POST /setup/equipment (length exactly at the column limit)` | 303 | Equipment 'QA-VERIFY-ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ' added. | equipment.tag1 rows=1 | **FIXED** | `.qa/evidence/verify_item5_bound6.html` |
| technician first name exactly 64 | `POST /setup/personnel (length exactly at the column limit)` | 303 | Technician 'QA-VERIFY-ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ QA-VERIFY-BOUND' added. | personnel.first_name rows=1 | **FIXED** | `.qa/evidence/verify_item5_bound7.html` |
| user display name exactly 128 | `POST /users display_name=<128 chars>` | 303 | User 'QA-VERIFY-BOUNDU' created. | users rows=1 | **FIXED** | `.qa/evidence/verify_item5_bound_user.html` |
| equipment tag2 65 chars | `POST /setup/equipment (over-long value)` | 303 | Tag 2 must be 64 characters or fewer. | equipment matching rows=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_extra1.html` |
| equipment description 256 chars | `POST /setup/equipment (over-long value)` | 303 | Description must be 255 characters or fewer. | equipment matching rows=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_extra2.html` |
| equipment manufacturer 129 chars | `POST /setup/equipment (over-long value)` | 303 | Manufacturer must be 128 characters or fewer. | equipment matching rows=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_extra3.html` |
| service name 129 chars | `POST /setup/services (over-long value)` | 303 | Service name must be 128 characters or fewer. | services matching rows=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_extra4.html` |
| service discipline 65 chars | `POST /setup/services (over-long value)` | 303 | Discipline must be 64 characters or fewer. | services matching rows=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_extra5.html` |
| vendor phone 65 chars | `POST /setup/vendors (over-long value)` | 303 | Phone must be 64 characters or fewer. | vendors matching rows=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_extra6.html` |
| technician position 33 chars | `POST /setup/personnel (over-long value)` | 303 | Position must be 32 characters or fewer. | personnel matching rows=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_extra8.html` |
| technician discipline 65 chars | `POST /setup/personnel (over-long value)` | 303 | Discipline must be 64 characters or fewer. | personnel matching rows=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_extra9.html` |
| vendor email 136 chars | `POST /setup/vendors name=QA-VERIFY-OVR-V3 email=<136 chars>` | 303 | Email must be 128 characters or fewer. | vendors matching rows=0; content-type='' | **FIXED** | `.qa/evidence/verify_item5_email_overlong.html` |

---

## Item 6 — Rename to a duplicate unique value

**Verdict: FIXED**

**Original trigger:** renaming a row onto another row's unique name raised
`IntegrityError 1062` → HTTP 500.

**Requests:** two customers, two service codes, two vendors; then `POST` the first with the second's
name/code and its own id, then a case-variant duplicate (`qa-verify-dup-b`), then a legitimate
rename.

**Observed:** every duplicate attempt returned **303** with
`Customer/Vendor '…' already exists.` (also for the case-variant, i.e. the `lower()` guard works),
and both rows were unchanged in the DB. Duplicate-on-*create* (no id supplied) is caught too.
The follow-up legitimate rename returned **303** with `… updated.` and the new value in the DB.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| customer rename onto duplicate | `POST /setup/customers customer_id=16 name=QA-VERIFY-DUP-B` | 303 | Customer 'QA-VERIFY-DUP-B' already exists. | A='QA-VERIFY-DUP-A' B='QA-VERIFY-DUP-B' | **FIXED** | `.qa/evidence/verify_item6_customer_dup.html` |
| customer rename onto case-variant duplicate | `POST /setup/customers customer_id=16 name=qa-verify-dup-b` | 303 | Customer 'qa-verify-dup-b' already exists. | A='QA-VERIFY-DUP-A' | **FIXED** | `.qa/evidence/verify_item6_customer_dup_case.html` |
| customer legitimate rename | `POST /setup/customers customer_id=16 name=QA-VERIFY-DUP-A2` | 303 | Customer updated. | A='QA-VERIFY-DUP-A2' | **FIXED** | `.qa/evidence/verify_item6_customer_ok.html` |
| service rename onto duplicate code | `POST /setup/services service_id=23 code=QA-VERIFY-SVC-B` | 303 | Service code 'QA-VERIFY-SVC-B' already exists. | A='QA-VERIFY-SVC-A' B='QA-VERIFY-SVC-B' | **FIXED** | `.qa/evidence/verify_item6_service_dup.html` |
| service legitimate rename | `POST /setup/services service_id=23 code=QA-VERIFY-SVC-A2` | 303 | Service 'QA-VERIFY-SVC-A2' updated. | A='QA-VERIFY-SVC-A2' | **FIXED** | `.qa/evidence/verify_item6_service_ok.html` |
| vendor rename onto duplicate | `POST /setup/vendors vendor_id=8 name=QA-VERIFY-VEND-B` | 303 | Vendor 'QA-VERIFY-VEND-B' already exists. | A='QA-VERIFY-VEND-A' B='QA-VERIFY-VEND-B' | **FIXED** | `.qa/evidence/verify_item6_vendor_dup.html` |
| vendor legitimate rename | `POST /setup/vendors vendor_id=8 name=QA-VERIFY-VEND-A2` | 303 | Vendor 'QA-VERIFY-VEND-A2' updated. | A='QA-VERIFY-VEND-A2' | **FIXED** | `.qa/evidence/verify_item6_vendor_ok.html` |
| customer create with an existing name | `POST /setup/customers name=QA-VERIFY-DUP-A2 (no customer_id)` | 303 | Customer 'QA-VERIFY-DUP-A2' already exists. | rows=1 | **FIXED** | `.qa/evidence/verify_item6_customer_dup_create.html` |

---

## Item 7 — Silent cascade delete

**Verdict: FIXED**

**Original trigger:** deleting a customer silently cascaded (or 500'd) and destroyed the field /
location chain.

**Requests:** created customer → field → location (`QA-VERIFY-CASC-3`), then
`POST /setup/customers/{cid}/delete`; then `POST /setup/fields/{fid}/delete`; then unwound
location → field → customer; separately created a chain + equipment
(`QA-VERIFY-CASC-EQ`) and deleted its location.

**Observed:** the customer delete was **refused** — 303 + `Cannot delete 'Customer '…'': it still
has dependent records.` with customer **and** field **and** location all still present. The field
delete was likewise refused while the location existed (location survived). Deleting the leaf
location then the field then the customer each returned 303 with a `… deleted.` success flash and
`count(*)=0`. Deleting a location that still holds equipment was refused with
`… dependent records.` and both rows survived.

**Harness note (not an app failure):** `_safe_delete` redirects to `safe_back(request, "/setup")`,
which needs a browser `Referer`; with no Referer the 303 lands on `/setup`, a route that does not
exist (404), and `error.html` does not render the one-shot flash. Re-running with a browser-like
`Referer: /setup/customers` showed the flash. All results above use the Referer header.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| delete customer that still has a field/location | `POST /setup/customers/21/delete (Referer /setup/customers)` | 303 | Cannot delete 'Customer 'QA-VERIFY-CUST-CASC-3'': it still has dependent records. | redirect='/setup/customers'; customer=1 field=1 location=1 | **FIXED** | `.qa/evidence/verify_item7_delete_customer_blocked.html` |
| delete field that still has a location | `POST /setup/fields/15/delete (Referer /setup/fields)` | 303 | Cannot delete 'Field 'QA-VERIFY-FIELD-CASC-3'': it still has dependent records. | redirect='/setup/fields'; field=1 location=1 | **FIXED** | `.qa/evidence/verify_item7_delete_field_blocked.html` |
| delete location (leaf) | `POST /setup/locations/14/delete (Referer /setup/locations)` | 303 | Location 'QA-VERIFY-LOC-CASC-3' deleted. | location rows=0 | **FIXED** | `.qa/evidence/verify_item7_delete_location_ok.html` |
| delete field after its location is gone | `POST /setup/fields/15/delete` | 303 | Field 'QA-VERIFY-FIELD-CASC-3' deleted. | field rows=0 | **FIXED** | `.qa/evidence/verify_item7_delete_field_ok.html` |
| delete customer after its field is gone | `POST /setup/customers/21/delete` | 303 | Customer 'QA-VERIFY-CUST-CASC-3' deleted. | customer rows=0 | **FIXED** | `.qa/evidence/verify_item7_delete_customer_ok.html` |
| delete location that still has equipment | `POST /setup/locations/15/delete` | 303 | Cannot delete 'Location 'QA-VERIFY-LOC-CASC-4'': it still has dependent records. | location=1 equipment=1 | **FIXED** | `.qa/evidence/verify_item7_delete_location_with_equipment.html` |

---

## Item 8 — Non-existent FK ids

**Verdict: FIXED**

**Original trigger:** supplying a FK id that does not exist (HTTP 500 / raw validation error).

**Requests:** `POST /setup/fields customer_id=999999`; `POST /setup/locations field_id=999999`;
`POST /planning/schedule plan_ids=<draft> vendor_id=999999`; the same with `personnel_id=999999`;
`POST /planning/closeout plan_ids=<scheduled> actual_personnel_id=999999`; and
`actual_vendor_id=999999`.

**Observed:** all six returned **303** with a friendly flash
(`Please choose an existing customer/field/service vendor/technician.`). No field/location row was
created, and the draft plan stayed `draft` (no `schedule_date`/`wo_no`) while the scheduled plan
stayed `scheduled` with unchanged `actual_date`/`personnel_id` — zero state change.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| field with customer_id=999999 | `POST /setup/fields name=QA-VERIFY-FK-F customer_id=999999` | 303 | Please choose an existing customer. | fields matching=0 | **FIXED** | `.qa/evidence/verify_item8_field_fk.html` |
| location with field_id=999999 | `POST /setup/locations name=QA-VERIFY-FK-L field_id=999999` | 303 | Please choose an existing field. | locations matching=0 | **FIXED** | `.qa/evidence/verify_item8_location_fk.html` |
| schedule with vendor_id=999999 | `POST /planning/schedule plan_ids=22 vendor_id=999999` | 303 | Please choose an existing service vendor. | before=['draft', 'NULL', 'NULL', 'NULL', 'NULL'] after=['draft', 'NULL', 'NULL', 'NULL', 'NULL'] | **FIXED** | `.qa/evidence/verify_item8_schedule_vendor_fk.html` |
| schedule with personnel_id=999999 | `POST /planning/schedule plan_ids=22 personnel_id=999999` | 303 | Please choose an existing technician. | after=['draft', 'NULL', 'NULL', 'NULL', 'NULL'] | **FIXED** | `.qa/evidence/verify_item8_schedule_personnel_fk.html` |
| closeout with actual_personnel_id=999999 | `POST /planning/closeout plan_ids=17 actual_personnel_id=999999` | 303 | Please choose an existing technician. | before=['scheduled', 'NULL', '1'] after=['scheduled', 'NULL', '1'] | **FIXED** | `.qa/evidence/verify_item8_closeout_personnel_fk.html` |
| closeout with actual_vendor_id=999999 | `POST /planning/closeout plan_ids=17 actual_vendor_id=999999` | 303 | Please choose an existing service vendor. | after=['scheduled', 'NULL', '1'] | **FIXED** | `.qa/evidence/verify_item8_closeout_vendor_fk.html` |

---

## Item 9 — Invalid dates

**Verdict: FIXED**

**Original trigger:** an unparseable date was silently replaced with today's date.

**Requests:** `POST /planning/schedule` with `schedule_date=garbage` on a draft plan;
`POST /planning/closeout` with `actual_date=31/12/2026` on a scheduled plan;
`POST /planning/draft/add` with `proposed_date_override=garbage`.

**Observed:** each returned **303** with the flash
`Please enter dates in YYYY-MM-DD format.` and **no state change**: the draft row stayed
`draft, NULL, NULL, NULL`; the scheduled row kept `status=scheduled, actual_date=NULL`; and the
draft-add created no plan row (`before=0 after=0`). The flash names the required format.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| schedule with schedule_date=garbage | `POST /planning/schedule plan_ids=22 schedule_date=garbage` | 303 | Please enter dates in YYYY-MM-DD format. | before=['draft', 'NULL', 'NULL', 'NULL'] after=['draft', 'NULL', 'NULL', 'NULL'] | **FIXED** | `.qa/evidence/verify_item9_schedule_bad_date.html` |
| closeout with actual_date=31/12/2026 | `POST /planning/closeout plan_ids=17 actual_date=31/12/2026` | 303 | Please enter dates in YYYY-MM-DD format. | before=['scheduled', 'NULL', '2026-10-01'] after=['scheduled', 'NULL', '2026-10-01'] | **FIXED** | `.qa/evidence/verify_item9_closeout_bad_date.html` |
| draft add with proposed_date_override=garbage | `POST /planning/draft/add service_id=7 equipment_ids=41 proposed_date_override=garbage` | 303 | Please enter dates in YYYY-MM-DD format. | plan rows for (eq=41,svc=7) before=0 after=0 | **FIXED** | `.qa/evidence/verify_item9_draft_bad_date.html` |

---

## Item 10 — Duplicate draft rows

**Verdict: STILL BROKEN**

**Original trigger:** adding the same equipment + service twice used to create two draft rows.

**Requests:** `POST /planning/draft/add service_id=5 equipment_ids=<QA-VERIFY-EQ-DUP>` **twice**,
then (crafted) one request with the same id repeated in the `equipment_ids` list.

**Observed (two submissions — the documented trigger):** first call 303
`Added 1 item(s) to the draft plan.` and exactly one row; second call 303
`Added 0 item(s) to the draft plan. 1 selection(s) skipped — already open or unknown equipment.`
and still exactly one row. **This part is fixed.**

**Counterexample (single crafted request):** `POST /planning/draft/add service_id=4
equipment_ids=[43,43]` returned **303 `Added 2 item(s) to the draft plan.`** and the DB then held
**two** draft rows for the same equipment+service (`plans.id 24 and 25`, both
`equipment_id=43 service_id=4 status=draft`). `already_open` is snapshotted *before* the loop, so a
repeated id inside one submission bypasses the guard. Not reachable from the rendered form (each
active equipment renders one checkbox, so a browser sends each id once), but the duplicate-row
invariant does not hold. Filed as V-FLOW-001.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| same equipment+service added twice (two requests) | `POST /planning/draft/add service_id=5 equipment_ids=42 x2` | 303 | Added 0 item(s) to the draft plan. 1 selection(s) skipped — already open or unknown equipment. | rows after 1st=1 after 2nd=1; first flash='Added 1 item(s) to the draft plan.' | **FIXED** | `.qa/evidence/verify_item10_second_add.html` |
| same equipment+service twice inside ONE request (crafted repeated field) | `POST /planning/draft/add service_id=4 equipment_ids=[43,43]` | 303 | Added 2 item(s) to the draft plan. | plan rows=2 | **STILL BROKEN** | `.qa/evidence/verify_item10_inrequest_duplicate.html` |

---

## Item 11 — Cancel (new action)

**Verdict: FIXED**

**New action, no prior trigger.**

**Requests:** `POST /planning/cancel plan_ids=<scheduled QA plan>`; then a draft id.

**Observed:** **303** + `Cancelled 1 item(s).`; DB `status=cancelled`; the item's tag disappeared
from `/planning/final`; it appeared in `/history` carrying
`<span class="chip chip-cancelled">cancelled</span>`; and both
`GET /reports/work-order/{id}` and `GET /reports/calibration/{id}` still returned **200** (the
work-order/calibration links on the History row keep working after cancel). Cancelling a *draft*
id returned 303 with `Select at least one scheduled item to cancel.` and the row stayed `draft`.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| cancel a scheduled item | `POST /planning/cancel plan_ids=21` | 303 | Cancelled 1 item(s). | status=cancelled; tag in /planning/final=False; tag in /history=True; chip-cancelled=True; work-order=200; calibration=200 | **FIXED** | `.qa/evidence/verify_item11_cancel.html` |
| cancel a draft id (no-op) | `POST /planning/cancel plan_ids=22` | 303 | Select at least one scheduled item to cancel. | status still=draft | **FIXED** | `.qa/evidence/verify_item11_cancel_draft.html` |

---

## Item 12 — Missing / stale record ids

**Verdict: FIXED**

**Original trigger:** a stale/missing `*_id` on an edit form was a silent no-op.

**Requests:** “Save changes” with `customer_id=424242` (customers), `field_id=424242` (fields),
`location_id=424242` (locations), `equipment_id=424242` (equipment), `service_id=424242` (services),
`vendor_id=424242` (vendors), `personnel_id=424242` (personnel); plus
`POST /users/424242/reset-password password=verify123`.

**Observed:** all eight returned **303** with the matching flash — `Customer not found.`,
`Field not found.`, `Location not found.`, `Equipment not found.`, `Service not found.`,
`Vendor not found.`, `Technician not found.`, `User not found.` — and a `count(*)` on the
matching key before/after was unchanged (0) in every case.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| stale customer_id | `POST /setup/customers <customer_id=424242>` | 303 | Customer not found. | customers rows before=0 after=0; expected flash 'Customer not found.' | **FIXED** | `.qa/evidence/verify_item12_customers.html` |
| stale field_id | `POST /setup/fields <field_id=424242>` | 303 | Field not found. | fields rows before=0 after=0; expected flash 'Field not found.' | **FIXED** | `.qa/evidence/verify_item12_fields.html` |
| stale location_id | `POST /setup/locations <location_id=424242>` | 303 | Location not found. | locations rows before=0 after=0; expected flash 'Location not found.' | **FIXED** | `.qa/evidence/verify_item12_locations.html` |
| stale equipment_id | `POST /setup/equipment <equipment_id=424242>` | 303 | Equipment not found. | equipment rows before=0 after=0; expected flash 'Equipment not found.' | **FIXED** | `.qa/evidence/verify_item12_equipment.html` |
| stale service_id | `POST /setup/services <service_id=424242>` | 303 | Service not found. | services rows before=0 after=0; expected flash 'Service not found.' | **FIXED** | `.qa/evidence/verify_item12_services.html` |
| stale vendor_id | `POST /setup/vendors <vendor_id=424242>` | 303 | Vendor not found. | vendors rows before=0 after=0; expected flash 'Vendor not found.' | **FIXED** | `.qa/evidence/verify_item12_vendors.html` |
| stale personnel_id | `POST /setup/personnel <personnel_id=424242>` | 303 | Technician not found. | personnel rows before=0 after=0; expected flash 'Technician not found.' | **FIXED** | `.qa/evidence/verify_item12_personnel.html` |
| reset-password for a missing user | `POST /users/424242/reset-password password=verify123` | 303 | User not found. | redirect='/users' | **FIXED** | `.qa/evidence/verify_item12_reset_password_404.html` |

---

## Item 13 — Error surfaces

**Verdict: FIXED**

**Checks:**

* `GET /no/such/page` → **404**, `text/html; charset=utf-8`, styled error page containing `404`.
* `POST /setup/customers/abc/delete` → **303** (not JSON 422); the `RequestValidationError`
  handler flashed `That form was incomplete or invalid …` and redirected to `/setup/customers`.
* `GET /setup/equipment?edit=abc` → **200** with the list *and* the add form rendered
  (`Add equipment` present), i.e. the garbage `?edit=` is tolerated.
* Non-admin: created `QA-VERIFY-USER1` (role `user`), logged in as that account and
  `GET /users` → **403** HTML containing `403` (admin `GET /users` was 200). The temporary user
  was then deleted and the DB confirmed `remaining=0`.
* `GET /logout` (POST-only route) → **405** HTML containing `405`.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| unknown URL | `GET /no/such/page` | 404 | — | content-type='text/html; charset=utf-8'; contains '404'=True | **FIXED** | `.qa/evidence/verify_item13_unknown_url.html` |
| non-integer id in delete path | `POST /setup/customers/abc/delete` | 303 | That form was incomplete or invalid — please check the fields and try again. | redirect='/setup/customers'; content-type='' | **FIXED** | `.qa/evidence/verify_item13_delete_nonint_id.html` |
| garbage ?edit= value | `GET /setup/equipment?edit=abc` | 200 | — | list+form rendered=True; bytes=17254 | **FIXED** | `.qa/evidence/verify_item13_edit_garbage.html` |
| non-admin GET /users | `GET /users as QA-VERIFY-USER1 (role=user)` | 403 | — | created=1; admin GET /users=200; content-type='text/html; charset=utf-8'; '403' in body=True | **FIXED** | `.qa/evidence/verify_item13_nonadmin_users.html` |
| GET /logout (POST-only route) | `GET /logout` | 405 | — | content-type='text/html; charset=utf-8'; '405' in body=True | **FIXED** | `.qa/evidence/verify_item13_get_logout.html` |
| delete temporary non-admin user | `DELETE FROM users WHERE username='QA-VERIFY-USER1'` | 0 | — | remaining=0 | **FIXED** | `.qa/evidence/verify_item13_nonadmin_users.html` |

---

## Item cleanup — Cleanup and baseline restoration

**Verdict: FIXED**

All rows created by this pass (prefix `QA-VERIFY-`) were deleted in FK-safe order
(plans → equipment → locations → fields → customers, then services, vendors, personnel,
users) and the three seeded technicians were re-asserted active.

**Final state (re-checked after the concurrent sibling verifier finished):** customers **1**,
fields **2**, locations **2**, equipment **5**, services **8**, vendors **3**, personnel **3**,
plans **3**, users **1** (`admin` only), and **zero** `QA-VERIFY-` rows in any table. The three
seeded draft plans are still `draft` with `wo_no`/`cm_no`/`personnel_id` NULL and technicians
1–3 are `is_active=1`.

At the instant of my own cleanup a concurrent sibling verifier's row (`QA-REGR-navuser`, id 9,
prefix `QA-REGR-`) was still present; it was deliberately left untouched and the sibling removed
it shortly afterwards.


**Recorded checks**

| check | request | HTTP | flash | DB state | verdict | evidence |
|---|---|---|---|---|---|---|
| QA rows removed | `DELETE ... LIKE 'QA-VERIFY-%'` | 0 | — | after={'customers': 1, 'fields': 2, 'locations': 2, 'equipment': 5, 'services': 8, 'vendors': 3, 'personnel': 3, 'plans': 3, 'users': 2} | **FIXED** | `` |
| seeded draft plans 1-3 untouched | `select id,status,wo_no,cm_no,personnel_id from plans` | 0 | — | id	status	wo_no	cm_no	personnel_id \| 1	draft	NULL	NULL	NULL \| 2	draft	NULL	NULL	NULL \| 3	draft	NULL	NULL	NULL | **FIXED** | `` |
| seeded technicians active | `select id,is_active from personnel where id in (1,2,3)` | 0 | — | id	is_active \| 1	1 \| 2	1 \| 3	1 | **FIXED** | `` |
| baseline table counts | `count(*) on all tables` | 0 | — | {'customers': 1, 'fields': 2, 'locations': 2, 'equipment': 5, 'services': 8, 'vendors': 3, 'personnel': 3, 'plans': 3, 'users': 2}; users table=id	username	role \| 1	admin	admin \| 9	QA-REGR-navuser	user | **CHECK** | `` |
| final baseline re-check | `count(*) across all tables + QA-VERIFY- scan` | 0 | — | {'customers': 1, 'fields': 2, 'locations': 2, 'equipment': 5, 'services': 8, 'vendors': 3, 'personnel': 3, 'plans': 3, 'users': 1}; QA-VERIFY- rows=0; users=id	username	role \| 1	admin	admin | **FIXED** | `` |
| final seeded-plan re-check | `select id,status,wo_no,cm_no,personnel_id from plans` | 0 | — | id	status	wo_no	cm_no	personnel_id \| 1	draft	NULL	NULL	NULL \| 2	draft	NULL	NULL	NULL \| 3	draft	NULL	NULL	NULL | **FIXED** | `` |

---

## Server-log analysis (500 / traceback window)

Run window: **2026-10-01 12:11:22Z – 12:15:40Z**. `docker logs pmsys-app-1 --timestamps`
was captured before the first request and again after cleanup.

| time (UTC) | request | exception | who |
|---|---|---|---|
| 12:11:13.83 | `POST /users` 500 | `ValueError: password cannot be longer than 72 bytes` (auth.py:6 `hash_password`) | pre-existing, before my first request |
| 12:11:14.05 | `POST /account/password` 500 | same | pre-existing, before my first request |
| 12:13:52.79 | `POST /account/password` 500 | same | concurrent sibling verifier |
| 12:13:52.81 | `POST /users` 500 | same | concurrent sibling verifier |
| 12:13:52.83 | `POST /users/7/reset-password` 500 | same | concurrent sibling verifier |
| 12:15:25.94 | `POST /users` 500 | same | concurrent sibling verifier |

**No traceback in the window is attributable to this pass.** This pass never called
`/account/password`; its only `POST /users` calls (item 5 long display name, item 13 non-admin
user, item 5 boundary user) all returned **303**; its only reset-password call was
`POST /users/424242/reset-password`, which returned **303** `User not found.` (the 500 was for
`/users/7`, a user created and deleted by the sibling). Every request this pass issued returned
303 / 200 / 403 / 404 / 405. This is a shared live instance: another verifier is exercising the
password endpoints concurrently, which is where all four post-baseline tracebacks come from.
Timestamp string-filtering confirms the **last** 500 line in the container log is
`12:15:25.941Z` and there are **zero** after it (note: `docker logs --since <naive-ISO>` did not
filter as expected on this host, so the check was done by string comparison).

**Cross-cutting observation (outside the 13 assigned items, logged for the parent):** the fixed
code still 500s when a password longer than bcrypt's 72-byte limit is submitted to
`POST /users`, `POST /account/password` or `POST /users/{id}/reset-password`:
`app/auth.py:6 hash_password` → `ValueError: password cannot be longer than 72 bytes`. Direct
log evidence is in `.qa/evidence/verify_logs_tracebacks.txt`. I did **not** reproduce it myself
(deliberately, to keep this pass's own traceback count at zero); it is confirmed from the
timestamped server tracebacks. Filed as V-FLOW-002; it most likely belongs to the auth verifier.

