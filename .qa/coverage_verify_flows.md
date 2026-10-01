# Coverage — write-flow verification

| item | verdict | evidence | note |
|---|---|---|---|
| 1 — Auto-assign evenly | **FIXED** | `.qa/evidence/verify_item1_equipment.html` | single item and 4-item batch; round-robin 1,2,3,1 over the 3 active technicians |
| 2 — Auto-assign with no active technicians | **FIXED** | `.qa/evidence/verify_item2_no_technicians.html` | personnel recorded inactive in DB first, then restored to active |
| 3 — Equipment without a Location / with an empty Customer or Field | **FIXED** | `.qa/evidence/verify_item3_case1.html` | 7 variants incl. empty strings and cross-customer/cross-field mismatches; 0 rows created |
| 4 — Unchecked “Active” on create and edit | **FIXED** | `.qa/evidence/verify_item4_equipment_create.html` | equipment + personnel; create and edit; edit form re-rendered unticked |
| 5 — Over-long values | **FIXED** | `.qa/evidence/verify_item5_case1.html` | 12 over-long columns rejected, 8 exact-limit boundaries accepted |
| 6 — Rename to a duplicate unique value | **FIXED** | `.qa/evidence/verify_item6_customer_dup.html` | customers, service codes, vendors; + case-variant and duplicate-on-create |
| 7 — Silent cascade delete | **FIXED** | `.qa/evidence/verify_item7_delete_customer_blocked.html` | refusals hold; location→field→customer deletes succeed; location+equipment refused |
| 8 — Non-existent FK ids | **FIXED** | `.qa/evidence/verify_item8_field_fk.html` | fields, locations, schedule (vendor/personnel), closeout (personnel/vendor) |
| 9 — Invalid dates | **FIXED** | `.qa/evidence/verify_item9_schedule_bad_date.html` | 3 date fields; flash names YYYY-MM-DD; zero state change |
| 10 — Duplicate draft rows | **STILL BROKEN** | `.qa/evidence/verify_item10_second_add.html` | two submissions FIXED; one crafted request with a repeated id still creates 2 rows |
| 11 — Cancel (new action) | **FIXED** | `.qa/evidence/verify_item11_cancel.html` | scheduled→cancelled, out of Final, in History with chip, WO/CM links 200; draft no-op |
| 12 — Missing / stale record ids | **FIXED** | `.qa/evidence/verify_item12_customers.html` | all 7 tabs + reset-password; “not found” flash, no state change |
| 13 — Error surfaces | **FIXED** | `.qa/evidence/verify_item13_unknown_url.html` | 404, 303, 200, 403, 405; all error surfaces HTML |
| cleanup — Cleanup and baseline restoration | **FIXED** | `.qa/evidence/verify_cleanup_baseline.txt` | full baseline: 1/2/2/5/8/3/3/3 tables, users=1 (admin only), zero QA-VERIFY- rows |

**Tally:** FIXED **12** · STILL BROKEN **1** · REGRESSION **0** (out of 13 items; cleanup row excluded).

Findings: **V-FLOW-001** (item 10 crafted duplicate), **V-FLOW-002** (cross-cutting bcrypt >72-byte password 500, outside the 13 items).
