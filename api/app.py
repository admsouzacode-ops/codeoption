"""API FastAPI + frontend estatico com autenticacao."""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from api.bot_runner import bot_runner
from api.state import state

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))

app = FastAPI(title="CodeOption", version="1.1.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="codeoption_session",
    max_age=60 * 60 * 12,  # 12 horas
    same_site="lax",
    https_only=False,
)

PUBLIC_PATHS = {
    "/health",
    "/login",
    "/api/login",
}


def _auth_enabled() -> bool:
    return bool(ADMIN_PASSWORD)


def _is_logged_in(request: Request) -> bool:
    if not _auth_enabled():
        return True  # sem senha configurada: modo aberto (nao recomendado)
    return bool(request.session.get("user"))


def _require_login(request: Request) -> None:
    if not _is_logged_in(request):
        raise HTTPException(status_code=401, detail="Nao autenticado")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # liberados
    if path in PUBLIC_PATHS or path.startswith("/static"):
        return await call_next(request)

    # se auth ativo e nao logado
    if _auth_enabled() and not request.session.get("user"):
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Nao autenticado"}, status_code=401)
        return RedirectResponse("/login", status_code=302)

    return await call_next(request)


@app.get("/health")
def health():
    return {"ok": True, "status": "up", "auth_required": _auth_enabled()}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _is_logged_in(request):
        return RedirectResponse("/", status_code=302)
    login_path = WEB_DIR / "login.html"
    if login_path.exists():
        return FileResponse(login_path)
    return HTMLResponse("<h1>Login</h1><p>login.html nao encontrado</p>", status_code=500)


@app.post("/api/login")
async def api_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if not _auth_enabled():
        request.session["user"] = username or "admin"
        return {"ok": True, "message": "Auth desabilitado (defina ADMIN_PASSWORD)"}

    user_ok = hmac.compare_digest(username.strip(), ADMIN_USER)
    pass_ok = hmac.compare_digest(password, ADMIN_PASSWORD)

    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos")

    request.session["user"] = ADMIN_USER
    return {"ok": True, "message": "Login ok"}


@app.post("/api/logout")
async def api_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def api_me(request: Request):
    _require_login(request)
    return {"user": request.session.get("user"), "auth_required": _auth_enabled()}


@app.get("/api/status")
def api_status(request: Request):
    _require_login(request)
    snap = state.snapshot()
    snap["bot_running"] = bot_runner.is_running or snap["bot_running"]
    return snap


@app.post("/api/bot/start")
def api_bot_start(request: Request):
    _require_login(request)
    return bot_runner.start()


@app.post("/api/bot/stop")
def api_bot_stop(request: Request):
    _require_login(request)
    return bot_runner.stop()


@app.get("/api/trades")
def api_trades(request: Request):
    _require_login(request)
    return {"trades": state.snapshot()["trades"]}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse(
            "<h1>CodeOption</h1><p>Frontend nao encontrado (web/index.html).</p>",
            status_code=500,
        )
    return FileResponse(index_path)


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
