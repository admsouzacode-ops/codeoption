"""Estado compartilhado entre o bot e a API web."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


class AppState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.bot_running = False
        self.connected = False
        self.account = "PRACTICE"
        self.balance = 0.0
        self.currency = "R$"
        self.user_name = ""
        self.strategy = "escadinha"
        self.asset = "EURUSD-OTC"
        self.timeframe = 60
        self.lucro_dia = 0.0
        self.wins = 0
        self.losses = 0
        self.last_signal: Optional[Dict[str, Any]] = None
        self.last_message = "Aguardando inicio"
        self.trades: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
        self.started_at: Optional[str] = None

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            total = self.wins + self.losses
            win_rate = round((self.wins / total) * 100, 1) if total else 0.0
            return {
                "bot_running": self.bot_running,
                "connected": self.connected,
                "account": self.account,
                "balance": self.balance,
                "currency": self.currency,
                "user_name": self.user_name,
                "strategy": self.strategy,
                "asset": self.asset,
                "timeframe": self.timeframe,
                "lucro_dia": round(self.lucro_dia, 2),
                "wins": self.wins,
                "losses": self.losses,
                "win_rate": win_rate,
                "last_signal": self.last_signal,
                "last_message": self.last_message,
                "error": self.error,
                "started_at": self.started_at,
                "trades": list(self.trades[:50]),
            }

    def add_trade(self, trade: Dict[str, Any]) -> None:
        with self.lock:
            trade["id"] = len(self.trades) + 1
            trade["time"] = trade.get("time") or datetime.now().strftime("%H:%M:%S")
            self.trades.insert(0, trade)
            self.trades = self.trades[:100]
            resultado = float(trade.get("resultado", 0) or 0)
            self.lucro_dia += resultado
            if resultado > 0:
                self.wins += 1
            elif resultado < 0:
                self.losses += 1


state = AppState()
