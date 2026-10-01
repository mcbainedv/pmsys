"""History of completed / cancelled maintenance work."""
from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload

from app.dependencies import current_user, get_db
from app.models import Customer, Equipment, Field, Location, Plan, Service, User
from app.templating import flash, templates

router = APIRouter()


def _parse_date(value: str):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@router.get("/history")
def history(
    request: Request,
    customer_id: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    # Tolerate a stale/garbage ?customer_id= instead of returning a 422 page.
    try:
        customer_id = int(customer_id)
    except (TypeError, ValueError):
        customer_id = 0
    q = (
        db.query(Plan)
        .options(
            joinedload(Plan.equipment).joinedload(Equipment.customer),
            joinedload(Plan.equipment).joinedload(Equipment.field),
            joinedload(Plan.equipment).joinedload(Equipment.location),
            joinedload(Plan.service),
            joinedload(Plan.vendor),
            joinedload(Plan.personnel),
        )
        .filter(Plan.status.in_([Plan.COMPLETED, Plan.CANCELLED]))
        .order_by(Plan.actual_date.desc(), Plan.id.desc())
    )
    if customer_id:
        q = q.join(Equipment, Plan.equipment_id == Equipment.id).filter(
            Equipment.customer_id == customer_id
        )
    from_d = _parse_date(request.query_params.get("from"))
    to_d = _parse_date(request.query_params.get("to"))
    if request.query_params.get("from") and not from_d:
        flash(request, "Ignoring the 'completed from' date — please use YYYY-MM-DD.", "error")
    if request.query_params.get("to") and not to_d:
        flash(request, "Ignoring the 'completed to' date — please use YYYY-MM-DD.", "error")
    if from_d:
        q = q.filter(Plan.actual_date >= from_d)
    if to_d:
        q = q.filter(Plan.actual_date <= to_d)

    ctx = {
        "user": user,
        "plans": q.all(),
        "customers": db.query(Customer).order_by(Customer.name).all(),
        "customer_id": customer_id,
        "from_d": from_d,
        "to_d": to_d,
    }
    return templates.TemplateResponse(request, "history.html", ctx)