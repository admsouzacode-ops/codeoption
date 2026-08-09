"""Gestao de risco: stop win / stop loss (sem matar o processo web)."""

from __future__ import annotations


class RiskManager:
    def __init__(self, stop_win: float, stop_loss: float, currency: str = "$"):
        self.stop_win = abs(float(stop_win))
        self.stop_loss = abs(float(stop_loss))
        self.currency = currency
        self.lucro_total = 0.0
        self.active = True
        self.stop_reason = ""

    def update_stops(self, stop_win: float, stop_loss: float) -> None:
        self.stop_win = abs(float(stop_win))
        self.stop_loss = abs(float(stop_loss))
        self._check()

    def register(self, resultado: float) -> None:
        self.lucro_total += float(resultado)
        self._check()

    def _check(self) -> None:
        if self.lucro_total <= -self.stop_loss:
            self.active = False
            self.stop_reason = "STOP_LOSS"
            print(f"\n### STOP LOSS BATIDO {self.currency}{self.lucro_total:.2f} ###")
            return

        if self.lucro_total >= self.stop_win:
            self.active = False
            self.stop_reason = "STOP_WIN"
            print(f"\n### STOP WIN BATIDO {self.currency}{self.lucro_total:.2f} ###")

    @property
    def can_trade(self) -> bool:
        return self.active
