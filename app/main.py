"""FastAPI application entry point."""
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.dependencies import current_user, get_db
from app.models import Equipment, Plan, User
from app.routers import auth, history, planning, reports, setup
from app.templating import flash, safe_back, templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.app_name)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=60 * 60 * 24 * 14,  # 2 weeks
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Human-readable text for the error page a browser lands on.
_ERROR_TEXT = {
    400: ("Bad request", "The request could not be understood."),
    403: ("Not allowed", "You do not have permission to open that page."),
    404: ("Not found", "That page or record does not exist."),
    405: ("Method not allowed", "That action is not available on this page."),
    422: ("Invalid request", "The submitted form was incomplete or invalid."),
    500: ("Server error", "Something went wrong while handling that request. "
                         "The details were logged — please try again."),
}


def _error_page(request: Request, status_code: int, message: str | None = None):
    title, default = _ERROR_TEXT.get(status_code, ("Error", "Something went wrong."))
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status": status_code, "title": title, "message": message or default},
        status_code=status_code,
    )


@app.exception_handler(StarletteHTTPException)
async def unauth_redirect(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        return RedirectResponse("/login", status_code=303)
    detail = exc.detail if isinstance(exc.detail, str) else None
    return _error_page(request, exc.status_code, detail)


@app.exception_handler(RequestValidationError)
async def invalid_form(request: Request, exc: RequestValidationError):
    """Never leak FastAPI's raw JSON 422 to a browser form submission."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        flash(request, "That form was incomplete or invalid — please check the fields and try again.", "error")
        return RedirectResponse(safe_back(request), status_code=303)
    return _error_page(request, 422, "The link you followed contained an invalid value.")


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    """Render the styled error page for unexpected 500s instead of plain text."""
    return _error_page(request, 500)


app.include_router(auth.router)
app.include_router(setup.router)
app.include_router(planning.router)
app.include_router(history.router)
app.include_router(reports.router)


@app.get("/")
def home(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    today = date.today()
    soon = today + timedelta(days=30)
    due_soon = (
        db.query(Plan)
        .options(
            joinedload(Plan.equipment).joinedload(Equipment.location),
            joinedload(Plan.service),
        )
        .filter(Plan.status == Plan.DRAFT, Plan.proposed_date <= soon)
        .order_by(Plan.proposed_date, Plan.id)
        .all()
    )
    stats = {
        "draft": db.query(Plan).filter(Plan.status == Plan.DRAFT).count(),
        "scheduled": db.query(Plan).filter(Plan.status == Plan.SCHEDULED).count(),
        "completed": db.query(Plan).filter(Plan.status == Plan.COMPLETED).count(),
    }
    return templates.TemplateResponse(
        request,
        "home.html",
        {"user": user, "due_soon": due_soon, "stats": stats, "today": today},
    )