"""Integration tests using FastAPI's TestClient against an in-memory SQLite DB."""
from datetime import date, timedelta

from sqlalchemy.orm import joinedload

from app.models import Customer, Equipment, Field, Location, Personnel, Plan, Service, Vendor


def login(client, username="admin", password="admin"):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=False)


def make_equipment(db, customer, field, location):
    eq = Equipment(
        customer_id=customer.id, field_id=field.id, location_id=location.id,
        tag1="FIT-1140", tag2="INLET", description="Inlet meter", equipment_type="Meter",
    )
    db.add(eq)
    db.commit()
    db.refresh(eq)
    return eq


def make_service(db, code="SCJ008", freq=4):
    s = Service(code=code, name="Plant Alarms", frequency_weeks=freq)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def test_unauth_redirects_to_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_wrong_password(client, admin):
    r = login(client, "admin", "nope")
    assert r.status_code == 401


def test_login_and_home(client, admin):
    r = login(client)
    assert r.status_code == 303
    r = client.get("/")
    assert r.status_code == 200
    assert "Dashboard" in r.text


def test_admin_creates_user_and_that_user_logs_in(client, admin):
    login(client)
    r = client.post(
        "/users",
        data={"username": "operator", "display_name": "Op", "password": "secret1", "role": "user"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    r = client.post("/login", data={"username": "operator", "password": "secret1"}, follow_redirects=False)
    assert r.status_code == 303


def test_change_own_password(client, admin):
    login(client)
    r = client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "newpass1", "confirm_password": "newpass1"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    client.post("/logout")
    assert login(client, "admin", "newpass1").status_code == 303


def test_full_planning_flow(client, admin, db_session):
    login(client)

    customer = Customer(name="Secure Energy")
    db_session.add(customer)
    db_session.commit()
    field = Field(customer_id=customer.id, name="Wild River")
    db_session.add(field)
    db_session.commit()
    location = Location(field_id=field.id, name="10-03-57-23W5")
    db_session.add(location)
    db_session.commit()

    eq = make_equipment(db_session, customer, field, location)
    svc = make_service(db_session, freq=4)
    vendor = Vendor(name="XYZ Company")
    person = Personnel(first_name="Jeff", last_name="Bezruchak", position="MT", discipline="Mechanical")
    db_session.add_all([vendor, person])
    db_session.commit()

    # Add to draft plan -> proposed date = last_completed + frequency weeks.
    r = client.post(
        "/planning/draft/add",
        data={"service_id": svc.id, "equipment_ids": [eq.id]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    plan = db_session.query(Plan).filter_by(status=Plan.DRAFT).one()
    assert plan.last_completed_date == date.today()
    assert plan.proposed_date == date.today() + timedelta(weeks=4)

    # Schedule -> stamped work order / calibration, moved to final.
    r = client.post(
        "/planning/schedule",
        data={
            "plan_ids": [plan.id],
            "schedule_date": "2026-10-05",
            "vendor_id": vendor.id,
            "personnel_id": person.id,
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    db_session.refresh(plan)
    assert plan.status == Plan.SCHEDULED
    assert plan.wo_no == f"WO-{plan.id:04d}"
    assert plan.cm_no == f"CM-{plan.id:04d}"

    # Close out with an actual date -> completed; actual date feeds the next cycle.
    r = client.post(
        "/planning/closeout",
        data={"plan_ids": [plan.id], "actual_date": "2026-10-06"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db_session.refresh(plan)
    assert plan.status == Plan.COMPLETED
    assert plan.actual_date == date(2026, 10, 6)

    # Re-adding the same equipment+service picks up the actual date as last-completed.
    client.post(
        "/planning/draft/add",
        data={"service_id": svc.id, "equipment_ids": [eq.id]},
        follow_redirects=False,
    )
    new_plan = (
        db_session.query(Plan)
        .options(joinedload(Plan.equipment))
        .filter(Plan.status == Plan.DRAFT)
        .one()
    )
    assert new_plan.last_completed_date == date(2026, 10, 6)
    assert new_plan.proposed_date == date(2026, 10, 6) + timedelta(weeks=4)