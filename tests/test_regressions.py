"""Regression tests for the defects found during the port-8000 QA pass.

Each test here failed (or would have failed) against the pre-fix build.
"""
from datetime import date, timedelta

from app.auth import hash_password
from app.models import Customer, Equipment, Field, Location, Personnel, Plan, Service, User


def login(client, username="admin", password="admin"):
    return client.post(
        "/login", data={"username": username, "password": password}, follow_redirects=False
    )


def post(client, path, data=None):
    """POST without following the 303, so the flash lands on the next GET."""
    return client.post(path, data=data or {}, follow_redirects=False)


def make_hierarchy(db):
    customer = Customer(name="Secure Energy")
    db.add(customer)
    db.commit()
    field = Field(customer_id=customer.id, name="Wild River")
    db.add(field)
    db.commit()
    location = Location(field_id=field.id, name="10-03-57-23W5")
    db.add(location)
    db.commit()
    return customer, field, location


def make_draft(db, equipment, service):
    plan = Plan(
        equipment_id=equipment.id,
        service_id=service.id,
        last_completed_date=date.today(),
        proposed_date=date.today() + timedelta(weeks=service.frequency_weeks),
        status=Plan.DRAFT,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


# --- raw JSON 422 -> friendly redirect with flash ----------------------------


def test_schedule_with_no_selection_flashes(client, admin, db_session):
    login(client)
    r = post(client, "/planning/schedule", {"schedule_date": "2026-01-05"})
    assert r.status_code == 303
    assert "Select at least one draft item" in client.get("/planning/draft").text


def test_draft_delete_with_no_selection_flashes(client, admin, db_session):
    login(client)
    r = post(client, "/planning/draft/delete")
    assert r.status_code == 303
    assert "Deleted 0 item(s)" in client.get("/planning/draft").text


def test_closeout_with_no_selection_flashes(client, admin, db_session):
    login(client)
    r = post(client, "/planning/closeout", {"actual_date": "2026-01-05"})
    assert r.status_code == 303
    assert "Select at least one item to close out" in client.get("/planning/final").text


def test_draft_add_without_service_flashes(client, admin, db_session):
    login(client)
    r = post(client, "/planning/draft/add", {"equipment_ids": [1]})
    assert r.status_code == 303
    assert "Please choose a service" in client.get("/planning/draft").text


def test_draft_add_without_equipment_flashes(client, admin, db_session):
    login(client)
    svc = Service(code="SCJ008", name="Plant Alarms", frequency_weeks=4)
    db_session.add(svc)
    db_session.commit()
    r = post(client, "/planning/draft/add", {"service_id": svc.id})
    assert r.status_code == 303
    assert "Select at least one equipment item" in client.get("/planning/draft").text


# --- setup validation instead of 500 / 422 ----------------------------------


def test_equipment_without_location_does_not_500(client, admin, db_session):
    """Was: IntegrityError -> HTTP 500 because location_id=0 violates the FK."""
    login(client)
    customer, field, _ = make_hierarchy(db_session)
    r = post(
        client,
        "/setup/equipment",
        {"customer_id": customer.id, "field_id": field.id, "location_id": 0, "tag1": "FIT-9"},
    )
    assert r.status_code == 303
    assert db_session.query(Equipment).count() == 0
    assert "location that belongs" in client.get("/setup/equipment").text


def test_equipment_with_empty_customer_flashes(client, admin, db_session):
    login(client)
    r = post(client, "/setup/equipment", {"customer_id": "", "field_id": "", "tag1": "FIT-9"})
    assert r.status_code == 303
    assert "Please choose a customer" in client.get("/setup/equipment").text


def test_equipment_field_must_belong_to_customer(client, admin, db_session):
    login(client)
    customer, _, location = make_hierarchy(db_session)
    other = Customer(name="Other Co")
    db_session.add(other)
    db_session.commit()
    other_field = Field(customer_id=other.id, name="Other Field")
    db_session.add(other_field)
    db_session.commit()
    r = post(
        client,
        "/setup/equipment",
        {
            "customer_id": customer.id,
            "field_id": other_field.id,
            "location_id": location.id,
            "tag1": "FIT-9",
        },
    )
    assert r.status_code == 303
    assert db_session.query(Equipment).count() == 0
    assert "belongs to the selected customer" in client.get("/setup/equipment").text


def test_equipment_unchecked_active_is_saved_inactive(client, admin, db_session):
    """Was: Form('on') default meant an unchecked box still saved is_active=True."""
    login(client)
    customer, field, location = make_hierarchy(db_session)
    r = post(
        client,
        "/setup/equipment",
        {
            "customer_id": customer.id,
            "field_id": field.id,
            "location_id": location.id,
            "tag1": "FIT-9",
        },
    )
    assert r.status_code == 303
    assert db_session.query(Equipment).one().is_active is False


def test_equipment_checked_active_is_saved_active(client, admin, db_session):
    login(client)
    customer, field, location = make_hierarchy(db_session)
    post(
        client,
        "/setup/equipment",
        {
            "customer_id": customer.id,
            "field_id": field.id,
            "location_id": location.id,
            "tag1": "FIT-9",
            "is_active": "on",
        },
    )
    assert db_session.query(Equipment).one().is_active is True


def test_personnel_unchecked_active_is_saved_inactive(client, admin, db_session):
    login(client)
    r = post(client, "/setup/personnel", {"first_name": "Jeff", "last_name": "Bezruchak"})
    assert r.status_code == 303
    assert db_session.query(Personnel).one().is_active is False


def test_fields_with_empty_customer_flashes(client, admin, db_session):
    login(client)
    r = post(client, "/setup/fields", {"name": "Wild River", "customer_id": ""})
    assert r.status_code == 303
    assert "Field name and customer are required" in client.get("/setup/fields").text


def test_locations_with_empty_field_flashes(client, admin, db_session):
    login(client)
    r = post(client, "/setup/locations", {"name": "10-03-57-23W5", "field_id": ""})
    assert r.status_code == 303
    assert "Location name and field are required" in client.get("/setup/locations").text


def test_service_frequency_must_be_positive(client, admin, db_session):
    login(client)
    r = post(
        client,
        "/setup/services",
        {"code": "SCJ999", "name": "Bad frequency", "frequency_weeks": "0"},
    )
    assert r.status_code == 303
    assert db_session.query(Service).count() == 0
    assert "Frequency must be" in client.get("/setup/services").text


# --- error pages instead of raw JSON ----------------------------------------


def test_unknown_url_renders_html_error_page(client, admin, db_session):
    login(client)
    r = client.get("/no-such-page")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html")
    assert "Not found" in r.text


def test_non_admin_gets_html_403(client, admin, db_session):
    db_session.add(
        User(
            username="worker",
            password_hash=hash_password("secret1"),
            display_name="Worker",
            role="user",
        )
    )
    db_session.commit()
    login(client, "worker", "secret1")
    r = client.get("/users")
    assert r.status_code == 403
    assert r.headers["content-type"].startswith("text/html")
    assert "Not allowed" in r.text


def test_stale_edit_param_renders_tab_instead_of_422(client, admin, db_session):
    """Was: raw JSON 422; a stale ?edit=abc should just show the list + add form."""
    login(client)
    r = client.get("/setup/equipment?edit=abc")
    assert r.status_code == 200
    assert "Add equipment" in r.text


def test_non_integer_path_param_renders_html_422(client, admin, db_session):
    login(client)
    r = client.get("/reports/work-order/abc")
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("text/html")
    assert "Invalid request" in r.text


def test_garbage_history_customer_filter_is_tolerated(client, admin, db_session):
    login(client)
    r = client.get("/history?customer_id=abc")
    assert r.status_code == 200
    assert "History" in r.text


def test_login_without_fields_shows_error_page_not_json(client, db_session):
    r = post(client, "/login")
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("text/html")
    assert "Invalid username or password" in r.text


# --- report content ---------------------------------------------------------


def test_final_plan_print_includes_schedule_columns(client, admin, db_session):
    """Was: 'scheduled' was never passed, so the final print dropped the columns."""
    login(client)
    customer, field, location = make_hierarchy(db_session)
    equipment = Equipment(
        customer_id=customer.id, field_id=field.id, location_id=location.id, tag1="FIT-1140"
    )
    service = Service(code="SCJ008", name="Plant Alarms", frequency_weeks=4)
    db_session.add_all([equipment, service])
    db_session.commit()
    plan = make_draft(db_session, equipment, service)
    plan.status = Plan.SCHEDULED
    plan.schedule_date = date(2026, 10, 5)
    plan.wo_no = f"WO-{plan.id:04d}"
    db_session.commit()

    final = client.get("/planning/final/print")
    assert final.status_code == 200
    assert "Work order" in final.text
    assert "Schedule date" in final.text
    assert f"WO-{plan.id:04d}" in final.text

    draft = client.get("/planning/draft/print")
    assert draft.status_code == 200
    assert "Work order" not in draft.text


def test_work_order_for_unscheduled_plan_is_404(client, admin, db_session):
    login(client)
    customer, field, location = make_hierarchy(db_session)
    equipment = Equipment(
        customer_id=customer.id, field_id=field.id, location_id=location.id, tag1="FIT-1140"
    )
    service = Service(code="SCJ008", name="Plant Alarms", frequency_weeks=4)
    db_session.add_all([equipment, service])
    db_session.commit()
    plan = make_draft(db_session, equipment, service)

    r = client.get(f"/reports/work-order/{plan.id}")
    assert r.status_code == 404
    assert "not been scheduled" in r.text
    assert client.get(f"/reports/calibration/{plan.id}").status_code == 404


# --- planning: auto-assign, FK validation, strict dates, duplicates ---------


def seed_plan_context(db):
    customer, field, location = make_hierarchy(db)
    equipment = Equipment(
        customer_id=customer.id, field_id=field.id, location_id=location.id, tag1="FIT-1140"
    )
    service = Service(code="SCJ008", name="Plant Alarms", frequency_weeks=4)
    db.add_all([equipment, service])
    db.commit()
    return equipment, service


def test_auto_assign_schedules_and_assigns(client, admin, db_session):
    """Was: TypeError ('str' object is not callable) because the form field
    auto_assign shadowed the imported app.services.auto_assign function."""
    login(client)
    equipment, service = seed_plan_context(db_session)
    person = Personnel(first_name="Jeff", last_name="Bezruchak", is_active=True)
    db_session.add(person)
    db_session.commit()
    plan = make_draft(db_session, equipment, service)

    r = post(
        client,
        "/planning/schedule",
        {"plan_ids": [plan.id], "schedule_date": "2026-10-05", "auto_assign": "on"},
    )
    assert r.status_code == 303
    db_session.refresh(plan)
    assert plan.status == Plan.SCHEDULED
    assert plan.personnel_id == person.id
    assert plan.wo_no == f"WO-{plan.id:04d}"


def test_auto_assign_without_active_personnel_flashes(client, admin, db_session):
    login(client)
    equipment, service = seed_plan_context(db_session)
    plan = make_draft(db_session, equipment, service)
    r = post(
        client,
        "/planning/schedule",
        {"plan_ids": [plan.id], "schedule_date": "2026-10-05", "auto_assign": "on"},
    )
    assert r.status_code == 303
    db_session.refresh(plan)
    assert plan.status == Plan.DRAFT
    assert "No active technicians" in client.get("/planning/draft").text


def test_schedule_with_bogus_vendor_flashes(client, admin, db_session):
    login(client)
    equipment, service = seed_plan_context(db_session)
    plan = make_draft(db_session, equipment, service)
    r = post(
        client,
        "/planning/schedule",
        {"plan_ids": [plan.id], "schedule_date": "2026-10-05", "vendor_id": 999999},
    )
    assert r.status_code == 303
    db_session.refresh(plan)
    assert plan.status == Plan.DRAFT
    assert "existing service vendor" in client.get("/planning/draft").text


def test_schedule_with_unparseable_date_flashes(client, admin, db_session):
    login(client)
    equipment, service = seed_plan_context(db_session)
    plan = make_draft(db_session, equipment, service)
    r = post(
        client,
        "/planning/schedule",
        {"plan_ids": [plan.id], "schedule_date": "not-a-date"},
    )
    assert r.status_code == 303
    db_session.refresh(plan)
    assert plan.status == Plan.DRAFT
    assert "YYYY-MM-DD" in client.get("/planning/draft").text


def test_closeout_with_bogus_vendor_flashes(client, admin, db_session):
    login(client)
    equipment, service = seed_plan_context(db_session)
    plan = make_draft(db_session, equipment, service)
    plan.status = Plan.SCHEDULED
    plan.schedule_date = date(2026, 10, 5)
    db_session.commit()

    r = post(
        client,
        "/planning/closeout",
        {"plan_ids": [plan.id], "actual_date": "2026-10-06", "actual_vendor_id": 999999},
    )
    assert r.status_code == 303
    db_session.refresh(plan)
    assert plan.status == Plan.SCHEDULED
    assert "existing service vendor" in client.get("/planning/final").text


def test_duplicate_draft_item_is_skipped(client, admin, db_session):
    login(client)
    equipment, service = seed_plan_context(db_session)
    post(client, "/planning/draft/add", {"service_id": service.id, "equipment_ids": [equipment.id]})
    post(client, "/planning/draft/add", {"service_id": service.id, "equipment_ids": [equipment.id]})
    assert db_session.query(Plan).count() == 1


def test_cancel_moves_scheduled_item_to_history(client, admin, db_session):
    login(client)
    equipment, service = seed_plan_context(db_session)
    plan = make_draft(db_session, equipment, service)
    plan.status = Plan.SCHEDULED
    plan.schedule_date = date(2026, 10, 5)
    plan.wo_no = f"WO-{plan.id:04d}"
    plan.cm_no = f"CM-{plan.id:04d}"
    db_session.commit()

    r = post(client, "/planning/cancel", {"plan_ids": [plan.id]})
    assert r.status_code == 303
    db_session.refresh(plan)
    assert plan.status == Plan.CANCELLED
    assert "cancelled" in client.get("/history").text


def test_reset_password_for_missing_user_flashes(client, admin, db_session):
    login(client)
    r = post(client, "/users/424242/reset-password", {"password": "abcdef"})
    assert r.status_code == 303
    assert "User not found" in client.get("/users").text


def test_long_password_does_not_500(client, admin, db_session):
    """bcrypt raises ValueError above 72 bytes; that used to be an HTTP 500."""
    login(client)
    long_pw = "A" * 100
    r = post(client, "/users", {"username": "longpw", "password": long_pw, "role": "user"})
    assert r.status_code == 303
    assert db_session.query(User).filter_by(username="longpw").first() is None
    assert "72 bytes" in client.get("/users").text

    r = post(
        client,
        "/account/password",
        {"current_password": "admin", "new_password": long_pw, "confirm_password": long_pw},
    )
    assert r.status_code == 303
    assert "72 bytes" in client.get("/account").text
    assert login(client).status_code == 303  # admin password untouched


# --- redirect / error-page hardening ---------------------------------------


def test_cross_site_referer_is_not_honoured(client, admin, db_session):
    login(client)
    customer, _, _ = make_hierarchy(db_session)
    r = client.post(
        f"/setup/customers/{customer.id}/delete",
        data={},
        headers={"Referer": "https://evil.example/phish"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/setup/customers"


def test_unhandled_error_renders_html_500(db_session):
    from fastapi.testclient import TestClient

    from app.dependencies import get_db as dep_get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[dep_get_db] = override_get_db

    @app.get("/__qa_boom__")
    def boom():
        raise RuntimeError("boom")

    try:
        c = TestClient(app, raise_server_exceptions=False)
        r = c.get("/__qa_boom__")
        assert r.status_code == 500
        assert r.headers["content-type"].startswith("text/html")
        assert "Server error" in r.text
    finally:
        app.routes[:] = [rt for rt in app.routes if getattr(rt, "path", None) != "/__qa_boom__"]
        app.dependency_overrides.clear()


# --- leftovers found by the independent verification pass --------------------


def test_repeated_equipment_id_in_one_request_creates_one_plan(client, admin, db_session):
    """A single request repeating the same id must not bypass the duplicate guard."""
    login(client)
    equipment, service = seed_plan_context(db_session)
    r = post(
        client,
        "/planning/draft/add",
        {"service_id": service.id, "equipment_ids": [equipment.id, equipment.id]},
    )
    assert r.status_code == 303
    assert db_session.query(Plan).count() == 1


def test_personnel_stale_edit_param_is_tolerated(client, admin, db_session):
    login(client)
    assert client.get("/setup/personnel?edit=abc").status_code == 200
    assert client.get("/setup/personnel?edit=").status_code == 200


def test_login_error_page_has_home_link(client, db_session):
    r = post(client, "/login", {"username": "nope", "password": "wrong1"})
    assert r.status_code == 401
    assert 'href="/"' in r.text


def test_delete_without_referer_lands_on_its_tab(client, admin, db_session):
    login(client)
    customer = Customer(name="Temp Co")
    db_session.add(customer)
    db_session.commit()
    r = client.post(f"/setup/customers/{customer.id}/delete", data={}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/setup/customers"
    assert "deleted" in client.get("/setup/customers").text


def test_delete_missing_row_flashes(client, admin, db_session):
    login(client)
    r = post(client, "/setup/services/424242/delete")
    assert r.status_code == 303
    assert "Service not found" in client.get("/setup/services").text


def test_toggle_missing_user_flashes(client, admin, db_session):
    login(client)
    r = post(client, "/users/424242/toggle")
    assert r.status_code == 303
    assert "User not found" in client.get("/users").text
