"""Jinja2 setup and small helpers shared by all routers."""
from pathlib import Path
from typing import Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def fmt_date(value) -> str:
    return value.strftime("%Y-%m-%d") if value else ""


templates.env.filters["fmt_date"] = fmt_date


def flash(request: Request, message: str, kind: str = "info") -> None:
    """Store a one-shot message to show on the next rendered page."""
    request.session["_flash"] = (message, kind)


def safe_back(request: Request, default: str = "/") -> str:
    """Referer for a form POST, restricted to this site (no open redirect).

    A cross-site Referer is discarded completely: keeping only its path would
    still let an attacker choose the page the user lands on.
    """
    ref = request.headers.get("referer") or default
    if ref.startswith(("http://", "https://")):
        from urllib.parse import urlsplit

        parts = urlsplit(ref)
        if parts.netloc and parts.netloc != request.url.netloc:
            return default
        ref = parts.path or default
        if parts.query:
            ref = f"{ref}?{parts.query}"
    return ref if ref.startswith("/") else default