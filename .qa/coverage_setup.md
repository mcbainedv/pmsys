# QA coverage — Setup CRUD tabs

Target: http://127.0.0.1:8000 (`pmsys-app-1`) — user `admin`. All writes made by QA used the `QA-SETUP-` prefix and were deleted afterwards.

| check | action | result | note |
| --- | --- | --- | --- |
| customers: GET list | `GET /setup/customers` | PASS | HTTP 200 |
| customers: Add form present | `GET /setup/customers` | PASS |  |
| fields: GET list | `GET /setup/fields` | PASS | HTTP 200 |
| fields: Add form present | `GET /setup/fields` | PASS |  |
| locations: GET list | `GET /setup/locations` | PASS | HTTP 200 |
| locations: Add form present | `GET /setup/locations` | PASS |  |
| equipment: GET list | `GET /setup/equipment` | PASS | HTTP 200 |
| equipment: Add form present | `GET /setup/equipment` | PASS |  |
| services: GET list | `GET /setup/services` | PASS | HTTP 200 |
| services: Add form present | `GET /setup/services` | PASS |  |
| vendors: GET list | `GET /setup/vendors` | PASS | HTTP 200 |
| vendors: Add form present | `GET /setup/vendors` | PASS |  |
| personnel: GET list | `GET /setup/personnel` | PASS | HTTP 200 |
| personnel: Add form present | `GET /setup/personnel` | PASS |  |
| customers: Add button creates | `POST /setup/customers name=<new>` | PASS | HTTP 303 loc=/setup/customers flash='Customer &#39;QA-SETUP-CUST-AE399&#39; added.' db_id=2 |
| customers: Edit link prefills | `GET /setup/customers?edit=2` | PASS | hidden=2 value=QA-SETUP-CUST-AE399 |
| customers: Save changes updates | `POST /setup/customers customer_id=<id>` | PASS | HTTP 303 db='name\nQA-SETUP-CUST-AE399-ED' |
| customers: Delete removes row | `POST /setup/customers/2/delete` | PASS | HTTP 303 loc=/ count='0' |
| fields: Add button creates | `POST /setup/fields name=<new> customer_id=1` | PASS | HTTP 303 db_id=3 |
| fields: Edit link prefills | `GET /setup/fields?edit=3` | PASS | hidden=3 selected=True |
| fields: Save changes updates | `POST /setup/fields field_id=<id>` | PASS | HTTP 303 db='name\nQA-SETUP-FIELD-AE399-ED' |
| fields: Delete removes row | `POST /setup/fields/3/delete` | PASS | HTTP 303 loc=/ |
| locations: Add button creates | `POST /setup/locations name=<new> field_id=1` | PASS | HTTP 303 db_id=3 |
| locations: Edit link prefills | `GET /setup/locations?edit=3` | PASS |  |
| locations: Save changes updates | `POST /setup/locations location_id=<id>` | PASS | HTTP 303 db='name\nQA-SETUP-LOC-AE399-ED' |
| locations: Delete removes row | `POST /setup/locations/3/delete` | PASS | HTTP 303 |
| equipment: Add button creates | `POST /setup/equipment tag1=<new>` | PASS | HTTP 303 db='id\tcustomer_id\tfield_id\tlocation_id\tis_active\n11\t1\t1\t1\t1' |
| equipment: Edit link prefills | `GET /setup/equipment?edit=11` | PASS | hidden=11 |
| equipment: Save changes updates | `POST /setup/equipment equipment_id=<id>` | PASS | HTTP 303 db='tag1\tdescription\nQA-SETUP-EQ-AE399-ED\tqa-ed' |
| equipment: Delete removes row | `POST /setup/equipment/11/delete` | PASS | HTTP 303 |
| services: Add button creates | `POST /setup/services code=<new>` | PASS | HTTP 303 db='id\tfrequency_weeks\testimated_hours\n9\t4\t1.5' |
| services: Edit link prefills | `GET /setup/services?edit=9` | PASS |  |
| services: Save changes updates | `POST /setup/services service_id=<id>` | PASS | HTTP 303 db='name\tfrequency_weeks\nQA svc ED\t6' |
| services: Delete removes row | `POST /setup/services/9/delete` | PASS | HTTP 303 |
| vendors: Add button creates | `POST /setup/vendors name=<new>` | PASS | HTTP 303 db_id=4 |
| vendors: Edit link prefills | `GET /setup/vendors?edit=4` | PASS |  |
| vendors: Save changes updates | `POST /setup/vendors vendor_id=<id>` | PASS | HTTP 303 db='name\tcontact_name\nQA-SETUP-VEN-AE399-ED\tQA2' |
| vendors: Delete removes row | `POST /setup/vendors/4/delete` | PASS | HTTP 303 |
| personnel: Add button creates | `POST /setup/personnel last_name=<new>` | PASS | HTTP 303 db_id=4 |
| personnel: Edit link prefills | `GET /setup/personnel?edit=4` | PASS |  |
| personnel: Save changes updates | `POST /setup/personnel personnel_id=<id>` | PASS | HTTP 303 db='last_name\nQA-SETUP-PERS-AE399ED' |
| personnel: Delete removes row | `POST /setup/personnel/4/delete` | PASS | HTTP 303 |
| customers: blank name | `POST /setup/customers name=''` | BUG | F-SETUP-007: HTTP 422 flash='' |
| customers: blank name(whitespace) | `POST /setup/customers name(whitespace)=''` | PASS | HTTP 303 flash='Customer name is required.' |
| fields: blank name | `POST /setup/fields name=''` | BUG | F-SETUP-007: HTTP 422 flash='' |
| locations: blank name | `POST /setup/locations name=''` | BUG | F-SETUP-007: HTTP 422 flash='' |
| equipment: blank tag1 | `POST /setup/equipment tag1=''` | PASS | HTTP 303 flash='Equipment tag (Tag 1) is required.' |
| services: blank code | `POST /setup/services code=''` | BUG | F-SETUP-007: HTTP 422 flash='' |
| services: blank name | `POST /setup/services name=''` | BUG | F-SETUP-007: HTTP 422 flash='' |
| vendors: blank name | `POST /setup/vendors name=''` | BUG | F-SETUP-007: HTTP 422 flash='' |
| personnel: blank first_name | `POST /setup/personnel first_name=''` | BUG | F-SETUP-007: HTTP 422 flash='' |
| personnel: blank last_name | `POST /setup/personnel last_name=''` | BUG | F-SETUP-007: HTTP 422 flash='' |
| fields: placeholder customer_id empty | `POST /setup/fields customer_id=''` | BUG | F-SETUP-008: HTTP 422 ct=application/json body='{"detail":[{"type":"missing","loc":["body","customer_id"],"msg":"Field required","input":n' ev=.qa/evidence/setup_fields_empty_customer_id.json |
| locations: placeholder field_id empty | `POST /setup/locations field_id=''` | BUG | F-SETUP-008: HTTP 422 ct=application/json body='{"detail":[{"type":"missing","loc":["body","field_id"],"msg":"Field required","input":null' ev=.qa/evidence/setup_locations_empty_field_id.json |
| equipment: placeholder customer_id empty | `POST /setup/equipment customer_id=''` | BUG | F-SETUP-008: HTTP 422 ct=application/json body='{"detail":[{"type":"missing","loc":["body","customer_id"],"msg":"Field required","input":n' ev=.qa/evidence/setup_equipment_empty_customer_id.json |
| equipment: placeholder field_id empty | `POST /setup/equipment field_id=''` | BUG | F-SETUP-008: HTTP 422 ct=application/json body='{"detail":[{"type":"missing","loc":["body","field_id"],"msg":"Field required","input":null' ev=.qa/evidence/setup_equipment_empty_field_id.json |
| customers: duplicate name rejected | `POST /setup/customers name=<dup>` | PASS | flash='Customer &#39;QA-SETUP-DUP-54C1C&#39; already exists.' count=1 |
| customers: duplicate name (different case) rejected | `POST /setup/customers name=<dup lower>` | PASS | flash='Customer &#39;qa-setup-dup-54c1c&#39; already exists.' count=1 |
| services: duplicate code rejected | `POST /setup/services code=<dup>` | PASS | flash='Service code &#39;QASD54C1C&#39; already exists.' count=1 |
| vendors: duplicate name rejected | `POST /setup/vendors name=<dup>` | PASS | flash='Vendor &#39;QA-SETUP-DUPV-54C1C&#39; already exists.' count=1 |
| fields: duplicate name within customer | `POST /setup/fields name=<dup>` | GAP | GAP (no finding): duplicate rows created=2 (no server-side check) |
| locations: duplicate name within field | `POST /setup/locations name=<dup>` | GAP | GAP (no finding): duplicate rows created=2 (no server-side check) |
| equipment: duplicate tag1 | `POST /setup/equipment tag1=<dup>` | GAP | GAP (no finding): duplicate rows created=2 (no server-side check) |
| services: frequency_weeks empty | `POST /setup/services frequency_weeks=''` | GAP | HTTP 303 stored=4 flash='Service &#39;QASN2BE30EM&#39; added.' expect=4 (silent default) |
| services: frequency_weeks non-numeric | `POST /setup/services frequency_weeks='abc'` | GAP | HTTP 303 stored=4 flash='Service &#39;QASN2BE30NO&#39; added.' expect=4 (silent default) |
| services: frequency_weeks negative | `POST /setup/services frequency_weeks='-5'` | BUG | F-SETUP-010: HTTP 303 stored=-5 flash='Service &#39;QASN2BE30NE&#39; added.' expect=-5 stored |
| services: frequency_weeks zero | `POST /setup/services frequency_weeks='0'` | GAP | HTTP 303 stored=0 flash='Service &#39;QASN2BE30ZE&#39; added.' expect=0 stored |
| services: frequency_weeks huge | `POST /setup/services frequency_weeks='99999999999'` | BUG | F-SETUP-004: HTTP 500 stored=None flash='' expect=server error? |
| services: frequency_weeks float | `POST /setup/services frequency_weeks='4.7'` | GAP | HTTP 303 stored=4 flash='Service &#39;QASN2BE30FL&#39; added.' expect=4 (truncated) |
| services: estimated_hours non-numeric | `POST /setup/services estimated_hours='abc'` | GAP | HTTP 303 stored='NULL' (silently becomes NULL) |
| services: estimated_hours empty | `POST /setup/services estimated_hours=''` | GAP | HTTP 303 stored='NULL' (silently becomes NULL) |
| customers: over-long name | `POST /setup/customers name=<200 chars>` | BUG | F-SETUP-001: HTTP 500 raw error; evidence=.qa/evidence/setup_customers_long_name.txt |
| services: over-long code | `POST /setup/services code=<200 chars>` | BUG | F-SETUP-001: HTTP 500 raw error; evidence=.qa/evidence/setup_services_long_code.txt |
| equipment: over-long tag1 | `POST /setup/equipment tag1=<200 chars>` | BUG | F-SETUP-001: HTTP 500 raw error; evidence=.qa/evidence/setup_equipment_long_tag1.txt |
| vendors: over-long name | `POST /setup/vendors name=<200 chars>` | BUG | F-SETUP-001: HTTP 500 raw error; evidence=.qa/evidence/setup_vendors_long_name.txt |
| personnel: over-long first_name | `POST /setup/personnel first_name=<200 chars>` | BUG | F-SETUP-001: HTTP 500 raw error; evidence=.qa/evidence/setup_personnel_long_first_name.txt |
| customers: update to duplicate name | `POST /setup/customers customer_id=4 name=<existing>` | BUG | F-SETUP-002: HTTP 500 raw IntegrityError; row unchanged? evidence=.qa/evidence/setup_customers_dupupdate.txt |
| services: update to duplicate code | `POST /setup/services service_id=18 code=<existing>` | BUG | F-SETUP-002: HTTP 500 raw IntegrityError; row unchanged? evidence=.qa/evidence/setup_services_dupupdate.txt |
| vendors: update to duplicate name | `POST /setup/vendors vendor_id=6 name=<existing>` | BUG | F-SETUP-002: HTTP 500 raw IntegrityError; row unchanged? evidence=.qa/evidence/setup_vendors_dupupdate.txt |
| customers: update non-existent id | `POST /setup/customers customer_id=999999` | PASS | HTTP 303 flash='Vendor &#39;QA-SETUP-UPDV-2BE30&#39; added.' (silent no-op: no success and no error message) |
| fields: update non-existent id | `POST /setup/fields field_id=999999` | BUG | F-SETUP-011: HTTP 303 flash='' (silent no-op: no success and no error message) |
| locations: update non-existent id | `POST /setup/locations location_id=999999` | BUG | F-SETUP-011: HTTP 303 flash='' (silent no-op: no success and no error message) |
| equipment: update non-existent id | `POST /setup/equipment equipment_id=999999` | BUG | F-SETUP-011: HTTP 303 flash='' (silent no-op: no success and no error message) |
| services: update non-existent id | `POST /setup/services service_id=999999` | BUG | F-SETUP-011: HTTP 303 flash='' (silent no-op: no success and no error message) |
| vendors: update non-existent id | `POST /setup/vendors vendor_id=999999` | BUG | F-SETUP-011: HTTP 303 flash='' (silent no-op: no success and no error message) |
| personnel: update non-existent id | `POST /setup/personnel personnel_id=999999` | BUG | F-SETUP-011: HTTP 303 flash='' (silent no-op: no success and no error message) |
| equipment: location from a different field | `POST /setup/equipment field_id=1 location_id=2` | BUG | F-SETUP-005: HTTP 303 db='18\t1\t2\t2' ev=.qa/evidence/setup_equipment_crosslocation_list.html |
| equipment: field/customer hierarchy mismatch | `POST /setup/equipment customer_id=1 field_id=6` | BUG | F-SETUP-005: HTTP 303 db='1\t6' |
| equipment: 'Active' unchecked on create | `POST /setup/equipment without is_active` | BUG | F-003 (confirmed by lead): HTTP 303 is_active=1 (known F-003, not re-reported) |
| personnel: 'Active' unchecked on create | `POST /setup/personnel without is_active` | BUG | F-003 (confirmed by lead): HTTP 303 is_active=1 (known F-003, not re-reported) |
| delete: location with dependent equipment | `POST /setup/locations/8/delete` | PASS | HTTP 303 still_exists=1 flash='Cannot delete &#39;Location &#39;QA-SETUP-DLB-B7EE0&#39;&#39;: it still has dependent records.' |
| delete: field with location+equipment | `POST /setup/fields/8/delete` | PASS | HTTP 303 still_exists=1 flash='Cannot delete &#39;Field &#39;QA-SETUP-DFB-B7EE0&#39;&#39;: it still has dependent records.' |
| delete: customer with field+location+equipment | `POST /setup/customers/7/delete` | PASS | HTTP 303 still_exists=1 flash='Cannot delete &#39;Customer &#39;QA-SETUP-DCB-B7EE0&#39;&#39;: it still has dependent records.' |
| delete: field whose only dependents are locations | `POST /setup/fields/7/delete` | BUG | F-SETUP-003: HTTP 303 field_exists=0 location_exists=0 flash='Field &#39;QA-SETUP-DFA-B7EE0&#39; deleted.' |
| delete: customer whose dependents have no equipment | `POST /setup/customers/8/delete` | BUG | F-SETUP-003: HTTP 303 customer=0 field=0 location=0 flash='Customer &#39;QA-SETUP-DCC-B7EE0&#39; deleted.' |
| customers: delete non-existent id | `POST /setup/customers/999999/delete` | GAP | HTTP 303 flash='' (silent: no 'record not found' feedback) |
| fields: delete non-existent id | `POST /setup/fields/999999/delete` | GAP | HTTP 303 flash='' (silent: no 'record not found' feedback) |
| locations: delete non-existent id | `POST /setup/locations/999999/delete` | GAP | HTTP 303 flash='' (silent: no 'record not found' feedback) |
| equipment: delete non-existent id | `POST /setup/equipment/999999/delete` | GAP | HTTP 303 flash='' (silent: no 'record not found' feedback) |
| services: delete non-existent id | `POST /setup/services/999999/delete` | GAP | HTTP 303 flash='' (silent: no 'record not found' feedback) |
| vendors: delete non-existent id | `POST /setup/vendors/999999/delete` | GAP | HTTP 303 flash='' (silent: no 'record not found' feedback) |
| personnel: delete non-existent id | `POST /setup/personnel/999999/delete` | GAP | HTTP 303 flash='' (silent: no 'record not found' feedback) |
| delete URL via GET | `GET /setup/customers/1/delete` | GAP | HTTP 405 application/json body='{"detail":"Method Not Allowed"}' (raw JSON, seeded row untouched) |
| delete non-integer id | `POST /setup/customers/abc/delete` | BUG | F-SETUP-009: HTTP 422 body='{"detail":[{"type":"int_parsing","loc":["path","cid"],"msg":"Input should be a v' |
| delete: no Referer header | `POST /setup/customers/9/delete (no Referer)` | PASS | HTTP 303 Location='/' |
| delete: Referer present | `POST /setup/customers/10/delete (Referer=list)` | PASS | HTTP 303 Location='http://127.0.0.1:8000/setup/customers' |
| delete: off-site Referer | `POST /setup/customers/11/delete (Referer=evil.example)` | BUG | F-SETUP-013: HTTP 303 Location='https://evil.example/phish' |
| delete: success flash shown on list | `POST /setup/customers/12/delete then GET list` | PASS | flash='Customer &#39;QA-SETUP-FLASH-B7EE0&#39; deleted.' |
| equipment: Location left at '— Location —' (0) | `POST /setup/equipment location_id=0` | BUG | F-002 (confirmed by lead): HTTP 500 (known F-002; FK equipment_ibfk_3 1452 at app/routers/setup.py:287) ev=.qa/evidence/setup_equipment_location0.txt |
| equipment: 'Active' unchecked on EDIT | `POST /setup/equipment equipment_id=23 without is_active` | BUG | F-003 (confirmed by lead): is_active=1 (known F-003 variant, not re-reported) |
| personnel: 'Active' unchecked on EDIT | `POST /setup/personnel personnel_id=7 without is_active` | BUG | F-003 (confirmed by lead): is_active=1 (known F-003 variant, not re-reported) |
| equipment: edit prefills the 3 selects | `GET /setup/equipment?edit=23` | PASS | selected={'customer_id': '1', 'field_id': '1', 'location_id': '1'} |
| services: edit prefills all inputs | `GET /setup/services?edit=19` | PASS | values={'code': 'QASE5C0B6', 'name': 'QA prefill', 'frequency_weeks': '7', 'estimated_hours': '3.5', 'discipline': 'Electrical'} |
| customers: failed dup update leaves row unchanged | `DB check after dup-update 500` | PASS | row=['QA-SETUP-UPDC-2BE30'] |
| services: estimated_hours=1e400 | `POST /setup/services estimated_hours=1e400` | BUG | F-SETUP-004: HTTP 500 stored=None |
| services: frequency_weeks=INT max | `POST /setup/services frequency_weeks=2147483647` | PASS | HTTP 303 |
| customers: ?edit= edge values | `GET /setup/customers?edit= / abc / 999999` | BUG | F-SETUP-009: empty=422 abc=422 999999=200 (999999 renders the empty Add form, no 'not found' notice) |
| fields: ?edit= edge values | `GET /setup/fields?edit= / abc / 999999` | BUG | F-SETUP-009: empty=422 abc=422 999999=200 (999999 renders the empty Add form, no 'not found' notice) |
| locations: ?edit= edge values | `GET /setup/locations?edit= / abc / 999999` | BUG | F-SETUP-009: empty=422 abc=422 999999=200 (999999 renders the empty Add form, no 'not found' notice) |
| equipment: ?edit= edge values | `GET /setup/equipment?edit= / abc / 999999` | BUG | F-SETUP-009: empty=422 abc=422 999999=200 (999999 renders the empty Add form, no 'not found' notice) |
| services: ?edit= edge values | `GET /setup/services?edit= / abc / 999999` | BUG | F-SETUP-009: empty=422 abc=422 999999=200 (999999 renders the empty Add form, no 'not found' notice) |
| vendors: ?edit= edge values | `GET /setup/vendors?edit= / abc / 999999` | BUG | F-SETUP-009: empty=422 abc=422 999999=200 (999999 renders the empty Add form, no 'not found' notice) |
| personnel: ?edit= edge values | `GET /setup/personnel?edit= / abc / 999999` | BUG | F-SETUP-009: empty=422 abc=422 999999=200 (999999 renders the empty Add form, no 'not found' notice) |
| customers: ?edit=<missing id> | `GET /setup/customers?edit=999999` | GAP | renders the blank Add form; the user gets no 'record not found' message |
| setup tabs: every link resolves | `GET 75 distinct links found on the 7 tabs` | PASS | broken=[] |
| customers: name is HTML-escaped in list | `POST then GET /setup/customers` | PASS | raw <img> absent from list HTML |
| setup: /setup root path | `GET /setup` | GAP | HTTP 404 application/json (no index route; nav never links it) |
| fields: non-existent customer_id FK id | `POST /setup/fields customer_id=999999` | BUG | F-SETUP-006: HTTP 500 flash='' ev=.qa/evidence/setup_fields_fk_customer_id.txt |
| locations: non-existent field_id FK id | `POST /setup/locations field_id=999999` | BUG | F-SETUP-006: HTTP 500 flash='' ev=.qa/evidence/setup_locations_fk_field_id.txt |
| equipment: non-existent customer_id FK id | `POST /setup/equipment customer_id=999999` | BUG | F-SETUP-006: HTTP 500 flash='' ev=.qa/evidence/setup_equipment_fk_customer_id.txt |
| equipment: non-existent field_id FK id | `POST /setup/equipment field_id=999999` | BUG | F-SETUP-006: HTTP 500 flash='' ev=.qa/evidence/setup_equipment_fk_field_id.txt |
| equipment: non-existent location_id FK id | `POST /setup/equipment location_id=999999` | BUG | F-SETUP-006: HTTP 500 flash='' ev=.qa/evidence/setup_equipment_fk_location_id.txt |
| customers: update non-existent id (clean) | `POST /setup/customers customer_id=999999` | BUG | F-SETUP-011: HTTP 303 flash='' rows_created=0 (silent no-op) |

