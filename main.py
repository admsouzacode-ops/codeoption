"""
Sistema modular de estrategias para IQ Option.

Configuracao:
  - Preferencial: environment variables (Dokploy)
  - Fallback local: config.txt

Recursos:
  - Martingale
  - Soros
  - Stop Win / Stop Loss
  - Estrategia inicial: Escadinha
"""

from __future__ import annotations

import json
import time
from datetime import datetime

from core.connection import connect_iq, ensure_connected
from core.order import OrderManager
from core.risk import RiskManager
from core.settings import load_settings
from strategies import get_strategy


def banner():
    print(
        """
============================================================
   IQ Option System - Multi Estrategias
   Config: ENV (Dokploy) + fallback config.txt
   Recursos: Martingale + Soros + Stop Win/Loss
============================================================
"""
    )


def main():
    banner()
    cfg = load_settings()

    api, _ = connect_iq(cfg["email"], cfg["senha"], cfg["tipo_conta"])

    perfil = json.loads(json.dumps(api.get_profile_ansyc()))
    currency = str(perfil.get("currency_char", "$"))
    nome = str(perfil.get("name", "trader"))
    saldo = float(api.get_balance())

    print(f"Ola, {nome}")
    print(f"Saldo: {currency}{saldo:.2f}")
    print(f"Conta: {cfg['tipo_conta']}")
    print(f"Ativo: {cfg['ativo']} | TF: {cfg['timeframe']}s | Exp: {cfg['expiracao']}m")
    print(f"Estrategia: {cfg['estrategia']}")
    print(
        f"Martingale: {'ON' if cfg['niveis_martingale'] else 'OFF'} "
        f"({cfg['niveis_martingale']} niveis x{cfg['fator_martingale']})"
    )
    print(f"Soros: {'ON' if cfg['usar_soros'] else 'OFF'} ({cfg['niveis_soros']} niveis)")
    print(f"Stop Win: {currency}{cfg['stop_win']} | Stop Loss: {currency}{cfg['stop_loss']}")
    print("============================================================\n")

    risk = RiskManager(
        stop_win=cfg["stop_win"],
        stop_loss=cfg["stop_loss"],
        currency=currency,
    )

    orders = OrderManager(
        api=api,
        risk=risk,
        tipo=cfg["tipo"],
        martingale_niveis=cfg["niveis_martingale"],
        martingale_fator=cfg["fator_martingale"],
        usar_soros=cfg["usar_soros"],
        niveis_soros=cfg["niveis_soros"],
        currency=currency,
    )

    strategy = get_strategy(
        cfg["estrategia"],
        api,
        min_velas=cfg["min_velas"],
        ema_rapida=cfg["ema_rapida"],
        ema_lenta=cfg["ema_lenta"],
        usar_filtro_ema=cfg["usar_filtro_ema"],
    )

    ultimo_sinal_ts = 0.0
    timeframe = cfg["timeframe"]

    while risk.can_trade:
        try:
            if not ensure_connected(api, cfg["email"], cfg["senha"]):
                time.sleep(3)
                continue

            result = strategy.analyze(cfg["ativo"], timeframe)
            now_ts = time.time()

            if result and (now_ts - ultimo_sinal_ts) > timeframe:
                direcao, motivo = result
                print("\n" + "=" * 60)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SINAL: {direcao.upper()}")
                print(f"Motivo: {motivo}")
                print(f"Ativo: {cfg['ativo']} | Entrada apos fechamento da vela")
                print("=" * 60)

                server_now = datetime.fromtimestamp(api.get_server_timestamp())
                espera = max(1, timeframe - server_now.second)
                print(f"Aguardando fechamento da vela (~{espera}s)...")
                time.sleep(espera + 1)

                orders.execute(
                    ativo=cfg["ativo"],
                    valor_entrada=cfg["valor_entrada"],
                    direcao=direcao,
                    expiracao=cfg["expiracao"],
                )
                ultimo_sinal_ts = time.time()
                print()
            else:
                ts = datetime.fromtimestamp(api.get_server_timestamp()).strftime("%H:%M:%S")
                print(
                    f"[{ts}] Monitorando {cfg['ativo']} | estrategia={strategy.name} ...",
                    end="\r",
                )
                time.sleep(1)

        except KeyboardInterrupt:
            print("\nEncerrado pelo usuario.")
            break
        except Exception as exc:
            print("\nErro no loop principal:", exc)
            time.sleep(3)

    print(f"\nLucro total da sessao: {currency}{risk.lucro_total:.2f}")


if __name__ == "__main__":
    main()
