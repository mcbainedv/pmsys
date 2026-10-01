"""The core planning loop: Draft Plan -> Schedule -> Final Plan -> Closeout."""
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.dependencies import current_user, get_db
from app.models import Customer, Equipment, Field, Location, Personnel, Plan, Service, User, Vendor
from app.services import calibration_no, proposed_date, work_order_no
from app.services import auto_assign as auto_assign_personnel
from app.templating import flash, safe_back, templates

router = APIRouter(prefix="/planning")


def _parse_date(value: str, default=None):
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


def _parse_date_strict(value: str):
    """Return (date, error). Empty -> (None, None); unparseable -> (None, message)."""
    if not value:
        return None, None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, "Please enter dates in YYYY-MM-DD format."


def _plan_query(db: Session, *statuses: str):
    return (
        db.query(Plan)
        .options(
            joinedload(Plan.equipment).joinedload(Equipment.customer),
            joinedload(Plan.equipment).joinedload(Equipment.field),
            joinedload(Plan.equipment).joinedload(Equipment.location),
            joinedload(Plan.service),
            joinedload(Plan.vendor),
            joinedload(Plan.personnel),
        )
        .filter(Plan.status.in_(statuses))
        .order_by(Plan.proposed_date, Plan.id)
    )


def _last_completed_for(db: Session, equipment_id: int, service_id: int):
    row = (
        db.query(Plan)
        .filter(
            Plan.equipment_id == equipment_id,
            Plan.service_id == service_id,
            Plan.status == Plan.COMPLETED,
            Plan.actual_date.isnot(None),
        )
        .order_by(Plan.actual_date.desc())
        .first()
    )
    return row.actual_date if row else None


def _active_equipment(db: Session):
    return (
        db.query(Equipment)
        .options(
            joinedload(Equipment.customer),
            joinedload(Equipment.field),
            joinedload(Equipment.location),
        )
        .filter(Equipment.is_active.is_(True))
        .order_by(Equipment.tag1)
        .all()
    )


def _form_context(db: Session):
    return {
        "services": db.query(Service).order_by(Service.code).all(),
        "vendors": db.query(Vendor).order_by(Vendor.name).all(),
        "personnel": db.query(Personnel).filter(Personnel.is_active.is_(True))
        .order_by(Personnel.last_name).all(),
        "equipment": _active_equipment(db),
        "customers": db.query(Customer).order_by(Customer.name).all(),
    }


