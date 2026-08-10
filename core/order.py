"""Gerenciamento de ordens, martingale e soros."""

from __future__ import annotations

import time
from typing import Optional, Tuple

from iqoptionapi.constants import ACTIVES as OP_ACTIVES

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
        self.last_error = ""

    def _resolve_entrada(self, valor_base: float) -> float:
        if not self.usar_soros:
            return float(valor_base)

        if self.nivel_soros == 0:
            return float(valor_base)

        if 1 <= self.nivel_soros <= self.niveis_soros and self.valor_soros > 0:
            return float(valor_base) + float(self.valor_soros)

        self.lucro_op_atual = 0.0
        self.valor_soros = 0.0
        self.nivel_soros = 0
        return float(valor_base)

    def _refresh_actives(self) -> None:
        try:
            self.api.update_ACTIVES_OPCODE()
        except Exception:
            pass
        try:
            self.api.get_all_open_time()
        except Exception:
            pass

    def _resolve_asset(self, ativo: str) -> Optional[str]:
        """Resolve o nome do ativo no dicionario ACTIVES da API."""
        name = (ativo or "").upper().strip()
        if not name:
            return None

        # tenta atualizar opcodes (importante para mercado aberto)
        self._refresh_actives()

        actives = getattr(self.api, "ACTIVES", None) or OP_ACTIVES
        try:
            from iqoptionapi.constants import ACTIVES as live_actives

            actives = live_actives
        except Exception:
            pass

        # tambem olha OP_code se existir no modulo
        try:
            import iqoptionapi.constants as constants

            actives = constants.ACTIVES
        except Exception:
            pass

        candidates = [name]
        if name.endswith("-OTC"):
            candidates.append(name.replace("-OTC", ""))
        else:
            candidates.append(f"{name}-OTC")

        # variantes comuns
        for c in list(candidates):
            candidates.append(c.replace("/", ""))

        for cand in candidates:
            if cand in actives:
                return cand

        # busca case-insensitive / parcial
        upper_map = {str(k).upper(): k for k in actives.keys()}
        for cand in candidates:
            if cand in upper_map:
                return upper_map[cand]

        return None

    def _is_open(self, ativo: str) -> Tuple[bool, str]:
        """Verifica se o ativo esta aberto em turbo ou binary."""
        try:
            open_time = self.api.get_all_open_time()
        except Exception as exc:
            return True, f"nao foi possivel checar open_time: {exc}"

        for market in ("turbo", "binary"):
            bucket = open_time.get(market) or {}
            info = bucket.get(ativo)
            if isinstance(info, dict) and info.get("open"):
                return True, market

        # tenta sem -OTC / com -OTC
        alt = ativo.replace("-OTC", "") if "-OTC" in ativo else f"{ativo}-OTC"
        for market in ("turbo", "binary"):
            bucket = open_time.get(market) or {}
            info = bucket.get(alt)
            if isinstance(info, dict) and info.get("open"):
                return True, market

        return False, "fechado"

    def _open_order(self, ativo: str, entrada: float, direcao: str, expiracao: int):
        """Abre ordem binaria/turbo ou digital conforme tipo."""
        resolved = self._resolve_asset(ativo)
        if not resolved:
            self.last_error = f"Ativo '{ativo}' nao encontrado na API (opcode)."
            print(self.last_error)
            return False, self.last_error

        aberto, market = self._is_open(resolved)
        if not aberto:
            # tenta o alternativo OTC/normal
            alt = resolved.replace("-OTC", "") if "-OTC" in resolved else f"{resolved}-OTC"
            alt_resolved = self._resolve_asset(alt)
            if alt_resolved:
                aberto2, market2 = self._is_open(alt_resolved)
                if aberto2:
                    resolved = alt_resolved
                    market = market2
                    aberto = True

        if not aberto:
            self.last_error = f"Ativo '{resolved}' esta fechado no momento."
            print(self.last_error)
            return False, self.last_error

        direcao = (direcao or "call").lower()
        if direcao not in ("call", "put"):
            direcao = "call"

        # digital
        if self.tipo.startswith("digital"):
            check, order_id = self.api.buy_digital_spot_v2(
                resolved, entrada, direcao, expiracao
            )
            return check, order_id

        # binarias / turbo (padrao)
        try:
            check, order_id = self.api.buy(entrada, resolved, direcao, expiracao)
            return check, order_id
        except KeyError:
            self.last_error = f"Opcode ausente para '{resolved}'. Atualize ativos."
            print(self.last_error)
            return False, self.last_error
        except Exception as exc:
            self.last_error = str(exc)
            print(f"Erro buy: {exc}")
            return False, self.last_error

    def execute(
        self,
        ativo: str,
        valor_entrada: float,
        direcao: str,
        expiracao: int = 1,
    ) -> Optional[float]:
        if not self.risk.can_trade:
            return None

        entrada = self._resolve_entrada(valor_entrada)
        resultado_final = 0.0
        self.last_error = ""

        for i in range(self.martingale_niveis + 1):
            if not self.risk.can_trade:
                break

            check, order_id = self._open_order(ativo, entrada, direcao, expiracao)

            if not check:
                msg = order_id if isinstance(order_id, str) else self.last_error
                print(f"Erro ao abrir ordem: {msg} | ativo={ativo}")
                self.last_error = str(msg)
                break

            label = "entrada" if i == 0 else f"gale {i}"
            print(
                f">> Ordem aberta ({label}) | {ativo} | {direcao.upper()} | "
                f"{self.currency}{entrada:.2f} | id={order_id}"
            )

            while True:
                time.sleep(0.25)
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

                if resultado <= 0 and i + 1 <= self.martingale_niveis:
                    if resultado < 0:
                        entrada = round(abs(float(entrada) * self.martingale_fator), 2)
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
