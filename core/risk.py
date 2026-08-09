"""Gestao de risco: stop win / stop loss."""

from __future__ import annotations

import sys


class RiskManager:
    def __init__(self, stop_win: float, stop_loss: float, currency: str = "$"):
        self.stop_win = abs(float(stop_win))
        self.stop_loss = abs(float(stop_loss))
        self.currency = currency
        self.lucro_total = 0.0
        self.active = True

    def register(self, resultado: float) -> None:
        self.lucro_total += float(resultado)
        self._check()

    def _check(self) -> None:
        if self.lucro_total <= -self.stop_loss:
            self.active = False
            print("\n#########################")
            print(f"STOP LOSS BATIDO {self.currency}{self.lucro_total:.2f}")
            print("#########################")
            sys.exit(0)

        if self.lucro_total >= self.stop_win:
            self.active = False
            print("\n#########################")
            print(f"STOP WIN BATIDO {self.currency}{self.lucro_total:.2f}")
            print("#########################")
            sys.exit(0)

    @property
    def can_trade(self) -> bool:
        return self.active
