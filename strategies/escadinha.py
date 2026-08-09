"""Estrategia Escadinha com confluencia Nano + Micro + Macro."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

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
        try:
            candles = self.api.get_candles(ativo, timeframe, qnt, time.time())
        except Exception:
            return None
        if not candles or len(candles) < 3:
            return None
        return candles

    def _trend_ema(self, ativo: str, timeframe: int) -> Optional[str]:
        qnt = self.ema_lenta + 10
        candles = self._get_candles(ativo, timeframe, qnt)
        if not candles:
            return None

        closes = [c["close"] for c in candles]
        ema_f = self._ema(closes, self.ema_rapida)
        ema_s = self._ema(closes, self.ema_lenta)
        if ema_f is None or ema_s is None:
            return None

        diff = abs(ema_f - ema_s) / max(abs(ema_s), 1e-9)
        if diff < 0.00005:
            return None

        if ema_f > ema_s:
            return "call"
        if ema_f < ema_s:
            return "put"
        return None

    def _nano_escadinha(self, ativo: str, timeframe: int) -> Optional[str]:
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
            return "call"

        if all(c == "vermelha" for c in colors):
            if self.usar_filtro_ema:
                ema_f = self._ema(closes, self.ema_rapida)
                ema_s = self._ema(closes, self.ema_lenta)
                if ema_f is None or ema_s is None or not (ema_f < ema_s):
                    return None
            return "put"

        return None

    def diagnose(self, ativo: str, timeframe: int = 60) -> Dict[str, Any]:
        """Status de cada camada para a UI Live."""
        tf_micro = timeframe * self.micro_mult
        tf_macro = timeframe * self.macro_mult

        nano = self._nano_escadinha(ativo, timeframe)
        micro = self._trend_ema(ativo, tf_micro)
        macro = self._trend_ema(ativo, tf_macro)

        aligned = False
        direction = None
        if nano and micro and macro and nano == micro == macro:
            aligned = True
            direction = nano
        elif not self.exigir_confluencia and nano:
            aligned = True
            direction = nano

        return {
            "nano": {
                "ok": nano is not None,
                "direction": (nano or "").upper() or None,
                "tf": timeframe,
                "label": f"Nano M{max(1, timeframe // 60)}",
            },
            "micro": {
                "ok": micro is not None,
                "direction": (micro or "").upper() or None,
                "tf": tf_micro,
                "label": f"Micro M{max(1, tf_micro // 60)}",
            },
            "macro": {
                "ok": macro is not None,
                "direction": (macro or "").upper() or None,
                "tf": tf_macro,
                "label": f"Macro M{max(1, tf_macro // 60)}",
            },
            "aligned": aligned,
            "direction": (direction or "").upper() or None,
            "exigir_confluencia": self.exigir_confluencia,
        }

    def analyze(self, ativo: str, timeframe: int = 60) -> Optional[Tuple[str, str]]:
        diag = self.diagnose(ativo, timeframe)
        if not diag["aligned"] or not diag["direction"]:
            return None

        direcao = diag["direction"].lower()
        n = diag["nano"]
        mi = diag["micro"]
        ma = diag["macro"]
        motivo = (
            f"Nano {n['direction']} | Micro TF{mi['tf']}s={mi['direction']} "
            f"| Macro TF{ma['tf']}s={ma['direction']}"
        )
        return direcao, motivo
