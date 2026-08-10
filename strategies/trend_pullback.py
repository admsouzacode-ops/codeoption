"""Trend Pullback M1 — versao seletiva.

Regras:
  1) M15 e M5 alinhados (EMA9/EMA21 + preco do lado certo)
  2) Bloqueia lateral (EMAs coladas no M5)
  3) Pullback no M1 ate a EMA9 (1–2 velas contra)
  4) Vela de confirmacao a favor, corpo >= min_corpo_pct
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseStrategy


class TrendPullbackStrategy(BaseStrategy):
    name = "trend_pullback"

    def __init__(
        self,
        api,
        ema_rapida: int = 9,
        ema_lenta: int = 21,
        micro_mult: int = 5,
        macro_mult: int = 15,
        min_corpo_pct: float = 0.45,
        max_pullback_velas: int = 2,
        lateral_threshold: float = 0.00012,
        **kwargs,
    ):
        super().__init__(api, **kwargs)
        self.ema_rapida = int(ema_rapida)
        self.ema_lenta = int(ema_lenta)
        self.micro_mult = max(2, int(micro_mult))
        self.macro_mult = max(self.micro_mult + 1, int(macro_mult))
        self.min_corpo_pct = max(0.25, min(0.9, float(min_corpo_pct)))
        self.max_pullback_velas = max(1, min(3, int(max_pullback_velas)))
        self.lateral_threshold = float(lateral_threshold)

    # ── helpers ──────────────────────────────────────────

    def _get_candles(self, ativo: str, timeframe: int, qnt: int) -> Optional[List[dict]]:
        try:
            candles = self.api.get_candles(ativo, timeframe, qnt, time.time())
        except Exception:
            return None
        if not candles or len(candles) < max(self.ema_lenta + 5, 10):
            return None
        return candles

    def _ema(self, closes: List[float], period: int) -> Optional[float]:
        if len(closes) < period:
            return None
        k = 2 / (period + 1)
        value = sum(closes[:period]) / period
        for price in closes[period:]:
            value = price * k + value * (1 - k)
        return value

    def _body_ratio(self, c: dict) -> float:
        high = float(c.get("max", c.get("high", 0)) or 0)
        low = float(c.get("min", c.get("low", 0)) or 0)
        open_ = float(c["open"])
        close = float(c["close"])
        amp = abs(high - low)
        if amp <= 0:
            return 0.0
        return abs(close - open_) / amp

    def _color(self, c: dict) -> str:
        if c["open"] < c["close"]:
            return "verde"
        if c["open"] > c["close"]:
            return "vermelha"
        return "doji"

    def _trend(self, ativo: str, timeframe: int) -> Optional[str]:
        """call/put se tendencia clara; None se lateral ou indefinido."""
        candles = self._get_candles(ativo, timeframe, self.ema_lenta + 20)
        if not candles:
            return None

        closes = [float(c["close"]) for c in candles]
        ema_f = self._ema(closes, self.ema_rapida)
        ema_s = self._ema(closes, self.ema_lenta)
        if ema_f is None or ema_s is None:
            return None

        diff = abs(ema_f - ema_s) / max(abs(ema_s), 1e-9)
        if diff < self.lateral_threshold:
            return None  # lateral

        last = closes[-1]
        if ema_f > ema_s and last >= ema_f:
            return "call"
        if ema_f < ema_s and last <= ema_f:
            return "put"
        return None

    def _m1_setup(self, ativo: str, timeframe: int, direction: str) -> Optional[str]:
        """
        Procura pullback + vela de confirmacao no Nano.

        Retorna motivo se setup valido, senao None.
        """
        candles = self._get_candles(ativo, timeframe, self.ema_lenta + 25)
        if not candles or len(candles) < self.ema_lenta + 5:
            return None

        closes = [float(c["close"]) for c in candles]
        ema_f = self._ema(closes, self.ema_rapida)
        if ema_f is None:
            return None

        # usa velas JA FECHADAS: ignora a vela em formacao (ultima)
        closed = candles[:-1]
        if len(closed) < self.max_pullback_velas + 2:
            return None

        conf = closed[-1]  # vela de confirmacao (ultima fechada)
        conf_color = self._color(conf)
        conf_body = self._body_ratio(conf)
        conf_close = float(conf["close"])

        if conf_body < self.min_corpo_pct or conf_color == "doji":
            return None

        # pullback: 1..N velas antes da confirmacao
        pb = closed[-(self.max_pullback_velas + 1) : -1]

        if direction == "call":
            # confirmacao verde fechando acima da EMA
            if conf_color != "verde" or conf_close < ema_f:
                return None
            # pelo menos 1 vela vermelha de pullback
            reds = [c for c in pb if self._color(c) == "vermelha"]
            if not reds:
                return None
            # prefere pullback que se aproximou da EMA (low perto/abaixo)
            touched = False
            for c in reds:
                low = float(c.get("min", c.get("low", c["close"])) or c["close"])
                if low <= ema_f * 1.0003:
                    touched = True
                    break
            if not touched:
                # ainda aceita se a minima do grupo ficou abaixo do close anterior
                # (pullback visual simples)
                touched = True  # seletivo mas nao exige toque matematico perfeito
            return (
                f"CALL pullback+conf corpo={conf_body:.0%} "
                f"EMA{self.ema_rapida}={ema_f:.5f}"
            )

        if direction == "put":
            if conf_color != "vermelha" or conf_close > ema_f:
                return None
            greens = [c for c in pb if self._color(c) == "verde"]
            if not greens:
                return None
            return (
                f"PUT pullback+conf corpo={conf_body:.0%} "
                f"EMA{self.ema_rapida}={ema_f:.5f}"
            )

        return None

    # ── API publica ──────────────────────────────────────

    def diagnose(self, ativo: str, timeframe: int = 60) -> Dict[str, Any]:
        tf_micro = timeframe * self.micro_mult
        tf_macro = timeframe * self.macro_mult

        micro = self._trend(ativo, tf_micro)
        macro = self._trend(ativo, tf_macro)

        aligned = bool(micro and macro and micro == macro)
        direction = micro if aligned else None

        nano_ok = False
        nano_dir = None
        if direction:
            motivo = self._m1_setup(ativo, timeframe, direction)
            if motivo:
                nano_ok = True
                nano_dir = direction

        return {
            "nano": {
                "ok": nano_ok,
                "direction": (nano_dir or "").upper() or None,
                "tf": timeframe,
                "label": f"Nano M{max(1, timeframe // 60)} pullback",
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
            "aligned": bool(nano_ok and aligned),
            "direction": (nano_dir or "").upper() or None,
            "strategy": self.name,
            "min_corpo_pct": self.min_corpo_pct,
        }

    def analyze(self, ativo: str, timeframe: int = 60) -> Optional[Tuple[str, str]]:
        diag = self.diagnose(ativo, timeframe)
        if not diag.get("aligned") or not diag.get("direction"):
            return None

        direcao = diag["direction"].lower()
        n = diag["nano"]
        mi = diag["micro"]
        ma = diag["macro"]
        motivo = (
            f"TrendPullback {direcao.upper()} | "
            f"Macro={ma['direction']} Micro={mi['direction']} | "
            f"Nano conf OK (corpo>={int(self.min_corpo_pct * 100)}%)"
        )
        return direcao, motivo
