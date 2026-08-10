"""Carrega configuracao via environment variables (Dokploy) com fallback para config.txt."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    from configobj import ConfigObj
except ImportError:
    ConfigObj = None


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(key)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env(key)
    if raw is None:
        return default
    return raw.upper() in ("1", "TRUE", "S", "SIM", "YES", "Y", "ON")


def _env_float(key: str, default: float) -> float:
    raw = _env(key)
    if raw is None:
        return float(default)
    return float(raw)


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    if raw is None:
        return int(default)
    return int(float(raw))


def _normalize_asset_env(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return "EURUSD-OTC"
    upper = raw.upper()
    if upper.endswith("-OP"):
        return upper[:-3] + "-op"
    if upper.endswith("-OTC"):
        return upper[:-4] + "-OTC"
    return upper


def _from_config_file(path: str = "config.txt") -> Dict[str, Any]:
    if ConfigObj is None or not os.path.exists(path):
        return {}
    cfg = ConfigObj(path)
    return {
        "email": cfg.get("LOGIN", {}).get("email"),
        "senha": cfg.get("LOGIN", {}).get("senha"),
        "tipo_conta": cfg.get("CONTA", {}).get("tipo_conta", "PRACTICE"),
        "tipo": cfg.get("AJUSTES", {}).get("tipo", "binarias"),
        "valor_entrada": cfg.get("AJUSTES", {}).get("valor_entrada", 2),
        "expiracao": cfg.get("AJUSTES", {}).get("expiracao", 1),
        "stop_win": cfg.get("AJUSTES", {}).get("stop_win", 50),
        "stop_loss": cfg.get("AJUSTES", {}).get("stop_loss", 30),
        "usar_martingale": str(cfg.get("MARTINGALE", {}).get("usar_martingale", "N")).upper() == "S",
        "niveis_martingale": cfg.get("MARTINGALE", {}).get("niveis_martingale", 2),
        "fator_martingale": cfg.get("MARTINGALE", {}).get("fator_martingale", 2.0),
        "usar_soros": str(cfg.get("SOROS", {}).get("usar_soros", "N")).upper() == "S",
        "niveis_soros": cfg.get("SOROS", {}).get("niveis_soros", 2),
        "estrategia": cfg.get("ESTRATEGIA", {}).get("nome", "escadinha"),
        "ativo": cfg.get("ESTRATEGIA", {}).get("ativo", "EURUSD-OTC"),
        "timeframe": cfg.get("ESTRATEGIA", {}).get("timeframe", 60),
        "min_velas": cfg.get("ESCADINHA", {}).get("min_velas", 3),
        "ema_rapida": cfg.get("ESCADINHA", {}).get("ema_rapida", 9),
        "ema_lenta": cfg.get("ESCADINHA", {}).get("ema_lenta", 21),
        "usar_filtro_ema": str(cfg.get("ESCADINHA", {}).get("usar_filtro_ema", "S")).upper() == "S",
        "micro_mult": cfg.get("ESCADINHA", {}).get("micro_mult", 5),
        "macro_mult": cfg.get("ESCADINHA", {}).get("macro_mult", 15),
        "exigir_confluencia": str(cfg.get("ESCADINHA", {}).get("exigir_confluencia", "S")).upper() == "S",
        "min_corpo_pct": cfg.get("ESCADINHA", {}).get("min_corpo_pct", 0.40),
        "max_losses_pause": cfg.get("ESCADINHA", {}).get("max_losses_pause", 2),
        "pause_minutes": cfg.get("ESCADINHA", {}).get("pause_minutes", 20),
        "hora_inicio": cfg.get("ESCADINHA", {}).get("hora_inicio", 0),
        "hora_fim": cfg.get("ESCADINHA", {}).get("hora_fim", 23),
        "usar_filtro_horario": str(cfg.get("ESCADINHA", {}).get("usar_filtro_horario", "N")).upper() == "S",
    }


def load_settings() -> Dict[str, Any]:
    file_cfg = _from_config_file()

    settings = {
        "email": _env("IQ_EMAIL", file_cfg.get("email")),
        "senha": _env("IQ_PASSWORD", file_cfg.get("senha")),
        "tipo_conta": (_env("IQ_ACCOUNT", file_cfg.get("tipo_conta", "PRACTICE")) or "PRACTICE").upper(),
        "tipo": (_env("IQ_ORDER_TYPE", file_cfg.get("tipo", "auto")) or "auto").lower(),
        "valor_entrada": _env_float("IQ_ENTRY_AMOUNT", float(file_cfg.get("valor_entrada", 2))),
        "expiracao": _env_int("IQ_EXPIRATION", int(file_cfg.get("expiracao", 1))),
        "stop_win": _env_float("IQ_STOP_WIN", float(file_cfg.get("stop_win", 50))),
        "stop_loss": _env_float("IQ_STOP_LOSS", float(file_cfg.get("stop_loss", 30))),
        "usar_martingale": _env_bool("IQ_MARTINGALE", bool(file_cfg.get("usar_martingale", False))),
        "niveis_martingale": _env_int("IQ_MARTINGALE_LEVELS", int(file_cfg.get("niveis_martingale", 2))),
        "fator_martingale": _env_float("IQ_MARTINGALE_FACTOR", float(file_cfg.get("fator_martingale", 2.0))),
        "usar_soros": _env_bool("IQ_SOROS", bool(file_cfg.get("usar_soros", False))),
        "niveis_soros": _env_int("IQ_SOROS_LEVELS", int(file_cfg.get("niveis_soros", 2))),
        "estrategia": (_env("IQ_STRATEGY", file_cfg.get("estrategia", "escadinha")) or "escadinha").lower(),
        "ativo": _normalize_asset_env(_env("IQ_ASSET", file_cfg.get("ativo", "EURUSD-OTC")) or "EURUSD-OTC"),
        "timeframe": _env_int("IQ_TIMEFRAME", int(file_cfg.get("timeframe", 60))),
        "min_velas": _env_int("IQ_MIN_CANDLES", int(file_cfg.get("min_velas", 3))),
        "ema_rapida": _env_int("IQ_EMA_FAST", int(file_cfg.get("ema_rapida", 9))),
        "ema_lenta": _env_int("IQ_EMA_SLOW", int(file_cfg.get("ema_lenta", 21))),
        "usar_filtro_ema": _env_bool("IQ_EMA_FILTER", bool(file_cfg.get("usar_filtro_ema", True))),
        "micro_mult": _env_int("IQ_MICRO_MULT", int(file_cfg.get("micro_mult", 5))),
        "macro_mult": _env_int("IQ_MACRO_MULT", int(file_cfg.get("macro_mult", 15))),
        "exigir_confluencia": _env_bool("IQ_CONFLUENCIA", bool(file_cfg.get("exigir_confluencia", True))),
        "min_corpo_pct": _env_float("IQ_MIN_BODY_PCT", float(file_cfg.get("min_corpo_pct", 0.40))),
        "max_losses_pause": _env_int("IQ_MAX_LOSSES_PAUSE", int(file_cfg.get("max_losses_pause", 2))),
        "pause_minutes": _env_int("IQ_PAUSE_MINUTES", int(file_cfg.get("pause_minutes", 20))),
        "usar_filtro_horario": _env_bool("IQ_HOUR_FILTER", bool(file_cfg.get("usar_filtro_horario", False))),
        "hora_inicio": _env_int("IQ_HOUR_START", int(file_cfg.get("hora_inicio", 9))),
        "hora_fim": _env_int("IQ_HOUR_END", int(file_cfg.get("hora_fim", 18))),
    }

    if not settings["email"] or not settings["senha"]:
        raise ValueError(
            "Credenciais ausentes. Defina IQ_EMAIL e IQ_PASSWORD no environment do Dokploy."
        )

    if not settings["usar_martingale"]:
        settings["niveis_martingale"] = 0
    if not settings["usar_soros"]:
        settings["niveis_soros"] = 0

    return settings
