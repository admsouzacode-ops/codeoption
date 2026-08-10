"""Gerenciamento de conexao com a IQ Option."""

from __future__ import annotations

import sys
import threading
from typing import Any, Tuple

from iqoptionapi.stable_api import IQ_Option


def _log(msg: str) -> None:
    """Log visivel no Dokploy (uvicorn captura stdout)."""
    line = f"[iq.connect] {msg}"
    print(line, flush=True)
    sys.stdout.flush()


class IQConnectionError(Exception):
    """Falha ao conectar na IQ Option."""


def _connect_with_timeout(api: IQ_Option, timeout: float = 20.0) -> Tuple[bool, Any]:
    result: dict = {"done": False, "check": False, "reason": "timeout"}

    def worker() -> None:
        try:
            _log("api.connect() iniciado...")
            check, reason = api.connect()
            result["check"] = bool(check)
            result["reason"] = reason
            _log(f"api.connect() retornou check={check} reason={reason}")
        except Exception as exc:
            result["check"] = False
            result["reason"] = f"exception: {type(exc).__name__}: {exc}"
            _log(f"api.connect() EXCEPTION: {exc}")
        finally:
            result["done"] = True

    t = threading.Thread(target=worker, daemon=True, name="iq-connect")
    t.start()
    t.join(timeout=timeout)

    if not result["done"]:
        msg = (
            f"Timeout apos {int(timeout)}s. "
            "Provavel bloqueio de IP (VPS/datacenter) pela IQ Option."
        )
        _log(msg)
        return False, msg

    return bool(result["check"]), result["reason"]


def connect_iq(
    email: str,
    senha: str,
    tipo_conta: str = "PRACTICE",
    timeout: float = 20.0,
) -> Tuple[IQ_Option, str]:
    if not email or not senha:
        raise IQConnectionError("IQ_EMAIL / IQ_PASSWORD nao configurados no environment.")

    _log(f"inicio email={email[:4]}*** senha_len={len(senha)} conta={tipo_conta} timeout={timeout}s")
    api = IQ_Option(email, senha)

    check, reason = _connect_with_timeout(api, timeout=timeout)

    if not check:
        reason_s = str(reason)
        low = reason_s.lower()
        if "invalid_credentials" in low:
            raise IQConnectionError("Email ou senha invalidos (IQ_EMAIL / IQ_PASSWORD).")
        if reason_s == "2FA" or "2fa" in low:
            raise IQConnectionError("Conta com 2FA. Desative 2FA ou use conta sem 2FA.")
        if "timeout" in low or "bloqueio" in low:
            raise IQConnectionError(reason_s)
        raise IQConnectionError(f"Falha na conexao IQ Option: {reason}")

    tipo_conta = (tipo_conta or "PRACTICE").upper()
    if tipo_conta not in ("PRACTICE", "REAL"):
        tipo_conta = "PRACTICE"

    try:
        api.change_balance(tipo_conta)
        _log(f"change_balance({tipo_conta}) ok")
    except Exception as exc:
        _log(f"change_balance falhou: {exc}")

    try:
        saldo = float(api.get_balance())
    except Exception as exc:
        _log(f"get_balance falhou: {exc}")
        saldo = 0.0

    status = f"Conectado | Conta: {tipo_conta} | Saldo: {saldo}"
    _log(status)
    return api, status


def ensure_connected(api: IQ_Option, email: str, senha: str) -> bool:
    try:
        if api.check_connect():
            return True
    except Exception:
        pass

    _log("conexao perdida, reconectando...")
    check, reason = _connect_with_timeout(api, timeout=15.0)
    if check:
        _log("reconectado")
        return True

    _log(f"falha reconectar: {reason}")
    return False
