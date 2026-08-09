"""Gerenciamento de ordens, martingale e soros."""

from __future__ import annotations

import time
from typing import Optional, Tuple

from .risk import RiskManager


class OrderManager:
    def __init__(
        self,
        api,
        risk: RiskManager,
        tipo: str = "binarias",
        martingale_niveis: int = 0,
        martingale_fator: float = 2.0,
        usar_soros: bool = False,
        niveis_soros: int = 0,
        currency: str = "$",
    ):
        self.api = api
        self.risk = risk
        self.tipo = (tipo or "binarias").lower()
        self.martingale_niveis = max(0, int(martingale_niveis))
        self.martingale_fator = float(martingale_fator)
        self.usar_soros = bool(usar_soros)
        self.niveis_soros = max(0, int(niveis_soros))
        self.currency = currency

        self.nivel_soros = 0
        self.valor_soros = 0.0
        self.lucro_op_atual = 0.0

    def _resolve_entrada(self, valor_base: float) -> float:
        if not self.usar_soros:
            return float(valor_base)

        if self.nivel_soros == 0:
            return float(valor_base)

        if 1 <= self.nivel_soros <= self.niveis_soros and self.valor_soros > 0:
            return float(valor_base) + float(self.valor_soros)

        # reset se passou do limite
        self.lucro_op_atual = 0.0
        self.valor_soros = 0.0
        self.nivel_soros = 0
        return float(valor_base)

    def execute(
        self,
        ativo: str,
        valor_entrada: float,
        direcao: str,
        expiracao: int = 1,
    ) -> Optional[float]:
        """
        Abre ordem com suporte a martingale e soros.
        Retorna o resultado liquido da sequencia (win/loss).
        """
        if not self.risk.can_trade:
            return None

        entrada = self._resolve_entrada(valor_entrada)
        resultado_final = 0.0

        for i in range(self.martingale_niveis + 1):
            if not self.risk.can_trade:
                break

            if self.tipo.startswith("digital"):
                check, order_id = self.api.buy_digital_spot_v2(ativo, entrada, direcao, expiracao)
            else:
                check, order_id = self.api.buy(entrada, ativo, direcao, expiracao)

            if not check:
                print(f"Erro ao abrir ordem: {order_id} | ativo={ativo}")
                break

            label = "entrada" if i == 0 else f"gale {i}"
            print(f">> Ordem aberta ({label}) | {ativo} | {direcao.upper()} | {self.currency}{entrada:.2f}")

            while True:
                time.sleep(0.2)
                if self.tipo.startswith("digital"):
                    status, resultado = self.api.check_win_digital_v2(order_id)
                else:
                    status, resultado = self.api.check_win_v4(order_id)

                if not status:
                    continue

                resultado = float(resultado or 0)
                resultado_final = resultado
                self.risk.register(resultado)

                if self.usar_soros:
                    self.valor_soros += resultado
                    self.lucro_op_atual += resultado

                if resultado > 0:
                    print(f">> WIN ({label}) | {resultado:+.2f} | Total: {self.risk.lucro_total:.2f}")
                elif resultado == 0:
                    print(f">> EMPATE ({label}) | Total: {self.risk.lucro_total:.2f}")
                else:
                    print(f">> LOSS ({label}) | {resultado:+.2f} | Total: {self.risk.lucro_total:.2f}")

                # prepara proximo gale se perdeu/empatou
                if resultado <= 0 and i + 1 <= self.martingale_niveis:
                    if resultado < 0:
                        entrada = round(abs(float(entrada) * self.martingale_fator), 2)
                    # empate: mantem valor
                break

            if resultado_final > 0:
                break

        if self.usar_soros:
            if self.lucro_op_atual > 0:
                self.nivel_soros += 1
                self.lucro_op_atual = 0.0
            else:
                self.valor_soros = 0.0
                self.nivel_soros = 0
                self.lucro_op_atual = 0.0

        return self.risk.lucro_total
