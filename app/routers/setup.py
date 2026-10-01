"""Setup tab CRUD: Customers, Fields, Locations, Equipment, Services,
Vendors and Personnel. Mirrors the original "Update" tab (reordered per the
review: Location Data, Equipment Data, Service Code Data, Service Vendor).
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.dependencies import current_user, get_db
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
from app.templating import flash, safe_back, templates

router = APIRouter(prefix="/setup")


def _int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _float(value, default=None):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


# Column widths from app/models.py — values longer than these raise a DB error
# ("Data too long for column") which used to surface as an HTTP 500.
MAX_NAME = 128
MAX_CODE = 32
MAX_TAG = 64
MAX_SHORT = 64
MAX_DESC = 255


def _overlong(*pairs) -> str:
    """Return a flash message for the first (label, value, limit) that is too long."""
    for label, value, limit in pairs:
        if value and len(value) > limit:
            return f"{label} must be {limit} characters or fewer."
    return ""


def _edit_id(edit) -> int:
    """Tolerate a stale/garbage ?edit= value instead of returning a 422."""
    return _int(edit, 0)


def _customer_options(db: Session):
    return [(c.id, c.name) for c in db.query(Customer).order_by(Customer.name)]


def _field_options(db: Session):
    return [
        (f.id, f"{f.customer.name} / {f.name}")
        for f in db.query(Field).join(Customer).order_by(Customer.name, Field.name)
    ]


def _location_options(db: Session):
    return [
        (l.id, f"{l.field.customer.name} / {l.field.name} / {l.name}")
        for l in db.query(Location).join(Field).join(Customer)
        .order_by(Customer.name, Field.name, Location.name)
    ]


def _safe_delete(
    db: Session, obj, request: Request, label: str, fallback: str = "/setup/equipment"
) -> RedirectResponse:
    db.delete(obj)
    try:
        db.commit()
        flash(request, f"{label} deleted.", "success")
    except IntegrityError:
        db.rollback()
        flash(request, f"Cannot delete '{label}': it still has dependent records.", "error")
    return RedirectResponse(safe_back(request, fallback), status_code=303)


# --- Customers ---------------------------------------------------------------

@router.get("/customers")
def customers(request: Request, edit: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Customer).order_by(Customer.name).all()
    edit_id = _edit_id(edit)
    return templates.TemplateResponse(
        request, "setup/customers.html",
        {"user": user, "rows": rows, "edit_obj": db.get(Customer, edit_id) if edit_id else None},
    )


@router.post("/customers")
def customer_save(
    request: Request,
    name: str = Form(""),
    customer_id: int = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    name = name.strip()
    if not name:
        flash(request, "Customer name is required.", "error")
        return RedirectResponse("/setup/customers", status_code=303)
    err = _overlong(("Customer name", name, MAX_NAME))
    if err:
        flash(request, err, "error")
        return RedirectResponse("/setup/customers", status_code=303)
    duplicate = (
        db.query(Customer)
        .filter(func.lower(Customer.name) == name.lower(), Customer.id != customer_id)
        .first()
    )
    if duplicate:
        flash(request, f"Customer '{name}' already exists.", "error")
        return RedirectResponse("/setup/customers", status_code=303)
    if customer_id:
        obj = db.get(Customer, customer_id)
        if obj:
            obj.name = name
            db.commit()
            flash(request, "Customer updated.", "success")
        else:
            flash(request, "Customer not found.", "error")
    else:
        db.add(Customer(name=name))
        db.commit()
        flash(request, f"Customer '{name}' added.", "success")
    return RedirectResponse("/setup/customers", status_code=303)


@router.post("/customers/{cid}/delete")
def customer_delete(cid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    obj = db.get(Customer, cid)
    if obj is None:
        flash(request, "Customer not found.", "error")
        return RedirectResponse("/setup/customers", status_code=303)
    return _safe_delete(db, obj, request, f"Customer '{obj.name}'", "/setup/customers")


# --- Fields ------------------------------------------------------------------

@router.get("/fields")
def fields(request: Request, edit: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Field).options(joinedload(Field.customer)).order_by(Field.name).all()
    edit_id = _edit_id(edit)
    return templates.TemplateResponse(
        request, "setup/fields.html",
        {"user": user, "rows": rows, "customers": _customer_options(db),
         "edit_obj": db.get(Field, edit_id) if edit_id else None},
    )


@router.post("/fields")
def field_save(
    request: Request,
    name: str = Form(""),
    customer_id: int = Form(0),
    field_id: int = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    name = name.strip()
    if not name or not customer_id:
        flash(request, "Field name and customer are required.", "error")
        return RedirectResponse("/setup/fields", status_code=303)
    if db.get(Customer, customer_id) is None:
        flash(request, "Please choose an existing customer.", "error")
        return RedirectResponse("/setup/fields", status_code=303)
    err = _overlong(("Field name", name, MAX_NAME))
    if err:
        flash(request, err, "error")
        return RedirectResponse("/setup/fields", status_code=303)
    if field_id:
        obj = db.get(Field, field_id)
        if obj:
            obj.name = name
            obj.customer_id = customer_id
            db.commit()
            flash(request, "Field updated.", "success")
        else:
            flash(request, "Field not found.", "error")
    else:
        db.add(Field(name=name, customer_id=customer_id))
        db.commit()
        flash(request, f"Field '{name}' added.", "success")
    return RedirectResponse("/setup/fields", status_code=303)


@router.post("/fields/{fid}/delete")
def field_delete(fid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    obj = db.get(Field, fid)
    if obj is None:
        flash(request, "Field not found.", "error")
        return RedirectResponse("/setup/fields", status_code=303)
    return _safe_delete(db, obj, request, f"Field '{obj.name}'", "/setup/fields")


# --- Locations ---------------------------------------------------------------

@router.get("/locations")
def locations(request: Request, edit: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Location).options(joinedload(Location.field)).order_by(Location.name).all()
    edit_id = _edit_id(edit)
    return templates.TemplateResponse(
        request, "setup/locations.html",
        {"user": user, "rows": rows, "fields": _field_options(db),
         "edit_obj": db.get(Location, edit_id) if edit_id else None},
    )


@router.post("/locations")
def location_save(
    request: Request,
    name: str = Form(""),
    field_id: int = Form(0),
    location_id: int = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    name = name.strip()
    if not name or not field_id:
        flash(request, "Location name and field are required.", "error")
        return RedirectResponse("/setup/locations", status_code=303)
    if db.get(Field, field_id) is None:
        flash(request, "Please choose an existing field.", "error")
        return RedirectResponse("/setup/locations", status_code=303)
    err = _overlong(("Location", name, MAX_NAME))
    if err:
        flash(request, err, "error")
        return RedirectResponse("/setup/locations", status_code=303)
    if location_id:
        obj = db.get(Location, location_id)
        if obj:
            obj.name = name
            obj.field_id = field_id
            db.commit()
            flash(request, "Location updated.", "success")
        else:
            flash(request, "Location not found.", "error")
    else:
        db.add(Location(name=name, field_id=field_id))
        db.commit()
        flash(request, f"Location '{name}' added.", "success")
    return RedirectResponse("/setup/locations", status_code=303)


@router.post("/locations/{lid}/delete")
def location_delete(lid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    obj = db.get(Location, lid)
    if obj is None:
        flash(request, "Location not found.", "error")
        return RedirectResponse("/setup/locations", status_code=303)
    return _safe_delete(db, obj, request, f"Location '{obj.name}'", "/setup/locations")


# --- Equipment ---------------------------------------------------------------

@router.get("/equipment")
def equipment(request: Request, edit: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = (
        db.query(Equipment)
        .options(
            joinedload(Equipment.customer),
            joinedload(Equipment.field),
            joinedload(Equipment.location),
        )
        .order_by(Equipment.tag1)
        .all()
    )
    edit_id = _edit_id(edit)
    return templates.TemplateResponse(
        request, "setup/equipment.html",
        {
            "user": user,
            "rows": rows,
            "customers": _customer_options(db),
            "fields": _field_options(db),
            "locations": _location_options(db),
            "edit_obj": db.get(Equipment, edit_id) if edit_id else None,
        },
    )


@router.post("/equipment")
def equipment_save(
    request: Request,
    customer_id: int = Form(0),
    field_id: int = Form(0),
    location_id: int = Form(0),
    tag1: str = Form(""),
    tag2: str = Form(""),
    description: str = Form(""),
    equipment_type: str = Form(""),
    manufacturer: str = Form(""),
    model: str = Form(""),
    serial_no: str = Form(""),
    parts_list_no: str = Form(""),
    instruction_no: str = Form(""),
    is_active: str = Form(""),
    equipment_id: int = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    tag1 = tag1.strip()
    if not tag1:
        flash(request, "Equipment tag (Tag 1) is required.", "error")
        return RedirectResponse("/setup/equipment", status_code=303)

    # Validate the Customer / Field / Location chain before touching the DB:
    # the FK columns are NOT NULL, so a bogus id used to raise a 500.
    customer = db.get(Customer, customer_id) if customer_id else None
    field = db.get(Field, field_id) if field_id else None
    location = db.get(Location, location_id) if location_id else None
    if customer is None:
        flash(request, "Please choose a customer.", "error")
        return RedirectResponse("/setup/equipment", status_code=303)
    if field is None or field.customer_id != customer.id:
        flash(request, "Please choose a field that belongs to the selected customer.", "error")
        return RedirectResponse("/setup/equipment", status_code=303)
    if location is None or location.field_id != field.id:
        flash(request, "Please choose a location that belongs to the selected field.", "error")
        return RedirectResponse("/setup/equipment", status_code=303)

    err = _overlong(
        ("Tag 1", tag1, MAX_TAG),
        ("Tag 2", tag2.strip(), MAX_TAG),
        ("Description", description.strip(), MAX_DESC),
        ("Type", equipment_type.strip(), MAX_SHORT),
        ("Manufacturer", manufacturer.strip(), MAX_NAME),
        ("Model", model.strip(), MAX_NAME),
        ("Serial no.", serial_no.strip(), MAX_NAME),
        ("Parts list no.", parts_list_no.strip(), MAX_NAME),
        ("Instruction no.", instruction_no.strip(), MAX_NAME),
    )
    if err:
        flash(request, err, "error")
        return RedirectResponse("/setup/equipment", status_code=303)

    fields = {
        "customer_id": customer.id,
        "field_id": field.id,
        "location_id": location.id,
        "tag1": tag1,
        "tag2": tag2.strip(),
        "description": description.strip(),
        "equipment_type": equipment_type.strip(),
        "manufacturer": manufacturer.strip(),
        "model": model.strip(),
        "serial_no": serial_no.strip(),
        "parts_list_no": parts_list_no.strip(),
        "instruction_no": instruction_no.strip(),
        "is_active": is_active == "on",
    }
    if equipment_id:
        obj = db.get(Equipment, equipment_id)
        if obj:
            for k, v in fields.items():
                setattr(obj, k, v)
            db.commit()
            flash(request, f"Equipment '{tag1}' updated.", "success")
        else:
            flash(request, "Equipment not found.", "error")
    else:
        db.add(Equipment(**fields))
        db.commit()
        flash(request, f"Equipment '{tag1}' added.", "success")
    return RedirectResponse("/setup/equipment", status_code=303)


@router.post("/equipment/{eid}/delete")
def equipment_delete(eid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    obj = db.get(Equipment, eid)
    if obj is None:
        flash(request, "Equipment not found.", "error")
        return RedirectResponse("/setup/equipment", status_code=303)
    return _safe_delete(db, obj, request, f"Equipment '{obj.tag1}'", "/setup/equipment")


# --- Services ----------------------------------------------------------------

@router.get("/services")
def services(request: Request, edit: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Service).order_by(Service.code).all()
    edit_id = _edit_id(edit)
    return templates.TemplateResponse(
        request, "setup/services.html",
        {"user": user, "rows": rows, "edit_obj": db.get(Service, edit_id) if edit_id else None},
    )


@router.post("/services")
def service_save(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    frequency_weeks: str = Form("4"),
    estimated_hours: str = Form(""),
    discipline: str = Form(""),
    description: str = Form(""),
    service_id: int = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    code = code.strip()
    name = name.strip()
    if not code or not name:
        flash(request, "Service code and name are required.", "error")
        return RedirectResponse("/setup/services", status_code=303)
    freq = _int(frequency_weeks, 0)
    if not 1 <= freq <= 520:
        flash(request, "Frequency must be a whole number of weeks between 1 and 520.", "error")
        return RedirectResponse("/setup/services", status_code=303)
    err = _overlong(
        ("Service code", code, MAX_CODE),
        ("Service name", name, MAX_NAME),
        ("Discipline", discipline.strip(), MAX_SHORT),
    )
    if err:
        flash(request, err, "error")
        return RedirectResponse("/setup/services", status_code=303)
    duplicate = (
        db.query(Service)
        .filter(func.lower(Service.code) == code.lower(), Service.id != service_id)
        .first()
    )
    if duplicate:
        flash(request, f"Service code '{code}' already exists.", "error")
        return RedirectResponse("/setup/services", status_code=303)
    hours = _float(estimated_hours)
    if hours is not None and (hours < 0 or hours > 100000 or hours != hours):
        flash(request, "Estimated hours must be a number between 0 and 100000.", "error")
        return RedirectResponse("/setup/services", status_code=303)
    data = {
        "code": code,
        "name": name,
        "frequency_weeks": freq,
        "estimated_hours": hours,
        "discipline": discipline.strip(),
        "description": description.strip(),
    }
    if service_id:
        obj = db.get(Service, service_id)
        if obj:
            for k, v in data.items():
                setattr(obj, k, v)
            db.commit()
            flash(request, f"Service '{code}' updated.", "success")
        else:
            flash(request, "Service not found.", "error")
    else:
        db.add(Service(**data))
        db.commit()
        flash(request, f"Service '{code}' added.", "success")
    return RedirectResponse("/setup/services", status_code=303)


@router.post("/services/{sid}/delete")
def service_delete(sid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    obj = db.get(Service, sid)
    if obj is None:
        flash(request, "Service not found.", "error")
        return RedirectResponse("/setup/services", status_code=303)
    return _safe_delete(db, obj, request, f"Service '{obj.code}'", "/setup/services")


# --- Vendors -----------------------------------------------------------------

@router.get("/vendors")
def vendors(request: Request, edit: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Vendor).order_by(Vendor.name).all()
    edit_id = _edit_id(edit)
    return templates.TemplateResponse(
        request, "setup/vendors.html",
        {"user": user, "rows": rows, "edit_obj": db.get(Vendor, edit_id) if edit_id else None},
    )


@router.post("/vendors")
def vendor_save(
    request: Request,
    name: str = Form(""),
    contact_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    vendor_id: int = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    name = name.strip()
    if not name:
        flash(request, "Vendor name is required.", "error")
        return RedirectResponse("/setup/vendors", status_code=303)
    err = _overlong(
        ("Vendor name", name, MAX_NAME),
        ("Contact name", contact_name.strip(), MAX_NAME),
        ("Phone", phone.strip(), MAX_SHORT),
        ("Email", email.strip(), MAX_NAME),
    )
    if err:
        flash(request, err, "error")
        return RedirectResponse("/setup/vendors", status_code=303)
    duplicate = (
        db.query(Vendor)
        .filter(func.lower(Vendor.name) == name.lower(), Vendor.id != vendor_id)
        .first()
    )
    if duplicate:
        flash(request, f"Vendor '{name}' already exists.", "error")
        return RedirectResponse("/setup/vendors", status_code=303)
    data = {"name": name, "contact_name": contact_name.strip(), "phone": phone.strip(), "email": email.strip()}
    if vendor_id:
        obj = db.get(Vendor, vendor_id)
        if obj:
            for k, v in data.items():
                setattr(obj, k, v)
            db.commit()
            flash(request, f"Vendor '{name}' updated.", "success")
        else:
            flash(request, "Vendor not found.", "error")
    else:
        db.add(Vendor(**data))
        db.commit()
        flash(request, f"Vendor '{name}' added.", "success")
    return RedirectResponse("/setup/vendors", status_code=303)


@router.post("/vendors/{vid}/delete")
def vendor_delete(vid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    obj = db.get(Vendor, vid)
    if obj is None:
        flash(request, "Vendor not found.", "error")
        return RedirectResponse("/setup/vendors", status_code=303)
    return _safe_delete(db, obj, request, f"Vendor '{obj.name}'", "/setup/vendors")


# --- Personnel ---------------------------------------------------------------

@router.get("/personnel")
def personnel(request: Request, edit: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Personnel).order_by(Personnel.last_name, Personnel.first_name).all()
    edit_id = _edit_id(edit)
    return templates.TemplateResponse(
        request, "setup/personnel.html",
        {"user": user, "rows": rows, "edit_obj": db.get(Personnel, edit_id) if edit_id else None},
    )


@router.post("/personnel")
def personnel_save(
    request: Request,
    first_name: str = Form(""),
    last_name: str = Form(""),
    position: str = Form(""),
    discipline: str = Form(""),
    is_active: str = Form(""),
    personnel_id: int = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    first_name = first_name.strip()
    last_name = last_name.strip()
    if not first_name or not last_name:
        flash(request, "First and last name are required.", "error")
        return RedirectResponse("/setup/personnel", status_code=303)
    err = _overlong(
        ("First name", first_name, MAX_SHORT),
        ("Last name", last_name, MAX_SHORT),
        ("Position", position.strip(), MAX_CODE),
        ("Discipline", discipline.strip(), MAX_SHORT),
    )
    if err:
        flash(request, err, "error")
        return RedirectResponse("/setup/personnel", status_code=303)
    data = {
        "first_name": first_name,
        "last_name": last_name,
        "position": position.strip(),
        "discipline": discipline.strip(),
        "is_active": is_active == "on",
    }
    if personnel_id:
        obj = db.get(Personnel, personnel_id)
        if obj:
            for k, v in data.items():
                setattr(obj, k, v)
            db.commit()
            flash(request, f"Technician '{first_name} {last_name}' updated.", "success")
        else:
            flash(request, "Technician not found.", "error")
    else:
        db.add(Personnel(**data))
        db.commit()
        flash(request, f"Technician '{first_name} {last_name}' added.", "success")
    return RedirectResponse("/setup/personnel", status_code=303)


@router.post("/personnel/{pid}/delete")
def personnel_delete(pid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    obj = db.get(Personnel, pid)
    if obj is None:
        flash(request, "Technician not found.", "error")
        return RedirectResponse("/setup/personnel", status_code=303)
    return _safe_delete(db, obj, request, f"Technician '{obj.first_name} {obj.last_name}'", "/setup/personnel")