@router.get("/draft")
def draft(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = _plan_query(db, Plan.DRAFT)
    from_d = _parse_date(request.query_params.get("from"))
    to_d = _parse_date(request.query_params.get("to"))
    if request.query_params.get("from") and not from_d:
        flash(request, "Ignoring the 'due from' date — please use YYYY-MM-DD.", "error")
    if request.query_params.get("to") and not to_d:
        flash(request, "Ignoring the 'due to' date — please use YYYY-MM-DD.", "error")
    if from_d:
        q = q.filter(Plan.proposed_date >= from_d)
    if to_d:
        q = q.filter(Plan.proposed_date <= to_d)
    ctx = _form_context(db)
    ctx.update(
        {
            "user": user,
            "plans": q.all(),
            "from_d": from_d,
            "to_d": to_d,
            "today": date.today(),
        }
    )
    return templates.TemplateResponse(request, "planning/draft.html", ctx)


@router.post("/draft/add")
def draft_add(
    request: Request,
    service_id: int = Form(0),
    equipment_ids: list[int] = Form([]),
    proposed_date_override: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    service = db.get(Service, service_id)
    if service is None:
        flash(request, "Please choose a service.", "error")
        return RedirectResponse("/planning/draft", status_code=303)
    if not equipment_ids:
        flash(request, "Select at least one equipment item.", "error")
        return RedirectResponse("/planning/draft", status_code=303)

    override, err = _parse_date_strict(proposed_date_override)
    if err:
        flash(request, err, "error")
        return RedirectResponse("/planning/draft", status_code=303)

    # Never queue the same equipment + service twice while it is still open.
    already_open = {
        (p.equipment_id, p.service_id)
        for p in db.query(Plan)
        .filter(
            Plan.service_id == service_id,
            Plan.status.in_([Plan.DRAFT, Plan.SCHEDULED]),
        )
        .all()
    }
    created = 0
    skipped = 0
    today = date.today()
    for eid in equipment_ids:
        if db.get(Equipment, eid) is None or (eid, service_id) in already_open:
            skipped += 1
            continue
        last_completed = _last_completed_for(db, eid, service_id) or today
        prop = override or proposed_date(last_completed, service.frequency_weeks)
        db.add(
            Plan(
                equipment_id=eid,
                service_id=service_id,
                last_completed_date=last_completed,
                proposed_date=prop,
                status=Plan.DRAFT,
            )
        )
        already_open.add((eid, service_id))
        created += 1
    db.commit()
    message = f"Added {created} item(s) to the draft plan."
    if skipped:
        message += f" {skipped} selection(s) skipped — already open or unknown equipment."
    flash(request, message, "success")
    return RedirectResponse("/planning/draft", status_code=303)


@router.post("/draft/delete")
def draft_delete(
    request: Request,
    plan_ids: list[int] = Form([]),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rows = db.query(Plan).filter(Plan.id.in_(plan_ids), Plan.status == Plan.DRAFT).all()
    for r in rows:
        db.delete(r)
    db.commit()
    flash(request, f"Deleted {len(rows)} item(s).", "success")
    return RedirectResponse("/planning/draft", status_code=303)


@router.post("/schedule")
def schedule(
    request: Request,
    plan_ids: list[int] = Form([]),
    schedule_date: str = Form(""),
    vendor_id: int = Form(0),
    personnel_id: int = Form(0),
    auto_assign: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    plans = (
        db.query(Plan).filter(Plan.id.in_(plan_ids), Plan.status == Plan.DRAFT).all()
    )
    if not plans:
        flash(request, "Select at least one draft item to schedule.", "error")
        return RedirectResponse("/planning/draft", status_code=303)

    sdate, err = _parse_date_strict(schedule_date)
    if err:
        flash(request, err, "error")
        return RedirectResponse("/planning/draft", status_code=303)
    sdate = sdate or date.today()

    if vendor_id and db.get(Vendor, vendor_id) is None:
        flash(request, "Please choose an existing service vendor.", "error")
        return RedirectResponse("/planning/draft", status_code=303)
    if personnel_id and db.get(Personnel, personnel_id) is None:
        flash(request, "Please choose an existing technician.", "error")
        return RedirectResponse("/planning/draft", status_code=303)

    assign_map: dict[int, int] = {}
    if auto_assign == "on":
        active_personnel = (
            db.query(Personnel).filter(Personnel.is_active.is_(True)).all()
        )
        try:
            grouping = auto_assign_personnel(plans, active_personnel)
        except ValueError:
            flash(request, "No active technicians available to auto-assign.", "error")
            return RedirectResponse("/planning/draft", status_code=303)
        for pid, pls in grouping.items():
            for pl in pls:
                assign_map[pl.id] = pid

    for p in plans:
        p.status = Plan.SCHEDULED
        p.schedule_date = sdate
        p.vendor_id = vendor_id or None
        p.personnel_id = assign_map.get(p.id, personnel_id or None)
        p.wo_no = work_order_no(p.id)
        p.cm_no = calibration_no(p.id)
    db.commit()
    flash(request, f"Scheduled {len(plans)} item(s).", "success")
    return RedirectResponse("/planning/final", status_code=303)


@router.get("/final")
def final(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    ctx = _form_context(db)
    ctx.update(
        {
            "user": user,
            "plans": _plan_query(db, Plan.SCHEDULED).all(),
            "today": date.today(),
        }
    )
    return templates.TemplateResponse(request, "planning/final.html", ctx)


@router.post("/closeout")
def closeout(
    request: Request,
    plan_ids: list[int] = Form([]),
    actual_date: str = Form(""),
    actual_vendor_id: int = Form(0),
    actual_personnel_id: int = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    plans = (
        db.query(Plan).filter(Plan.id.in_(plan_ids), Plan.status == Plan.SCHEDULED).all()
    )
    if not plans:
        flash(request, "Select at least one item to close out.", "error")
        return RedirectResponse("/planning/final", status_code=303)

    adate, err = _parse_date_strict(actual_date)
    if err:
        flash(request, err, "error")
        return RedirectResponse("/planning/final", status_code=303)
    adate = adate or date.today()

    if actual_vendor_id and db.get(Vendor, actual_vendor_id) is None:
        flash(request, "Please choose an existing service vendor.", "error")
        return RedirectResponse("/planning/final", status_code=303)
    if actual_personnel_id and db.get(Personnel, actual_personnel_id) is None:
        flash(request, "Please choose an existing technician.", "error")
        return RedirectResponse("/planning/final", status_code=303)

    for p in plans:
        p.status = Plan.COMPLETED
        p.actual_date = adate
        if actual_vendor_id:
            p.vendor_id = actual_vendor_id
        if actual_personnel_id:
            p.personnel_id = actual_personnel_id
    db.commit()
    flash(request, f"Closed out {len(plans)} item(s).", "success")
    return RedirectResponse("/history", status_code=303)


@router.post("/cancel")
def cancel(
    request: Request,
    plan_ids: list[int] = Form([]),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Cancel approved/scheduled work that will not be carried out."""
    plans = (
        db.query(Plan)
        .filter(Plan.id.in_(plan_ids), Plan.status == Plan.SCHEDULED)
        .all()
    )
    if not plans:
        flash(request, "Select at least one scheduled item to cancel.", "error")
        return RedirectResponse("/planning/final", status_code=303)
    for p in plans:
        p.status = Plan.CANCELLED
    db.commit()
    flash(request, f"Cancelled {len(plans)} item(s).", "success")
    return RedirectResponse(safe_back(request, "/planning/final"), status_code=303)