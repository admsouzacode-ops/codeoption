"""API FastAPI + frontend estatico."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.bot_runner import bot_runner
from api.state import state

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="CodeOption", version="1.0.0")


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


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
