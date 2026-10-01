"""Pure business logic — no database access, so it is trivially unit-testable.

The scheduling rule is the core of the whole product:
    Last Completed PM Date + Service Frequency (weeks) = Next Proposed PM Date
"""
from datetime import date, timedelta
from typing import Sequence


def proposed_date(last_completed: date, frequency_weeks: int) -> date:
    """Compute the next scheduled PM date from a last-completed date."""
    return last_completed + timedelta(weeks=frequency_weeks)


def work_order_no(plan_id: int) -> str:
    """Deterministic work-order number (e.g. WO-0406)."""
    return f"WO-{plan_id:04d}"


def calibration_no(plan_id: int) -> str:
    """Deterministic calibration-report number (e.g. CM-0406)."""
    return f"CM-{plan_id:04d}"


def auto_assign(plans: Sequence["object"], personnel: Sequence["object"]) -> dict:
    """Round-robin distribute plans across personnel as evenly as possible.

    Returns a mapping personnel.id -> [plans]. Raises ValueError when there is
    no active personnel to assign to.
    """
    active = list(personnel)
    if not active:
        raise ValueError("No active personnel available to assign.")
    result: dict[int, list] = {}
    for i, plan in enumerate(plans):
        person = active[i % len(active)]
        result.setdefault(person.id, []).append(plan)
    return result