"""Estado compartilhado entre o bot e a API web."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")


def now_br() -> datetime:
    return datetime.now(TZ)


def time_br() -> str:
    return now_br().strftime("%H:%M:%S")


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
        self.valor_entrada = 2.0
        self.expiracao = 1
        self.min_velas = 3
        self.ema_rapida = 9
        self.ema_lenta = 21
        self.usar_filtro_ema = True
        self.micro_mult = 5
        self.macro_mult = 15
        self.exigir_confluencia = True
        self.usar_martingale = True
        self.niveis_martingale = 2
        self.fator_martingale = 2.0
        self.usar_soros = True
        self.niveis_soros = 2
        self.stop_win = 50.0
        self.stop_loss = 30.0
        self.lucro_dia = 0.0
        self.wins = 0
        self.losses = 0
        self.last_signal: Optional[Dict[str, Any]] = None
        self.confluence: Optional[Dict[str, Any]] = None
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
                "valor_entrada": self.valor_entrada,
                "expiracao": self.expiracao,
                "min_velas": self.min_velas,
                "ema_rapida": self.ema_rapida,
                "ema_lenta": self.ema_lenta,
                "usar_filtro_ema": self.usar_filtro_ema,
                "micro_mult": self.micro_mult,
                "macro_mult": self.macro_mult,
                "exigir_confluencia": self.exigir_confluencia,
                "usar_martingale": self.usar_martingale,
                "niveis_martingale": self.niveis_martingale,
                "fator_martingale": self.fator_martingale,
                "usar_soros": self.usar_soros,
                "niveis_soros": self.niveis_soros,
                "stop_win": self.stop_win,
                "stop_loss": self.stop_loss,
                "lucro_dia": round(self.lucro_dia, 2),
                "wins": self.wins,
                "losses": self.losses,
                "win_rate": win_rate,
                "last_signal": self.last_signal,
                "confluence": self.confluence,
                "last_message": self.last_message,
                "error": self.error,
                "started_at": self.started_at,
                "server_time": time_br(),
                "timezone": "America/Sao_Paulo",
                "trades": list(self.trades[:50]),
            }

    def add_trade(self, trade: Dict[str, Any]) -> None:
        with self.lock:
            trade["id"] = len(self.trades) + 1
            trade["time"] = trade.get("time") or time_br()
            self.trades.insert(0, trade)
            self.trades = self.trades[:100]
            resultado = float(trade.get("resultado", 0) or 0)
            self.lucro_dia += resultado
            if resultado > 0:
                self.wins += 1
            elif resultado < 0:
                self.losses += 1


state = AppState()
