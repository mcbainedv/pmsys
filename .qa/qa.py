#!/usr/bin/env python3
"""Shared live-QA harness for the PMSyS rebuild.

Target: http://127.0.0.1:8000  (Docker container `pmsys-app-1`, MariaDB `pmsys-db-1`)

Library use
-----------
    from qa import QA
    q = QA(prefix="SETUP")
    r = q.get("/setup/customers")
    q.save("customers_list", r)
    q.finding("F-SETUP-001", "Delete of a customer 500s", severity="high",
              area="setup", action="POST /setup/customers/1/delete",
              steps=["..."], expected="flash error", actual="HTTP 500",
              evidence="customers_delete.html", cause="app/routers/setup.py:60")

CLI use
-------
    python .qa/qa.py login
    python .qa/qa.py get /planning/draft
    python .qa/qa.py post /setup/customers name=QA-X
    python .qa/qa.py forms /planning/draft
    python .qa/qa.py links /planning/final
    python .qa/qa.py db "select count(*) from plans"

Notes
-----
* Every QA instance logs in as admin/admin by default.
* Never change the admin password and never deactivate the admin user.
* Created records must be prefixed with the area name (e.g. ``QA-SETUP-``).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent
EVID = ROOT / "evidence"
EVID.mkdir(exist_ok=True)

DB_CONTAINER = "pmsys-db-1"
DB_CMD = ["mariadb", "-upmsys", "-ppmsys_secret", "pmsys", "-e"]


class _PageParser(HTMLParser):
    """Collect forms, form fields, buttons and links from a page."""

    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict] = []
        self.links: list[str] = []
        self._cur: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            href = a.get("href")
            if href:
                self.links.append(href)
        elif tag == "form":
            self._cur = {
                "method": (a.get("method") or "get").lower(),
                "action": a.get("action", ""),
                "fields": [],
                "buttons": [],
            }
        elif tag in ("input", "select", "textarea") and self._cur is not None:
            self._cur["fields"].append(
                {
                    "name": a.get("name"),
                    "type": a.get("type"),
                    "value": a.get("value"),
                    "required": "required" in a,
                }
            )
        elif tag == "button" and self._cur is not None:
            self._cur["buttons"].append(
                {
                    "type": a.get("type") or "submit",
                    "formaction": a.get("formaction", ""),
                    "text": "",
                }
            )

    def handle_data(self, data):
        if self._cur is not None and self._cur["buttons"] and data.strip():
            self._cur["buttons"][-1]["text"] += data.strip()

    def handle_endtag(self, tag):
        if tag == "form" and self._cur is not None:
            self.forms.append(self._cur)
            self._cur = None


def parse(html: str) -> _PageParser:
    p = _PageParser()
    p.feed(html)
    return p


class QA:
    def __init__(self, prefix: str = "QA", base: str = BASE,
                 username: str = "admin", password: str = "admin") -> None:
        self.prefix = prefix
        self.base = base
        self.findings_file = ROOT / f"findings_{prefix.lower()}.md"
        self.client = httpx.Client(base_url=base, follow_redirects=False, timeout=60.0)
        self.login(username, password)

    # -- auth ---------------------------------------------------------------
    def login(self, username: str = "admin", password: str = "admin") -> None:
        r = self.client.post("/login", data={"username": username, "password": password})
        if r.status_code != 303:
            raise RuntimeError(f"login as {username} failed: HTTP {r.status_code}")

    # -- requests -----------------------------------------------------------
    def get(self, path: str, follow: bool = False) -> httpx.Response:
        return self.client.get(path, follow_redirects=follow)

    def post(self, path: str, data=None, follow: bool = False) -> httpx.Response:
        return self.client.post(path, data=data or {}, follow_redirects=follow)

    def page(self, path: str) -> httpx.Response:
        """GET following redirects, ending on the rendered page."""
        return self.client.get(path, follow_redirects=True)

    def save(self, name: str, resp: httpx.Response) -> str:
        """Persist a response body under .qa/evidence and return its path."""
        ext = "html"
        ctype = resp.headers.get("content-type", "")
        if "pdf" in ctype:
            ext = "pdf"
        elif "json" in ctype:
            ext = "json"
        elif "text/plain" in ctype:
            ext = "txt"
        path = EVID / f"{name}.{ext}"
        if ext == "pdf":
            path.write_bytes(resp.content)
        else:
            path.write_text(resp.text, encoding="utf-8")
        return str(path.relative_to(ROOT.parent))

    # -- interrogation ------------------------------------------------------
    def forms(self, path: str) -> list[dict]:
        return parse(self.page(path).text).forms

    def links(self, path: str) -> list[str]:
        return parse(self.page(path).text).links

    def flash(self, html: str) -> str:
        m = re.search(r'<div class="flash flash-\w+">(.*?)</div>', html, re.S)
        return m.group(1).strip() if m else ""

    def db(self, sql: str) -> str:
        out = subprocess.run(
            ["docker", "exec", DB_CONTAINER, *DB_CMD, sql],
            capture_output=True, text=True,
        )
        return (out.stdout + out.stderr).strip()

    # -- reporting ----------------------------------------------------------
    def finding(self, fid: str, title: str, *, severity: str, area: str,
                action: str, steps: list[str], expected: str, actual: str,
                evidence: str = "", cause: str = "", status: str = "confirmed") -> None:
        bullets = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
        block = (
            f"\n## {fid}: {title}\n"
            f"- **Severity:** {severity}\n"
            f"- **Area:** {area}\n"
            f"- **Status:** {status}\n"
            f"- **Action:** `{action}`\n"
            f"- **Steps:**\n{bullets}\n"
            f"- **Expected:** {expected}\n"
            f"- **Actual:** {actual}\n"
            f"- **Evidence:** {evidence or '(see notes)'}\n"
            f"- **Suspected cause:** {cause or 'not yet located'}\n"
        )
        with self.findings_file.open("a", encoding="utf-8") as fh:
            fh.write(block)
        print(block)

    def header(self, area: str) -> None:
        if not self.findings_file.exists():
            self.findings_file.write_text(
                f"# QA findings — {area}\n\nGenerated against {self.base}\n",
                encoding="utf-8",
            )


def main() -> int:
    ap = argparse.ArgumentParser(description="PMSyS live QA helper")
    ap.add_argument("cmd", choices=["login", "get", "post", "forms", "links", "db", "status"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("kv", nargs="*", help="key=value pairs for post")
    ns = ap.parse_args()

    if ns.cmd == "db":
        print(subprocess.run(["docker", "exec", DB_CONTAINER, *DB_CMD, ns.arg],
                             capture_output=True, text=True).stdout)
        return 0

    if ns.cmd == "status":
        r = httpx.get(BASE + (ns.arg or "/"), follow_redirects=False)
        print(f"{r.status_code} {r.headers.get('location', '')}")
        return 0

    q = QA(prefix="cli")
    if ns.cmd == "login":
        print("logged in OK")
    elif ns.cmd == "get":
        r = q.get(ns.arg)
        print(f"HTTP {r.status_code} {r.headers.get('location', '')} ({len(r.text)} bytes)")
    elif ns.cmd == "post":
        data = dict(kv.split("=", 1) for kv in ns.kv)
        r = q.post(ns.arg, data=data)
        print(f"HTTP {r.status_code} -> {r.headers.get('location', '')}")
    elif ns.cmd == "forms":
        for f in q.forms(ns.arg):
            print(f"{f['method'].upper()} {f['action']}")
            for fld in f["fields"]:
                if fld["name"]:
                    print(f"   field {fld['name']} type={fld['type']} required={fld['required']}")
            for b in f["buttons"]:
                print(f"   button type={b['type']} formaction={b['formaction']} text={b['text']!r}")
    elif ns.cmd == "links":
        for href in sorted(set(q.links(ns.arg))):
            print(href)
    return 0


if __name__ == "__main__":
    sys.exit(main())
