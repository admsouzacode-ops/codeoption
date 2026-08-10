"""Gerenciamento de conexao com a IQ Option."""

from __future__ import annotations

import threading
from typing import Any, Tuple

from iqoptionapi.stable_api import IQ_Option


class IQConnectionError(Exception):
    """Falha ao conectar na IQ Option."""


def _connect_with_timeout(api: IQ_Option, timeout: float = 25.0) -> Tuple[bool, Any]:
    """Executa api.connect() com timeout para nao travar o bot."""
    result: dict = {"done": False, "check": False, "reason": "timeout"}

    def worker() -> None:
        try:
            check, reason = api.connect()
            result["check"] = check
            result["reason"] = reason
        except Exception as exc:
            result["check"] = False
            result["reason"] = f"exception: {exc}"
        finally:
            result["done"] = True

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if not result["done"]:
        return False, (
            f"Timeout apos {int(timeout)}s. "
            f"Servidor pode estar bloqueado pela IQ (IP de datacenter/VPS)."
        )

    return bool(result["check"]), result["reason"]


def connect_iq(
    email: str,
    senha: str,
    tipo_conta: str = "PRACTICE",
    timeout: float = 25.0,
) -> Tuple[IQ_Option, str]:
    """
    Conecta na IQ Option e seleciona a conta (PRACTICE/REAL).

    Raises:
        IQConnectionError se falhar (nao mata o processo web).
    """
    if not email or not senha:
        raise IQConnectionError("IQ_EMAIL / IQ_PASSWORD nao configurados no environment.")

    print(f"[connect] conectando como {email[:3]}*** (timeout={timeout}s)...")
    api = IQ_Option(email, senha)

    check, reason = _connect_with_timeout(api, timeout=timeout)
    print(f"[connect] check={check} reason={reason}")

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
    except Exception as exc:
        print(f"[connect] aviso change_balance: {exc}")

    try:
        api.update_ACTIVES_OPCODE()
    except Exception as exp:
        print(f"[connect] aviso update_ACTIVES_OPCODE: {exp}")

    try:
        saldo = float(api.get_balance())
    except Exception:
        saldo = 0.0

    status = f"Conectado | Conta: {tipo_conta} | Saldo: {saldo}"
    print(f"[connect] {status}")
    return api, status


def ensure_connected(api: IQ_Option, email: str, senha: str) -> bool:
    """Reconecta se a websocket cair."""
    try:
        if api.check_connect():
            return True
    except Exception:
        pass

    print("[connect] conexao perdida, reconectando...")
    check, reason = _connect_with_timeout(api, timeout=20.0)
    if check:
        try:
            api.update_ACTIVES_OPCODE()
        except Exception:
            pass
        print("[connect] reconectado")
        return True

    print(f"[connect] falha reconectar: {reason}")
    return False
