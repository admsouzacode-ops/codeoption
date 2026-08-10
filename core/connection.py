"""Gerenciamento de conexao com a IQ Option."""

from __future__ import annotations

from typing import Tuple

from iqoptionapi.stable_api import IQ_Option


class IQConnectionError(Exception):
    """Falha ao conectar na IQ Option."""


def connect_iq(email: str, senha: str, tipo_conta: str = "PRACTICE") -> Tuple[IQ_Option, str]:
    """
    Conecta na IQ Option e seleciona a conta (PRACTICE/REAL).

    Raises:
        IQConnectionError se falhar (nao mata o processo web).
    """
    if not email or not senha:
        raise IQConnectionError("IQ_EMAIL / IQ_PASSWORD nao configurados no environment.")

    print(f"[connect] conectando como {email[:3]}***...")
    api = IQ_Option(email, senha)

    try:
        check, reason = api.connect()
    except Exception as exc:
        raise IQConnectionError(f"Excecao no connect(): {exc}") from exc

    print(f"[connect] check={check} reason={reason}")

    if not check:
        reason_s = str(reason)
        if "invalid_credentials" in reason_s.lower():
            raise IQConnectionError("Email ou senha invalidos (IQ_EMAIL / IQ_PASSWORD).")
        if reason_s == "2FA":
            raise IQConnectionError("Conta com 2FA. Desative 2FA ou use conta sem 2FA.")
        raise IQConnectionError(f"Falha na conexao IQ Option: {reason}")

    tipo_conta = (tipo_conta or "PRACTICE").upper()
    if tipo_conta not in ("PRACTICE", "REAL"):
        tipo_conta = "PRACTICE"

    try:
        api.change_balance(tipo_conta)
    except Exception as exc:
        print(f"[connect] aviso change_balance: {exc}")

    # NAO chama get_all_open_time aqui (trava). Atualiza opcodes leve.
    try:
        api.update_ACTIVES_OPCODE()
    except Exception as exc:
        print(f"[connect] aviso update_ACTIVES_OPCODE: {exc}")

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
    try:
        check, reason = api.connect()
    except Exception as exc:
        print(f"[connect] falha reconectar: {exc}")
        return False

    if check:
        try:
            api.update_ACTIVES_OPCODE()
        except Exception:
            pass
        print("[connect] reconectado")
        return True

    print(f"[connect] falha reconectar: {reason}")
    return False