## Totals

- checks run: **133**
- PASS: **61**
- BUG: **53**
- GAP: **19**
- BLOCKED: **0**

## Gaps / usability notes (no HTTP error, but the UI misleads or cannot do something)

- **Duplicate detection missing for Fields, Locations and Equipment**: only Customers, Services and Vendors have a duplicate check. `POST /setup/fields`, `/setup/locations` and `/setup/equipment` happily create two fields with the same name under one customer, two identically named locations in one field, and two equipment rows with the same Tag 1 (no unique constraint either). Legacy PMSyS treats the tag as the asset identifier; duplicate tags make the Equipment list ambiguous and make work orders unreferenceable.
- **Numeric coercion**: clearing or corrupting Services *Frequency (weeks)* silently stores 4; a non-numeric *Est. hours* silently stores NULL (F-SETUP-012).
- **Delete of an already-deleted id is silent**: 303 with no flash (all 7 tabs) — the user gets no 'record not found' feedback.
- **`?edit=<missing id>` renders the blank *Add* form** with no 'record not found' notice (all 7 tabs), so a stale bookmark looks like the Add screen.
- **`/setup` (no tab) is a raw JSON 404** — there is no index route, though the nav never links it.
- **Equipment Location select has no `required`** and defaults to `value=0` while `equipment.location_id` is NOT NULL: the most natural mistake in the form (leave Location alone) is the 500 in F-002. There is no way to record equipment without a location, and no way to see which locations belong to the selected field (all locations from all customers are listed in one flat select).
- **Delete uses `onsubmit="return confirm(...)"`**, so it is a silent no-op with JavaScript disabled; no server-rendered confirmation page exists.
- **No deactivate/soft-delete**: `is_active` exists on Equipment/Personnel (and is ignored on save — F-003), but the list views give no way to filter by it.
- **Services list does not show `description`**, and **Equipment list does not show serial / parts-list / instruction numbers**, so data entered on the form cannot be reviewed from the UI.

## Excluded / not tested

- Planning, reports, history and auth routers (other testers' areas).
- The seeded demo rows (Secure Energy, its fields/locations, equipment 1-5, service codes, vendors, personnel) were only read, never written; the delete-dependency checks used QA-created records.
- PDF/print output of these tabs (none exists).
