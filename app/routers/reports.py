"""Printable reports: Draft Plan, Final Plan, Work Order, Calibration Report.

HTML pages are print-styled (window.print()); a ``?format=pdf`` query renders
a downloadable PDF via WeasyPrint when available.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, joinedload

from app.dependencies import current_user, get_db
from app.models import Equipment, Plan, User
from app.templating import templates

router = APIRouter()


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


def _parse_date(value: str):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _render(ctx: dict, name: str, title: str):
    """Render one report as HTML or PDF depending on ctx['format']."""
    want_pdf = ctx.get("format") == "pdf"
    html = templates.env.get_template(name).render(ctx)
    if not want_pdf:
        return HTMLResponse(html)
    try:
        from weasyprint import HTML

        pdf = HTML(string=html).write_pdf()
        return Response(
            pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{title}.pdf"'},
        )
    except Exception:
        # Fall back to the printable HTML page if PDF generation is unavailable.
        ctx["pdf_unavailable"] = True
        return HTMLResponse(templates.env.get_template(name).render(ctx))


@router.get("/planning/draft/print")
def print_draft(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    q = _plan_query(db, Plan.DRAFT)
    from_d = _parse_date(request.query_params.get("from"))
    to_d = _parse_date(request.query_params.get("to"))
    if from_d:
        q = q.filter(Plan.proposed_date >= from_d)
    if to_d:
        q = q.filter(Plan.proposed_date <= to_d)
    ctx = {
        "request": request,
        "user": user,
        "plans": q.all(),
        "title": "DRAFT PLAN",
        "scheduled": False,
        "printed_by": user.display_name or user.username,
        "today": date.today(),
        "format": request.query_params.get("format"),
    }
    return _render(ctx, "reports/plan_print.html", "draft-plan")


@router.get("/planning/final/print")
def print_final(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    ctx = {
        "request": request,
        "user": user,
        "plans": _plan_query(db, Plan.SCHEDULED).all(),
        "title": "FINAL PLAN",
        "scheduled": True,
        "printed_by": user.display_name or user.username,
        "today": date.today(),
        "format": request.query_params.get("format"),
    }
    return _render(ctx, "reports/plan_print.html", "final-plan")


@router.get("/reports/work-order/{plan_id}")
def work_order(
    plan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    plan = (
        db.query(Plan)
        .options(
            joinedload(Plan.equipment).joinedload(Equipment.customer),
            joinedload(Plan.equipment).joinedload(Equipment.field),
            joinedload(Plan.equipment).joinedload(Equipment.location),
            joinedload(Plan.service),
            joinedload(Plan.vendor),
            joinedload(Plan.personnel),
        )
        .filter(Plan.id == plan_id)
        .first()
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    if not plan.wo_no:
        raise HTTPException(
            status_code=404,
            detail="This item has not been scheduled yet, so it has no work order.",
        )
    ctx = {
        "request": request,
        "user": user,
        "plan": plan,
        "today": date.today(),
        "printed_by": user.display_name or user.username,
        "format": request.query_params.get("format"),
    }
    return _render(ctx, "reports/work_order.html", f"work-order-{plan.wo_no}")


@router.get("/reports/calibration/{plan_id}")
def calibration(
    plan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    plan = (
        db.query(Plan)
        .options(
            joinedload(Plan.equipment).joinedload(Equipment.customer),
            joinedload(Plan.equipment).joinedload(Equipment.field),
            joinedload(Plan.equipment).joinedload(Equipment.location),
            joinedload(Plan.service),
            joinedload(Plan.vendor),
            joinedload(Plan.personnel),
        )
        .filter(Plan.id == plan_id)
        .first()
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Calibration report not found")
    if not plan.cm_no:
        raise HTTPException(
            status_code=404,
            detail="This item has not been scheduled yet, so it has no calibration report.",
        )
    ctx = {
        "request": request,
        "user": user,
        "plan": plan,
        "today": date.today(),
        "printed_by": user.display_name or user.username,
        "format": request.query_params.get("format"),
    }
    return _render(ctx, "reports/calibration.html", f"calibration-{plan.cm_no}")