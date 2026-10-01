"""Idempotent first-run seed.

Creates the default ``admin``/``admin`` account and (only on an empty DB) a
demo dataset that mirrors the original PMSyS example: Secure Energy customer,
fields/locations/equipment, service codes with weekly frequencies, vendors
and personnel.
"""
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import settings
from app.database import SessionLocal
from app.models import (
    Customer,
    Equipment,
    Field,
    Location,
    Personnel,
    Service,
    User,
    Vendor,
)


def seed_admin(db: Session) -> None:
    user = db.query(User).filter_by(username=settings.default_admin_username).first()
    if user is None:
        db.add(
            User(
                username=settings.default_admin_username,
                password_hash=hash_password(settings.default_admin_password),
                display_name="Administrator",
                role="admin",
            )
        )
        db.commit()


def seed_demo(db: Session) -> None:
    if db.query(func.count(Customer.id)).scalar() > 0:
        return

    customer = Customer(name="Secure Energy")
    db.add(customer)
    db.flush()

    brazeau = Field(customer_id=customer.id, name="Brazeau")
    wild_river = Field(customer_id=customer.id, name="Wild River")
    db.add_all([brazeau, wild_river])
    db.flush()

    loc_brazeau = Location(field_id=brazeau.id, name="11-12-047-11W5")
    loc_wild = Location(field_id=wild_river.id, name="10-03-57-23W5")
    db.add_all([loc_brazeau, loc_wild])
    db.flush()

    base = date.today()
    equipment = [
        Equipment(customer_id=customer.id, field_id=brazeau.id, location_id=loc_brazeau.id,
                  tag1="FIT-1140", tag2="INLET", description="Inlet gas meter",
                  equipment_type="Meter", manufacturer="Emerson", model="M100"),
        Equipment(customer_id=customer.id, field_id=brazeau.id, location_id=loc_brazeau.id,
                  tag1="FIT-1150", tag2="INLET", description="Inlet gas meter",
                  equipment_type="Meter", manufacturer="Emerson", model="M100"),
        Equipment(customer_id=customer.id, field_id=wild_river.id, location_id=loc_wild.id,
                  tag1="FIT-1110", tag2="INLET", description="Inlet gas meter",
                  equipment_type="Meter", manufacturer="Emerson", model="M100"),
        Equipment(customer_id=customer.id, field_id=wild_river.id, location_id=loc_wild.id,
                  tag1="PIT-1600", tag2="H2O", description="Water pressure transmitter",
                  equipment_type="Transmitter", manufacturer="Rosemount", model="3051"),
        Equipment(customer_id=customer.id, field_id=wild_river.id, location_id=loc_wild.id,
                  tag1="FIT-5032", tag2="FLARE", description="Flare gas meter",
                  equipment_type="Meter", manufacturer="Emerson", model="M100"),
    ]
    db.add_all(equipment)

    services = [
        Service(code="SCJ001", name="Plant Alarms", frequency_weeks=4, estimated_hours=2,
                discipline="Electrical"),
        Service(code="SCJ002", name="Field Gas Meters", frequency_weeks=4, estimated_hours=3,
                discipline="Mechanical"),
        Service(code="SCJ008", name="Plant Gas Meters", frequency_weeks=4, estimated_hours=3,
                discipline="Mechanical"),
        Service(code="SCJ010", name="Gas Detection LEL", frequency_weeks=12,
                estimated_hours=4, discipline="Electrical"),
        Service(code="SCJ011", name="Gas Detection H2S", frequency_weeks=12,
                estimated_hours=4, discipline="Electrical"),
        Service(code="SCJ015", name="Fire Detection", frequency_weeks=24, estimated_hours=4,
                discipline="Electrical"),
        Service(code="SCJ020", name="Pressure Transmitter Calibration", frequency_weeks=26,
                estimated_hours=2, discipline="Electrical"),
        Service(code="SCJ030", name="UPS Inspection", frequency_weeks=12, estimated_hours=1,
                discipline="Electrical"),
    ]
    db.add_all(services)

    vendors = [
        Vendor(name="XYZ Company", contact_name="John Smith", phone="555-0100"),
        Vendor(name="VEN 01", contact_name="North Field Services"),
        Vendor(name="VEN 02", contact_name="Alberta Calibration"),
    ]
    db.add_all(vendors)

    personnel = [
        Personnel(first_name="Jeff", last_name="Bezruchak", position="MT",
                  discipline="Mechanical"),
        Personnel(first_name="Jason", last_name="Bilyk", position="ET",
                  discipline="Electrical"),
        Personnel(first_name="Jerry", last_name="Sinclair", position="ET",
                  discipline="Electrical"),
    ]
    db.add_all(personnel)

    db.commit()


def run() -> None:
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_demo(db)
    finally:
        db.close()


if __name__ == "__main__":
    run()