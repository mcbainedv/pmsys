# Post-fix verification — port 8000

Two independent verification subagents and the Lead re-tested the rebuilt server. The
container (`pmsys-app-1`) was rebuilt and redeployed from the fixed working tree; every
result below is a live HTTP request against `http://127.0.0.1:8000` with the real MariaDB.

## Pass 1 — write-flow falsification (subagent `verify-flows`)

`.qa/verify_flows.md`, `coverage_verify_flows.md`, `findings_verify.md`, 84 raw captures.

**Tally: FIXED 12 · STILL BROKEN 1 · REGRESSION 0**

Fixed: auto-assign evenly (303 + round-robin p1→p2→p3→p1 across 3 technicians, `WO-`/`CM-`
stamped); 0-active-technician flash with the item left in Draft; 7 equipment-chain variants
(303 + friendly flash, no row); `is_active` omitted on create **and** edit persisting `0`
for equipment and technicians (edit form re-renders unticked); 12 over-long columns rejected
and 8 exact-limit boundaries accepted; duplicate customer/service/vendor renames refused
(including case variants); cascade deletes refused with rows intact, and location → field →
customer deletes still succeed in order; FK `999999` → 303 with no state change; garbage
dates → 303 `Please enter dates in YYYY-MM-DD format.` with zero state change; cancel →
`cancelled`, out of Final Plan, visible in History with the `chip-cancelled` chip, WO/CM
links still 200, cancelling a draft is a no-op; stale `*_id` on all 7 tabs plus
`/users/424242/reset-password` → "not found" flash; all error surfaces HTML.

Only counterexample: a single crafted request repeating the same equipment id
(`equipment_ids=43&equipment_ids=43`) created two draft rows (V-FLOW-001). Not reachable
from the rendered form. Also flagged: the deployed image was 3 files behind the tree
(bcrypt >72-byte 500, `?customer_id=` 422), and `_safe_delete`'s `/setup` fallback is not a
route.

## Pass 2 — broad regression sweep (subagent `verify-regression`)

`.qa/verify_regression.md`, `coverage_verify_regression.md`.

**292 request-level checks → 52 scored, 45 PASS / 7 BUG; JSON error bodies encountered: 0.**

Confirmed good: crawl of 98 URLs all 200/303 with no dead links and no Jinja markers; 14
empty form submits all 303 + flash; Final Plan print contains Schedule date / Vendor /
Technician / Work order; work-order + calibration 200; `?format=pdf` → 4/4 real PDFs; the
filtered draft print's "Download PDF" link keeps `from`/`to`; nav active-tab 13/13; Setup
dropdown 7/7; non-admin `/users` → HTML 403 with a Home link; `?edit=` pre-fill +
create/update/delete round-trip 44/44.

Found (all fixed in the final tree and rebuilt): long password 500 (V-REGR-001, high),
`/history?customer_id=abc` 422 (V-REGR-002), `/setup/personnel?edit=abc` 422 — one tab was
missed by the first pass (V-REGR-003), login 401 page had no Home link (V-REGR-004),
no-Referer delete landed on the non-route `/setup` (V-REGR-005), delete/toggle of a missing
row was a silent 303 (V-REGR-006).

## Pass 3 — Lead final end-to-end run on the fully rebuilt image

`python -m pytest` → **51 passed** (12 original + 39 regression tests).
Live scripted run (`.qa/verify_live.md`, evidence in `.qa/evidence/final_*`):

| # | Check | Result |
|---|---|---|
| 1 | F-PLAN-001 auto-assign evenly (was a guaranteed 500) | PASS — 303, `scheduled`, `personnel_id` set, `WO-0026`/`CM-0026` |
| 2 | New cancel action → History | PASS — `cancelled`, `chip-cancelled` in History |
| 3 | V-FLOW-001 repeated id in one request | PASS — exactly 1 open plan row (isolated re-check) |
| 4 | Equipment without a Location (was 500) | PASS — 303, 0 rows |
| 5 | Unchecked Active (was always saved active) | PASS — `is_active=0` |
| 6 | Customer-with-field delete (was silent cascade) | PASS — refused, row intact |
| 7 | Over-long name (was 500) | PASS — 303 flash |
| 8 | Duplicate rename (was 500) | PASS — 303 flash, original name intact |
| 9 | Bogus FK parent (was 500) | PASS — 303 flash, no row |
| 10 | V-REGR-001 password > 72 bytes (was 500) | PASS — 303 flash, no user created |
| 11 | V-REGR-002 `/history?customer_id=abc` | PASS — 200 |
| 12 | V-REGR-003 `/setup/personnel?edit=abc` and `?edit=` | PASS — 200 |
| 13 | V-REGR-004 login error page Home link | PASS — 401 with Home link |
| 14 | V-REGR-005 delete without Referer | PASS — 303 → `/setup/services` |
| 15 | V-REGR-006 missing-row delete/toggle flashes | PASS — "not found" flashes |
| 16 | Empty-selection buttons (was raw 422 JSON) | PASS — 303/303/303/303 |
| 17 | Error surfaces | PASS — 404 HTML, 422 HTML, `?edit=abc` 200 |
| 18 | Final Plan print scheduled columns | PASS — includes `WO-<id>` |

**19/19 checks pass** (the one initial FAIL was a test-assertion artefact: it counted a
previously cancelled plan in the same equipment+service pair; the isolated re-check above
shows one open row).

Post-run state: `docker logs` since the redeploy contain **0 tracebacks and 0 500s**; the
database is back to its seeded baseline (1 customer, 2 fields, 2 locations, 5 equipment,
8 services, 3 vendors, 3 technicians, 3 draft plans, `admin` only) with no QA rows left.
