"""Estrategia Escadinha com confluencia Nano + Micro + Macro.

- Nano  = timeframe de entrada (ex: M1) — escadinha de velas + EMA
- Micro = timeframe medio (ex: M5) — tendencia EMA
- Macro = timeframe maior (ex: M15) — tendencia EMA

So gera sinal quando as 3 tendencias apontam a mesma direcao.
"""

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
        micro_mult: int = 5,
        macro_mult: int = 15,
        exigir_confluencia: bool = True,
        **kwargs,
    ):
        super().__init__(api, **kwargs)
        self.min_velas = max(2, int(min_velas))
        self.ema_rapida = int(ema_rapida)
        self.ema_lenta = int(ema_lenta)
        self.usar_filtro_ema = bool(usar_filtro_ema)
        self.micro_mult = max(2, int(micro_mult))
        self.macro_mult = max(self.micro_mult + 1, int(macro_mult))
        self.exigir_confluencia = bool(exigir_confluencia)

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

    def _get_candles(self, ativo: str, timeframe: int, qnt: int):
        candles = self.api.get_candles(ativo, timeframe, qnt, time.time())
        if not candles or len(candles) < 3:
            return None
        return candles

    def _trend_ema(self, ativo: str, timeframe: int) -> Optional[str]:
        """Retorna 'call', 'put' ou None conforme EMA rapida x lenta."""
        qnt = self.ema_lenta + 10
        candles = self._get_candles(ativo, timeframe, qnt)
        if not candles:
            return None

        closes = [c["close"] for c in candles]
        ema_f = self._ema(closes, self.ema_rapida)
        ema_s = self._ema(closes, self.ema_lenta)
        if ema_f is None or ema_s is None:
            return None

        # margem minima para evitar mercado lateral
        diff = abs(ema_f - ema_s) / max(abs(ema_s), 1e-9)
        if diff < 0.00005:  # ~0.005% — lateral demais
            return None

        if ema_f > ema_s:
            return "call"
        if ema_f < ema_s:
            return "put"
        return None

    def _nano_escadinha(self, ativo: str, timeframe: int) -> Optional[Tuple[str, str]]:
        """Sinal nano: sequencia de velas + EMA no TF de entrada."""
        qnt = max(self.min_velas + 5, self.ema_lenta + 10)
        candles = self._get_candles(ativo, timeframe, qnt)
        if not candles or len(candles) < self.min_velas:
            return None

        recent = candles[-self.min_velas :]
        colors = [self._candle_color(c) for c in recent]
        if "doji" in colors:
            return None

        closes = [c["close"] for c in candles]

        if all(c == "verde" for c in colors):
            if self.usar_filtro_ema:
                ema_f = self._ema(closes, self.ema_rapida)
                ema_s = self._ema(closes, self.ema_lenta)
                if ema_f is None or ema_s is None or not (ema_f > ema_s):
                    return None
            return "call", f"Nano: {self.min_velas} verdes"

        if all(c == "vermelha" for c in colors):
            if self.usar_filtro_ema:
                ema_f = self._ema(closes, self.ema_rapida)
                ema_s = self._ema(closes, self.ema_lenta)
                if ema_f is None or ema_s is None or not (ema_f < ema_s):
                    return None
            return "put", f"Nano: {self.min_velas} vermelhas"

        return None

    def analyze(self, ativo: str, timeframe: int = 60) -> Optional[Tuple[str, str]]:
        nano = self._nano_escadinha(ativo, timeframe)
        if not nano:
            return None

        direcao, motivo_nano = nano

        if not self.exigir_confluencia:
            return direcao, motivo_nano

        tf_micro = timeframe * self.micro_mult
        tf_macro = timeframe * self.macro_mult

        micro = self._trend_ema(ativo, tf_micro)
        macro = self._trend_ema(ativo, tf_macro)

        if micro is None or macro is None:
            return None

        # as 3 precisam apontar a mesma direcao
        if not (direcao == micro == macro):
            return None

        motivo = (
            f"{motivo_nano} | Micro TF{tf_micro}s={micro.upper()} "
            f"| Macro TF{tf_macro}s={macro.upper()}"
        )
        return direcao, motivo
