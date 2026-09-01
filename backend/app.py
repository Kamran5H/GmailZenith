"""
Gmail Zenith Pro - FastAPI Backend Server
High-performance REST API supporting real-time inbox analytics, batch cleanups,
smart query filtering, and GitHub notification triage.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional
import webbrowser

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Ensure backend folder is on path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from gmail_engine import CREDENTIALS_PATH, TOKEN_PATH, engine

app = FastAPI(
    title="Gmail Zenith Pro",
    description="4K HD AI-Powered Inbox Optimizer & Triage Suite for Kamran Ashraf",
    version="1.0.0",
)

# This server controls destructive Gmail operations (trash/permanent-delete). It is
# bound to localhost, so restrict CORS to local origins — a wide-open "*" would let
# any website you visit issue delete commands to this API from your browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request Models ---
class SimulateCleanRequest(BaseModel):
    query: str
    max_scan: int = 50


class PresetCleanRequest(BaseModel):
    preset: str
    max_items: int = 100


class BatchTrashRequest(BaseModel):
    message_ids: List[str]


class BatchLabelsRequest(BaseModel):
    message_ids: List[str]
    add_labels: Optional[List[str]] = None
    remove_labels: Optional[List[str]] = None


class CredentialsUploadJson(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    raw_json: Optional[Dict[str, Any]] = None


# --- API Routes ---

@app.get("/api/health")
def api_health():
    return {"status": "ok", "app": "Gmail Zenith Pro", "version": "1.0.0"}


@app.get("/api/auth/status")
def get_auth_status():
    has_credentials = CREDENTIALS_PATH.exists()
    has_token = TOKEN_PATH.exists()
    is_auth = engine.is_authenticated()
    profile = engine.get_profile() if is_auth else None

    return {
        "authenticated": is_auth,
        "hasCredentials": has_credentials,
        "hasToken": has_token,
        "profile": profile,
    }


@app.post("/api/auth/upload-credentials")
async def upload_credentials(file: UploadFile = File(...)):
    try:
        content = await file.read()
        saved = engine.save_credentials_file(content)
        if saved:
            return {"success": True, "message": "credentials.json saved successfully."}
        else:
            raise HTTPException(status_code=400, detail="Invalid JSON file format.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/save-credentials-json")
def save_credentials_json(payload: Dict[str, Any]):
    saved = engine.save_credentials_file(payload)
    if saved:
        return {"success": True, "message": "credentials.json saved successfully."}
    raise HTTPException(status_code=400, detail="Failed to parse credentials JSON.")


@app.get("/api/auth/url")
def get_auth_url(redirect_uri: str = "http://127.0.0.1:8765/oauth2callback"):
    try:
        url = engine.get_authorization_url(redirect_uri=redirect_uri)
        return {"success": True, "auth_url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/oauth2callback", response_class=HTMLResponse)
def oauth2callback(code: Optional[str] = None, error: Optional[str] = None):
    if error:
        return f"""
        <!DOCTYPE html>
        <html><head><title>Auth Error</title>
        <style>body{{font-family:sans-serif;background:#0f1220;color:#f87171;text-align:center;padding:50px;}}</style>
        </head><body>
        <h2>Authentication Failed</h2><p>{error}</p>
        <p><a href="/" style="color:#60a5fa;">Return to Gmail Zenith Pro</a></p>
        </body></html>
        """
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    res = engine.exchange_code_for_token(code=code, redirect_uri="http://127.0.0.1:8765/oauth2callback")
    if res.get("success"):
        email_addr = res.get("profile", {}).get("email", "Your Account")
        return f"""
        <!DOCTYPE html>
        <html><head><title>Connected — Gmail Zenith Pro</title>
        <meta charset="utf-8">
        <style>
          body {{ font-family: -apple-system, system-ui, sans-serif; background: #070913; color: #f8fafc; text-align: center; padding: 60px 20px; }}
          .card {{ background: rgba(18,24,44,0.85); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; max-width: 480px; margin: 0 auto; padding: 36px 24px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }}
          .badge {{ display: inline-block; width: 60px; height: 60px; line-height: 60px; border-radius: 50%; background: rgba(16,185,129,0.15); color: #34d399; font-size: 32px; margin-bottom: 16px; }}
          h2 {{ margin: 0 0 8px; color: #f8fafc; font-size: 24px; }}
          p {{ color: #94a3b8; font-size: 15px; line-height: 1.5; }}
          .btn {{ display: inline-block; margin-top: 20px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: #fff; text-decoration: none; padding: 12px 24px; border-radius: 10px; font-weight: bold; }}
        </style>
        <script>
          if (window.opener) {{
            try {{ window.opener.postMessage('oauth_complete', '*'); }} catch(e) {{}}
            setTimeout(() => window.close(), 1500);
          }} else {{
            setTimeout(() => window.location.href = '/', 2000);
          }}
        </script>
        </head><body>
        <div class="card">
          <div class="badge">&#10004;</div>
          <h2>Connected Successfully!</h2>
          <p>Gmail Zenith Pro is now connected to <b>{email_addr}</b>.</p>
          <p style="font-size:13px; color:#64748b;">This window will close automatically...</p>
          <a class="btn" href="/">Return to Dashboard</a>
        </div>
        </body></html>
        """
    else:
        return f"""
        <!DOCTYPE html>
        <html><head><title>Auth Error</title>
        <style>body{{font-family:sans-serif;background:#0f1220;color:#f87171;text-align:center;padding:50px;}}</style>
        </head><body>
        <h2>Authentication Failed</h2><p>{res.get('error')}</p>
        <p><a href="/" style="color:#60a5fa;">Return to Gmail Zenith Pro</a></p>
        </body></html>
        """


@app.post("/api/auth/exchange-code")
def exchange_code(payload: Dict[str, str]):
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Code is required.")
    res = engine.exchange_code_for_token(code=code, redirect_uri=payload.get("redirect_uri", "http://127.0.0.1:8765/oauth2callback"))
    return res


@app.post("/api/auth/interactive-login")
def interactive_login():
    res = engine.authenticate_interactive()
    return res


@app.post("/api/auth/logout")
def logout():
    success = engine.logout()
    return {"success": success}


@app.get("/api/stats/inbox")
def get_inbox_stats():
    if not engine.is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail is not authenticated.")
    return engine.get_inbox_stats()


@app.get("/api/stats/top-senders")
def get_top_senders(limit: int = Query(100, ge=10, le=200)):
    if not engine.is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail is not authenticated.")
    return {"senders": engine.get_top_clutter_senders(scan_limit=limit)}


@app.get("/api/search")
def search_emails(
    q: str = Query(..., description="Gmail search query"),
    max_results: int = Query(50, ge=1, le=200),
    page_token: Optional[str] = Query(None),
    include_spam_trash: bool = Query(False),
):
    if not engine.is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail is not authenticated.")
    return engine.search_messages(
        query=q,
        max_results=max_results,
        page_token=page_token,
        include_spam_trash=include_spam_trash,
    )


@app.get("/api/github/triage")
def get_github_triage(max_results: int = Query(50, ge=1, le=100)):
    if not engine.is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail is not authenticated.")
    return engine.get_github_triage(max_results=max_results)


@app.post("/api/clean/simulate")
def simulate_clean(req: SimulateCleanRequest):
    if not engine.is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail is not authenticated.")
    return engine.simulate_clean(query=req.query, max_scan=req.max_scan)


@app.post("/api/clean/preset")
def clean_by_preset(req: PresetCleanRequest):
    if not engine.is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail is not authenticated.")
    return engine.clean_by_preset(preset_name=req.preset, max_items=req.max_items)


@app.post("/api/batch/trash")
def batch_trash(req: BatchTrashRequest):
    if not engine.is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail is not authenticated.")
    return engine.batch_trash_messages(req.message_ids)


@app.post("/api/batch/untrash")
def batch_untrash(req: BatchTrashRequest):
    if not engine.is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail is not authenticated.")
    return engine.batch_untrash_messages(req.message_ids)


@app.post("/api/batch/delete")
def batch_delete(req: BatchTrashRequest):
    if not engine.is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail is not authenticated.")
    return engine.batch_delete_messages(req.message_ids)


@app.post("/api/batch/labels")
def batch_modify_labels(req: BatchLabelsRequest):
    if not engine.is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail is not authenticated.")
    return engine.batch_modify_labels(
        message_ids=req.message_ids,
        add_labels=req.add_labels,
        remove_labels=req.remove_labels,
    )


@app.get("/api/sync/config")
def get_sync_config():
    config_file = BASE_DIR / "auto_sync_config.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "enabled": True,
        "interval_minutes": 15,
        "purge_promotions": True,
        "purge_social": True,
        "purge_spam": True,
        # Example rules — edit these in the app to match your own inbox.
        "custom_rules": [
            {"name": "Newsletters & Digests", "query": "(newsletter OR digest) in:inbox", "enabled": True},
            {"name": "Social Notifications", "query": "category:social in:inbox", "enabled": True},
            {"name": "Promotions", "query": "category:promotions in:inbox", "enabled": True},
            {"name": "Receipts & Bookings", "query": "(receipt OR booking OR ticket) in:inbox", "enabled": False},
        ]
    }


@app.post("/api/sync/config")
def update_sync_config(cfg: Dict[str, Any]):
    config_file = BASE_DIR / "auto_sync_config.json"
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return {"success": True, "config": cfg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sync/history")
def get_sync_history():
    log_file = BASE_DIR / "auto_sync_log.json"
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


@app.post("/api/sync/run-now")
def trigger_sync_now(background_tasks: BackgroundTasks):
    try:
        import subprocess
        subprocess.Popen([sys.executable, str(BASE_DIR / "auto_process_inbox.py")], cwd=str(BASE_DIR))
        return {"success": True, "message": "Automated sync cycle triggered in background"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Static Frontend Mounting ---
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index_page():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Gmail Zenith Pro: Frontend is building...</h1>"


def open_in_browser(url: str):
    """Launches Google Chrome or Microsoft Edge or default browser in app mode."""
    import subprocess
    browser_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for exe in browser_candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, f"--app={url}"])
                return
            except Exception:
                try:
                    subprocess.Popen([exe, url])
                    return
                except Exception:
                    pass
    # Fallback to webbrowser module
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


def is_port_in_use(port: int = 8765, host: str = "127.0.0.1") -> bool:
    """Checks if server is already running."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def start_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    """Starts the uvicorn server or opens browser if already running."""
    url = f"http://{host}:{port}"
    if is_port_in_use(port=port, host=host):
        print(f"[INFO] Server is already running on {url}. Opening browser...")
        open_in_browser(url)
        sys.exit(0)

    if open_browser:
        def _open():
            time.sleep(0.8)
            open_in_browser(url)
        import threading
        threading.Thread(target=_open, daemon=True).start()

    print(f"=======================================================")
    print(f"[START] GMAIL ZENITH PRO - AI INBOX OPTIMIZER & TRIAGE")
    print(f"[HTTP]  Web UI running at: {url}")
    print(f"=======================================================\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server(open_browser=True)
