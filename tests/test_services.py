"""Unit tests for the pure scheduling business logic (no database)."""
from datetime import date

import pytest

from app.services import auto_assign, calibration_no, proposed_date, work_order_no


def test_proposed_date_adds_weeks():
    assert proposed_date(date(2015, 5, 4), 4) == date(2015, 6, 1)
    assert proposed_date(date(2015, 10, 27), 4) == date(2015, 11, 24)
    assert proposed_date(date(2026, 1, 1), 26) == date(2026, 7, 2)


def test_proposed_date_zero_weeks():
    assert proposed_date(date(2026, 1, 1), 0) == date(2026, 1, 1)


def test_work_order_and_calibration_numbers():
    assert work_order_no(406) == "WO-0406"
    assert calibration_no(406) == "CM-0406"
    assert work_order_no(1) == "WO-0001"


def test_auto_assign_round_robin():
    p1, p2, p3, p4, p5 = range(5)  # plan ids stand in for plan objects
    a = type("P", (), {"id": 10})()
    b = type("P", (), {"id": 20})()
    result = auto_assign([p1, p2, p3, p4, p5], [a, b])
    assert result == {10: [p1, p3, p5], 20: [p2, p4]}


def test_auto_assign_single_personnel():
    a = type("P", (), {"id": 10})()
    plans = [1, 2, 3]
    assert auto_assign(plans, [a]) == {10: [1, 2, 3]}


def test_auto_assign_no_personnel_raises():
    with pytest.raises(ValueError):
        auto_assign([1, 2], [])