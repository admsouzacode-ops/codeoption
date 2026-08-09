"""API FastAPI + frontend estatico."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.bot_runner import bot_runner
from api.state import state

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="CodeOption", version="1.0.0")


@app.get("/health")
def health():
    return {"ok": True, "status": "up"}


@app.get("/api/status")
def api_status():
    snap = state.snapshot()
    snap["bot_running"] = bot_runner.is_running or snap["bot_running"]
    return snap


@app.post("/api/bot/start")
def api_bot_start():
    return bot_runner.start()


@app.post("/api/bot/stop")
def api_bot_stop():
    return bot_runner.stop()


@app.get("/api/trades")
def api_trades():
    return {"trades": state.snapshot()["trades"]}


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse(
            "<h1>CodeOption</h1><p>Frontend nao encontrado (web/index.html).</p>",
            status_code=500,
        )
    return FileResponse(index_path)


# /static/css/... e /static/js/...
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
