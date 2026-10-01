"""Shared FastAPI dependencies."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

__all__ = ["get_db", "current_user", "require_admin"]


def _load_user(request: Request, db: Session) -> User:
    uid = request.session.get("uid")
    if uid is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.get(User, uid)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Require an authenticated session; returns the logged-in User."""
    return _load_user(request, db)


def require_admin(user: User = Depends(current_user)) -> User:
    """Require an authenticated admin user."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user