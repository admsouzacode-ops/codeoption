"""Estrategia Escadinha: sequencia de velas + confirmacao de tendencia."""

from __future__ import annotations

import time
from typing import Optional, Tuple

from .base import BaseStrategy


class EscadinhaStrategy(BaseStrategy):
    name = "escadinha"

    def __init__(
        self,
        api,
        min_velas: int = 3,
        ema_rapida: int = 9,
        ema_lenta: int = 21,
        usar_filtro_ema: bool = True,
        **kwargs,
    ):
        super().__init__(api, **kwargs)
        self.min_velas = max(2, int(min_velas))
        self.ema_rapida = int(ema_rapida)
        self.ema_lenta = int(ema_lenta)
        self.usar_filtro_ema = bool(usar_filtro_ema)

    def _candle_color(self, candle: dict) -> str:
        if candle["open"] < candle["close"]:
            return "verde"
        if candle["open"] > candle["close"]:
            return "vermelha"
        return "doji"

    def _ema(self, closes, period: int):
        if len(closes) < period:
            return None
        k = 2 / (period + 1)
        value = sum(closes[:period]) / period
        for price in closes[period:]:
            value = price * k + value * (1 - k)
        return value

    def analyze(self, ativo: str, timeframe: int = 60) -> Optional[Tuple[str, str]]:
        qnt = max(self.min_velas + 5, self.ema_lenta + 5)
        candles = self.api.get_candles(ativo, timeframe, qnt, time.time())
        if not candles or len(candles) < self.min_velas:
            return None

        # get_candles retorna do mais antigo para o mais recente
        recent = candles[-self.min_velas :]
        colors = [self._candle_color(c) for c in recent]

        if "doji" in colors:
            return None

        closes = [c["close"] for c in candles]

        # Escadinha de alta
        if all(c == "verde" for c in colors):
            if self.usar_filtro_ema:
                ema_f = self._ema(closes, self.ema_rapida)
                ema_s = self._ema(closes, self.ema_lenta)
                if ema_f is None or ema_s is None or not (ema_f > ema_s):
                    return None
            # continuidade de fechamentos
            if not all(closes[-i] > closes[-i - 1] for i in range(1, self.min_velas)):
                # nao bloqueia totalmente; apenas preferencial
                pass
            return "call", f"Escadinha ALTA ({self.min_velas} verdes)" + (
                " + EMA" if self.usar_filtro_ema else ""
            )

        # Escadinha de baixa
        if all(c == "vermelha" for c in colors):
            if self.usar_filtro_ema:
                ema_f = self._ema(closes, self.ema_rapida)
                ema_s = self._ema(closes, self.ema_lenta)
                if ema_f is None or ema_s is None or not (ema_f < ema_s):
                    return None
            return "put", f"Escadinha BAIXA ({self.min_velas} vermelhas)" + (
                " + EMA" if self.usar_filtro_ema else ""
            )

        return None
