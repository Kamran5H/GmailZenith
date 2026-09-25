"""
Gmail Zenith - FastAPI server.

Serves the dashboard and a small local REST API over the Gmail engine.
Run with:  python backend/app.py   (opens http://127.0.0.1:8767)
"""

from __future__ import annotations

import html
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import webbrowser

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field
import uvicorn

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
if str(BASE_DIR / "backend") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "backend"))

import auto_sync  # noqa: E402
from gmail_engine import (  # noqa: E402
    CREDENTIALS_PATH, PRESETS, TOKEN_PATH, USER_ACTIONS, NotAuthenticated, engine,
)

VERSION = "2.0.0"
HOST = os.environ.get("ZENITH_HOST", "127.0.0.1")
PORT = int(os.environ.get("ZENITH_PORT", "8767"))

app = FastAPI(title="Gmail Zenith", description="Local Gmail inbox cleanup API", version=VERSION)


# --------------------------------------------------------------- security
@app.middleware("http")
async def same_origin_only(request: Request, call_next):
    """This API can trash mail, so reject state-changing requests from other websites.
    Browsers always send Origin on cross-site POSTs; local tools (curl, scripts) send none."""
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Cross-origin request blocked."}, status_code=403)
    return await call_next(request)


@app.exception_handler(NotAuthenticated)
async def _not_auth(_: Request, exc: NotAuthenticated):
    return JSONResponse({"detail": str(exc)}, status_code=401)


@app.exception_handler(RefreshError)
async def _refresh_failed(_: Request, exc: RefreshError):
    engine.load_credentials()
    return JSONResponse({"detail": "Google rejected the saved sign-in. Please reconnect on the Setup tab."},
                        status_code=401)


@app.exception_handler(HttpError)
async def _gmail_error(_: Request, exc: HttpError):
    reason = exc._get_reason() if hasattr(exc, "_get_reason") else str(exc)
    return JSONResponse({"detail": f"Gmail API error: {reason}"}, status_code=502)


@app.exception_handler(ValueError)
async def _bad_value(_: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


# ----------------------------------------------------------------- models
class IdsRequest(BaseModel):
    message_ids: List[str] = Field(..., max_length=5000)
    action: str


class UndoOp(BaseModel):
    action: str
    ids: List[str] = Field(..., max_length=5000)


class UndoRequest(BaseModel):
    ops: List[UndoOp] = Field(..., max_length=10)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    action: str = "trash"
    limit: int = Field(5000, ge=1, le=5000)
    protect_starred: bool = True


class PreviewRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    protect_starred: bool = True


class UnsubscribeRequest(BaseModel):
    message_id: str


def _redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/oauth2callback"


# ------------------------------------------------------------------- auth
@app.get("/api/health")
def api_health():
    return {"status": "ok", "app": "Gmail Zenith", "version": VERSION}


@app.get("/api/auth/status")
def get_auth_status(request: Request):
    authenticated = engine.is_authenticated()
    profile = None
    if authenticated:
        try:
            profile = engine.get_profile()
        except Exception:
            authenticated = False
    return {
        "authenticated": authenticated,
        "hasCredentials": CREDENTIALS_PATH.exists(),
        "hasToken": TOKEN_PATH.exists(),
        "clientType": engine.client_type(),
        "redirectUri": _redirect_uri(request),
        "profile": profile,
    }


@app.post("/api/auth/upload-credentials")
async def upload_credentials(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > 100_000:
        raise HTTPException(400, "File is too large to be an OAuth client JSON.")
    try:
        engine.save_credentials_file(content)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(400, "Could not read the file. Make sure it is the JSON you downloaded from Google.")
    return {"success": True, "message": "credentials.json saved."}


@app.post("/api/auth/save-credentials-json")
def save_credentials_json(payload: Dict[str, Any]):
    engine.save_credentials_file(payload)
    return {"success": True, "message": "credentials.json saved."}


@app.get("/api/auth/url")
def get_auth_url(request: Request):
    try:
        return {"success": True, "auth_url": engine.get_authorization_url(_redirect_uri(request))}
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))


def _result_page(ok: bool, title: str, message: str) -> str:
    color = "#34d399" if ok else "#f87171"
    icon = "&#10004;" if ok else "&#10006;"
    script = """
      if (window.opener) { try { window.opener.postMessage('oauth_complete', window.location.origin); } catch (e) {}
        setTimeout(() => window.close(), 1200); }
      else { setTimeout(() => window.location.href = '/', 1800); }""" if ok else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html.escape(title)} — Gmail Zenith</title>
