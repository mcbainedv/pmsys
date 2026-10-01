"""SQLAlchemy ORM models.

Mirrors the original PMSyS data model:
    Customer -> Field -> Location -> Equipment
reference tables (Service, Vendor, Personnel), app Users, and the central
Plan work item that drives the Draft -> Schedule -> Closeout loop.
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """App login account (distinct from field Personnel)."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(16), default="user")  # "admin" | "user"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)

    # No delete cascade: a customer with fields (or a field with locations) must
    # not be silently removed together with its children — `_safe_delete` in
    # app/routers/setup.py turns the resulting IntegrityError into a refusal.
    fields: Mapped[list["Field"]] = relationship(back_populates="customer")


class Field(Base):
    """A named area within a customer (e.g. "Wild River")."""
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))

    customer: Mapped["Customer"] = relationship(back_populates="fields")
    locations: Mapped[list["Location"]] = relationship(back_populates="field")


class Location(Base):
    """A legal survey / site location string (e.g. "10-03-57-23W5")."""
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))

    field: Mapped["Field"] = relationship(back_populates="locations")


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    tag1: Mapped[str] = mapped_column(String(64))  # e.g. "FIT-1140"
    tag2: Mapped[str] = mapped_column(String(64), default="")  # e.g. "INLET"
    description: Mapped[str] = mapped_column(String(255), default="")
    equipment_type: Mapped[str] = mapped_column(String(64), default="")
    manufacturer: Mapped[str] = mapped_column(String(128), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    serial_no: Mapped[str] = mapped_column(String(128), default="")
    parts_list_no: Mapped[str] = mapped_column(String(128), default="")
    instruction_no: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    customer: Mapped["Customer"] = relationship()
    field: Mapped["Field"] = relationship()
    location: Mapped["Location"] = relationship()


class Service(Base):
    """A service code; `frequency_weeks` drives the scheduling formula."""
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # e.g. "SCJ008"
    name: Mapped[str] = mapped_column(String(128))
    frequency_weeks: Mapped[int] = mapped_column(Integer, default=4)
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float, default=None)
    discipline: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")


class Vendor(Base):
    """A service vendor (originally "Responsible Technician" -> "Service Vendor")."""
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    contact_name: Mapped[str] = mapped_column(String(128), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(128), default="")


class Personnel(Base):
    """A responsible technician."""
    __tablename__ = "personnel"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(64))
    last_name: Mapped[str] = mapped_column(String(64))
    position: Mapped[str] = mapped_column(String(32), default="")  # "MT"/"ET"/...
    discipline: Mapped[str] = mapped_column(String(64), default="")  # "Mechanical"/...
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Plan(Base):
    """A single preventive-maintenance work item.

    status drives placement: "draft" -> Draft Plan, "scheduled" -> Final Plan,
    "completed" -> History. wo_no/cm_no are stamped when scheduled.
    """
    __tablename__ = "plans"

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    last_completed_date: Mapped[date] = mapped_column(Date)
    proposed_date: Mapped[date] = mapped_column(Date)
    schedule_date: Mapped[Optional[date]] = mapped_column(Date, default=None)
    actual_date: Mapped[Optional[date]] = mapped_column(Date, default=None)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id"), default=None)
    personnel_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("personnel.id"), default=None
    )
    status: Mapped[str] = mapped_column(String(16), default=DRAFT, index=True)
    wo_no: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    cm_no: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    equipment: Mapped["Equipment"] = relationship()
    service: Mapped["Service"] = relationship()
    vendor: Mapped[Optional["Vendor"]] = relationship()
    personnel: Mapped[Optional["Personnel"]] = relationship()