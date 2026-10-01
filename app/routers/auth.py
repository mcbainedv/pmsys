"""Login, logout, self-service password change, and admin user management."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import hash_password, password_too_long, verify_password
from app.dependencies import current_user, get_db, require_admin
from app.models import User
from app.templating import flash, templates

router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    if request.session.get("uid"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter_by(username=username.strip()).first()
    if user is None or not verify_password(password, user.password_hash) or not user.is_active:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username or password."},
            status_code=401,
        )
    request.session["uid"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/account")
def account(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return templates.TemplateResponse(
        request, "account.html", {"user": user, "account": user}
    )


@router.post("/account/password")
def change_password(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not verify_password(current_password, user.password_hash):
        flash(request, "Current password is incorrect.", "error")
    elif len(new_password) < 6:
        flash(request, "New password must be at least 6 characters.", "error")
    elif password_too_long(new_password):
        flash(request, "New password must be 72 bytes or fewer.", "error")
    elif new_password != confirm_password:
        flash(request, "New passwords do not match.", "error")
    else:
        user.password_hash = hash_password(new_password)
        db.commit()
        flash(request, "Password updated.", "success")
    return RedirectResponse("/account", status_code=303)


@router.get("/users")
def list_users(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    users = db.query(User).order_by(User.username).all()
    return templates.TemplateResponse(
        request, "users.html", {"user": user, "users": users}
    )


@router.post("/users")
def create_user(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(""),
    password: str = Form(...),
    role: str = Form("user"),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    username = username.strip()
    display_name = display_name.strip()
    if not username:
        flash(request, "Username is required.", "error")
    elif len(username) > 64:
        flash(request, "Username must be 64 characters or fewer.", "error")
    elif len(display_name) > 128:
        flash(request, "Display name must be 128 characters or fewer.", "error")
    elif db.query(User).filter_by(username=username).first():
        flash(request, f"Username '{username}' already exists.", "error")
    elif len(password) < 6:
        flash(request, "Password must be at least 6 characters.", "error")
    elif password_too_long(password):
        flash(request, "Password must be 72 bytes or fewer.", "error")
    else:
        db.add(
            User(
                username=username,
                display_name=display_name,
                password_hash=hash_password(password),
                role="admin" if role == "admin" else "user",
            )
        )
        db.commit()
        flash(request, f"User '{username}' created.", "success")
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/toggle")
def toggle_user(
    user_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)
):
    target = db.get(User, user_id)
    if target and target.id != user.id:
        target.is_active = not target.is_active
        db.commit()
    elif target is None:
        flash(request, "User not found.", "error")
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    request: Request,
    password: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    target = db.get(User, user_id)
    if target and len(password) >= 6 and not password_too_long(password):
        target.password_hash = hash_password(password)
        db.commit()
        flash(request, f"Password reset for '{target.username}'.", "success")
    elif target and password_too_long(password):
        flash(request, "Password must be 72 bytes or fewer.", "error")
    elif target:
        flash(request, "Password must be at least 6 characters.", "error")
    else:
        flash(request, "User not found.", "error")
    return RedirectResponse("/users", status_code=303)