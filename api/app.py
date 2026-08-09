"""API FastAPI + frontend com login simples e seguro."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path
from typing import List, Optional

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

FALLBACK_ASSETS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC",
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC", "USDCHF-OTC",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD",
]

app = FastAPI(title="CodeOption", version="1.3.0")


class LoginBody(BaseModel):
    username: str
    password: str


class SettingsBody(BaseModel):
    asset: Optional[str] = None
    stop_win: Optional[float] = Field(None, gt=0)
    stop_loss: Optional[float] = Field(None, gt=0)
    valor_entrada: Optional[float] = Field(None, gt=0)
    expiracao: Optional[int] = Field(None, ge=1)
    timeframe: Optional[int] = Field(None, ge=60)
    min_velas: Optional[int] = Field(None, ge=2)
    ema_rapida: Optional[int] = Field(None, ge=2)
    ema_lenta: Optional[int] = Field(None, ge=3)
    usar_filtro_ema: Optional[bool] = None
    micro_mult: Optional[int] = Field(None, ge=2)
    macro_mult: Optional[int] = Field(None, ge=3)
    exigir_confluencia: Optional[bool] = None
    usar_martingale: Optional[bool] = None
    niveis_martingale: Optional[int] = Field(None, ge=0)
    fator_martingale: Optional[float] = Field(None, gt=1)
    usar_soros: Optional[bool] = None
    niveis_soros: Optional[int] = Field(None, ge=0)


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

    data = body.model_dump(exclude_none=True)
    with state.lock:
        for key, value in data.items():
            if key == "asset" and value:
                state.asset = str(value).upper().strip()
            elif hasattr(state, key):
                setattr(state, key, value)

        if body.stop_win is not None:
            state.stop_win = float(body.stop_win)
        if body.stop_loss is not None:
            state.stop_loss = float(body.stop_loss)

    if body.stop_win is not None and body.stop_loss is not None:
        bot_runner.update_stops(body.stop_win, body.stop_loss)
    elif body.stop_win is not None or body.stop_loss is not None:
        bot_runner.update_stops(state.stop_win, state.stop_loss)

    return {"ok": True, "message": "Configuracoes salvas", "settings": state.snapshot()}


def _parse_open_assets(open_time: dict) -> List[str]:
    names = set()
    for market in ("turbo", "binary", "digital"):
        bucket = open_time.get(market) or {}
        for name, info in bucket.items():
            if isinstance(info, dict) and info.get("open"):
                names.add(str(name).upper())
    return sorted(names)


@app.get("/api/assets")
def api_assets():
    """Lista ativos abertos (API) ou fallback estatico."""
    from api.bot_runner import bot_runner

    # 1) se bot conectado, usa a mesma sessao
    api = getattr(bot_runner, "_api", None)
    if api is not None:
        try:
            open_time = api.get_all_open_time()
            assets = _parse_open_assets(open_time)
            if assets:
                return {"ok": True, "source": "live", "assets": assets}
        except Exception as exc:
            return {"ok": True, "source": "fallback", "assets": FALLBACK_ASSETS, "warning": str(exc)}

    # 2) tenta conexao temporaria
    try:
        from core.settings import load_settings
        from iqoptionapi.stable_api import IQ_Option

        cfg = load_settings()
        tmp = IQ_Option(cfg["email"], cfg["senha"])
        check, reason = tmp.connect()
        if not check:
            return {
                "ok": True,
                "source": "fallback",
                "assets": FALLBACK_ASSETS,
                "warning": f"Nao conectou: {reason}",
            }
        tmp.change_balance(cfg["tipo_conta"])
        open_time = tmp.get_all_open_time()
        assets = _parse_open_assets(open_time)
        return {
            "ok": True,
            "source": "live",
            "assets": assets or FALLBACK_ASSETS,
        }
    except Exception as exc:
        return {
            "ok": True,
            "source": "fallback",
            "assets": FALLBACK_ASSETS,
            "warning": str(exc),
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
