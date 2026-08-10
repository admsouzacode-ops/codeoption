"""Gerenciamento de conexao com a IQ Option."""

from __future__ import annotations

import logging
import threading
from typing import Any, Tuple

from iqoptionapi.stable_api import IQ_Option

log = logging.getLogger("iq.connect")


class IQConnectionError(Exception):
    """Falha ao conectar na IQ Option."""


def _connect_with_timeout(api: IQ_Option, timeout: float = 25.0) -> Tuple[bool, Any]:
    result: dict = {"done": False, "check": False, "reason": "timeout"}

    def worker() -> None:
        try:
            log.info("api.connect() iniciado...")
            check, reason = api.connect()
            result["check"] = check
            result["reason"] = reason
            log.info("api.connect() retornou check=%s reason=%s", check, reason)
        except Exception as exc:
            result["check"] = False
            result["reason"] = f"exception: {exc}"
            log.exception("api.connect() exception")
        finally:
            result["done"] = True

    t = threading.Thread(target=worker, daemon=True, name="iq-connect")
    t.start()
    t.join(timeout=timeout)

    if not result["done"]:
        msg = (
            f"Timeout apos {int(timeout)}s. "
            f"Servidor pode estar bloqueado pela IQ (IP de datacenter/VPS)."
        )
        log.error(msg)
        return False, msg

    return bool(result["check"]), result["reason"]


def connect_iq(
    email: str,
    senha: str,
    tipo_conta: str = "PRACTICE",
    timeout: float = 25.0,
) -> Tuple[IQ_Option, str]:
    if not email or not senha:
        raise IQConnectionError("IQ_EMAIL / IQ_PASSWORD nao configurados no environment.")

    log.info("Conectando IQ email=%s*** timeout=%ss conta=%s", email[:3], int(timeout), tipo_conta)
    api = IQ_Option(email, senha)

    check, reason = _connect_with_timeout(api, timeout=timeout)

    if not check:
        reason_s = str(reason)
        low = reason_s.lower()
        if "invalid_credentials" in low:
            raise IQConnectionError("Email ou senha invalidos (IQ_EMAIL / IQ_PASSWORD).")
        if reason_s == "2FA" or "2fa" in low:
            raise IQConnectionError("Conta com 2FA. Desative 2FA ou use conta sem 2FA.")
        if "timeout" in low:
            raise IQConnectionError(reason_s)
        raise IQConnectionError(f"Falha na conexao IQ Option: {reason}")

    tipo_conta = (tipo_conta or "PRACTICE").upper()
    if tipo_conta not in ("PRACTICE", "REAL"):
        tipo_conta = "PRACTICE"

    try:
        api.change_balance(tipo_conta)
        log.info("change_balance(%s) ok", tipo_conta)
    except Exception as exc:
        log.warning("change_balance falhou: %s", exc)

    try:
        api.update_ACTIVES_OPCODE()
    except Exception as exp:
        log.warning("update_ACTIVES_OPCODE: %s", exp)

    try:
        saldo = float(api.get_balance())
    except Exception:
        saldo = 0.0

    status = f"Conectado | Conta: {tipo_conta} | Saldo: {saldo}"
    log.info(status)
    return api, status


def ensure_connected(api: IQ_Option, email: str, senha: str) -> bool:
    try:
        if api.check_connect():
            return True
    except Exception:
        pass

    log.warning("Conexao perdida, reconectando...")
    check, reason = _connect_with_timeout(api, timeout=20.0)
    if check:
        try:
            api.update_ACTIVES_OPCODE()
        except Exception:
            pass
        log.info("Reconectado")
        return True

    log.error("Falha ao reconectar: %s", reason)
    return False
