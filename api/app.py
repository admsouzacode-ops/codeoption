"""API FastAPI + frontend com login simples e seguro."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

ADMIN_USER = os.getenv("ADMIN_USER", "admin").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
SESSION_SECRET = (os.getenv("SESSION_SECRET") or secrets.token_hex(32)).strip()
COOKIE_NAME = "codeoption_auth"
COOKIE_MAX_AGE = 60 * 60 * 12

app = FastAPI(title="CodeOption", version="1.2.0")


class LoginBody(BaseModel):
    username: str
    password: str


class SettingsBody(BaseModel):
    stop_win: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)


def _auth_enabled() -> bool:
    return bool(ADMIN_PASSWORD)


def _sign(value: str) -> str:
    sig = hmac.new(SESSION_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{sig}"


def _verify(token: Optional[str]) -> bool:
    if not token or "." not in token:
        return False
    value, sig = token.rsplit(".", 1)
    expected = hmac.new(SESSION_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        user, exp_s = value.split(":", 1)
        if int(exp_s) < int(time.time()):
            return False
        return user == ADMIN_USER
    except Exception:
        return False


def _is_logged_in(request: Request) -> bool:
    if not _auth_enabled():
        return True
    return _verify(request.cookies.get(COOKIE_NAME))


def _set_login_cookie(response: Response, username: str) -> None:
    exp = int(time.time()) + COOKIE_MAX_AGE
    token = _sign(f"{username}:{exp}")
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in {"/health", "/login", "/api/login"} or path.startswith("/static"):
        return await call_next(request)
    if _auth_enabled() and not _is_logged_in(request):
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
    path = WEB_DIR / "login.html"
    if path.exists():
        return FileResponse(path)
    return HTMLResponse("<h1>Login</h1>", status_code=500)


@app.post("/api/login")
async def api_login(body: LoginBody):
    if not _auth_enabled():
        resp = JSONResponse({"ok": True, "message": "Auth desabilitado"})
        _set_login_cookie(resp, body.username or "admin")
        return resp

    user_ok = hmac.compare_digest(body.username.strip(), ADMIN_USER)
    pass_ok = hmac.compare_digest(body.password, ADMIN_PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos")

    resp = JSONResponse({"ok": True, "message": "Login ok"})
    _set_login_cookie(resp, ADMIN_USER)
    return resp


@app.post("/api/logout")
async def api_logout():
    resp = JSONResponse({"ok": True})
    _clear_cookie(resp)
    return resp


@app.get("/api/status")
def api_status(request: Request):
    from api.bot_runner import bot_runner
    from api.state import state

    snap = state.snapshot()
    snap["bot_running"] = bot_runner.is_running or snap["bot_running"]
    return snap


@app.post("/api/settings")
def api_settings(body: SettingsBody):
    from api.bot_runner import bot_runner
    from api.state import state

    with state.lock:
        state.stop_win = float(body.stop_win)
        state.stop_loss = float(body.stop_loss)

    # se o bot estiver rodando, atualiza o risk manager em tempo real
    bot_runner.update_stops(body.stop_win, body.stop_loss)

    return {
        "ok": True,
        "stop_win": body.stop_win,
        "stop_loss": body.stop_loss,
        "message": "Stops atualizados",
    }


@app.post("/api/bot/start")
def api_bot_start(request: Request):
    from api.bot_runner import bot_runner

    return bot_runner.start()


@app.post("/api/bot/stop")
def api_bot_stop(request: Request):
    from api.bot_runner import bot_runner

    return bot_runner.stop()


@app.get("/api/trades")
def api_trades(request: Request):
    from api.state import state

    return {"trades": state.snapshot()["trades"]}


@app.get("/")
def index(request: Request):
    path = WEB_DIR / "index.html"
    if not path.exists():
        return HTMLResponse("<h1>CodeOption</h1><p>Frontend nao encontrado.</p>", status_code=500)
    return FileResponse(path)


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