<style>body{{font-family:system-ui,-apple-system,sans-serif;background:#070913;color:#f8fafc;display:grid;place-items:center;min-height:100vh;margin:0;padding:20px}}
.card{{background:#12182c;border:1px solid rgba(255,255,255,.1);border-radius:16px;max-width:460px;padding:36px 28px;text-align:center}}
.i{{font-size:30px;color:{color};margin-bottom:10px}}p{{color:#94a3b8;line-height:1.5}}a{{color:#60a5fa}}</style>
<script>{script}</script></head><body><div class="card"><div class="i">{icon}</div><h2>{html.escape(title)}</h2>
<p>{html.escape(message)}</p><p><a href="/">Back to Gmail Zenith</a></p></div></body></html>"""


@app.get("/oauth2callback", response_class=HTMLResponse)
def oauth2callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error:
        return HTMLResponse(_result_page(False, "Sign-in cancelled", f"Google returned: {error}"), status_code=400)
    if not code or not state:
        return HTMLResponse(_result_page(False, "Sign-in failed", "Missing authorization code."), status_code=400)
    try:
        profile = engine.exchange_code_for_token(code=code, state=state)
    except Exception as e:
        return HTMLResponse(_result_page(False, "Sign-in failed", str(e)), status_code=400)
    return _result_page(True, "Connected", f"Gmail Zenith is connected to {profile.get('email', 'your account')}.")


@app.post("/api/auth/logout")
def logout():
    engine.logout()
    return {"success": True}


# ------------------------------------------------------------------ stats
@app.get("/api/stats/inbox")
def get_inbox_stats():
    return engine.get_inbox_stats()


@app.get("/api/stats/top-senders")
def get_top_senders(limit: int = Query(300, ge=50, le=1000)):
    return engine.get_top_senders(scan_limit=limit)


@app.get("/api/presets")
def get_presets(counts: bool = False):
    data = {k: dict(v, key=k) for k, v in PRESETS.items()}
    if counts:
        for k, c in engine.preset_counts().items():
            data[k].update(c)
    return {"presets": list(data.values())}


# ----------------------------------------------------------------- search
@app.get("/api/search")
def search_emails(
    q: str = Query(..., min_length=1, max_length=2000),
    max_results: int = Query(50, ge=1, le=200),
    page_token: Optional[str] = None,
):
    return engine.search_messages(query=q, max_results=max_results, page_token=page_token)


@app.get("/api/github/triage")
def get_github_triage(max_results: int = Query(100, ge=1, le=200)):
    return engine.get_github_triage(max_results=max_results)


# ---------------------------------------------------------------- actions
@app.post("/api/actions/preview")
def preview(req: PreviewRequest):
    return engine.preview(req.query, protect_starred=req.protect_starred)


@app.post("/api/actions/query")
def action_on_query(req: QueryRequest):
    return engine.apply_action_to_query(req.query, req.action, limit=req.limit, protect_starred=req.protect_starred)


@app.post("/api/actions/ids")
def action_on_ids(req: IdsRequest):
    return engine.apply_action(req.message_ids, req.action)


@app.post("/api/actions/undo")
def undo(req: UndoRequest):
    return engine.run_ops([op.model_dump() for op in req.ops])


@app.get("/api/actions")
def list_actions():
    return {"actions": list(USER_ACTIONS)}


@app.post("/api/unsubscribe")
def unsubscribe(req: UnsubscribeRequest):
    return engine.unsubscribe(req.message_id)


# -------------------------------------------------------------- auto-clean
@app.get("/api/sync/config")
def get_sync_config():
    return auto_sync.load_config()


@app.post("/api/sync/config")
def update_sync_config(cfg: Dict[str, Any]):
    return {"success": True, "config": auto_sync.save_config(cfg)}


@app.get("/api/sync/history")
def get_sync_history():
    return list(reversed(auto_sync.load_history()))


@app.get("/api/sync/status")
def get_sync_status():
    return auto_sync.status()


@app.post("/api/sync/run-now")
def trigger_sync_now():
    if not engine.is_authenticated():
        raise NotAuthenticated("Gmail is not connected.")
    if auto_sync.status()["running"]:
        raise HTTPException(409, "An auto-clean run is already in progress.")

    def _run():
        try:
            auto_sync.run_rules(engine)
        except Exception as e:
            print(f"[AutoSync] Run failed: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return {"success": True, "message": "Auto-clean started."}


# --------------------------------------------------------------- frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index_page():
    return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(BASE_DIR / "gmail_zenith.ico")


# ---------------------------------------------------------------- launcher
def open_in_browser(url: str) -> None:
    """Opens the dashboard as a chromeless app window when Chrome/Edge is available."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for exe in candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, f"--app={url}"])
                return
            except OSError:
                pass
    webbrowser.open(url)


def is_port_in_use(port: int = PORT, host: str = HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def start_server(host: str = HOST, port: int = PORT, open_browser: bool = True) -> None:
    url = f"http://{host}:{port}"
    if is_port_in_use(port=port, host=host):
        print(f"[INFO] Gmail Zenith is already running at {url}")
        if open_browser:
            open_in_browser(url)
        return

    if open_browser:
        threading.Thread(target=lambda: (time.sleep(1.0), open_in_browser(url)), daemon=True).start()

    print("=" * 50)
    print(f"  Gmail Zenith {VERSION}  ->  {url}")
    print("=" * 50)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    start_server(open_browser="--no-browser" not in sys.argv)
