"""Gerenciamento de conexao com a IQ Option."""

from __future__ import annotations

import sys
from typing import Tuple

from iqoptionapi.stable_api import IQ_Option


def connect_iq(email: str, senha: str, tipo_conta: str = "PRACTICE") -> Tuple[IQ_Option, str]:
    """
    Conecta na IQ Option e seleciona a conta (PRACTICE/REAL).

    Returns:
        (api, mensagem_status)
    """
    api = IQ_Option(email, senha)
    check, reason = api.connect()

    if not check:
        if isinstance(reason, str) and "invalid_credentials" in reason:
            print("Email ou senha incorreta.")
        else:
            print("Falha na conexao:", reason)
        sys.exit(1)

    tipo_conta = (tipo_conta or "PRACTICE").upper()
    if tipo_conta not in ("PRACTICE", "REAL"):
        tipo_conta = "PRACTICE"

    api.change_balance(tipo_conta)
    saldo = api.get_balance()
    status = f"Conectado | Conta: {tipo_conta} | Saldo: {saldo}"
    print(status)
    return api, status


def ensure_connected(api: IQ_Option, email: str, senha: str) -> bool:
    """Reconecta se a websocket cair."""
    if api.check_connect():
        return True
    print("Conexao perdida. Tentando reconectar...")
    check, reason = api.connect()
    if check:
        print("Reconectado com sucesso.")
        return True
    print("Falha ao reconectar:", reason)
    return False
