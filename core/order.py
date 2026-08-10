"""Gerenciamento de ordens, martingale e soros."""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

from .risk import RiskManager


def _get_actives_map() -> Dict:
    try:
        import iqoptionapi.constants as constants

        return constants.ACTIVES or {}
    except Exception:
        return {}


def resolve_active_name(ativo: str, actives: Optional[Dict] = None) -> Optional[str]:
    """
    Resolve o nome exato no dicionario ACTIVES da IQ Option.

    A API usa chaves sensiveis a maiusculas:
      EURUSD, EURUSD-OTC, EURUSD-op
    (nao EURUSD-OP)
    """
    raw = (ativo or "").strip()
    if not raw:
        return None

    actives = actives if actives is not None else _get_actives_map()
    if not actives:
        return raw

    # match exato
    if raw in actives:
        return raw

    upper = raw.upper()
    # mapa case-insensitive: UPPER -> chave real
    upper_map = {str(k).upper(): k for k in actives.keys()}

    if upper in upper_map:
        return upper_map[upper]

    # candidatos comuns
    base = upper.replace("-OTC", "").replace("-OP", "")
    candidates = [
        base,
        f"{base}-OTC",
        f"{base}-op",  # forma correta na API
        f"{base}-OP",
        raw,
        upper,
    ]

    for cand in candidates:
        if cand in actives:
            return cand
        if cand.upper() in upper_map:
            return upper_map[cand.upper()]

    return None


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

    def _is_open(self, ativo: str) -> Tuple[bool, str]:
        try:
            open_time = self.api.get_all_open_time()
        except Exception as exc:
            return True, f"nao checou open_time: {exc}"

        # open_time keys podem vir com case diferente
        for market in ("turbo", "binary"):
            bucket = open_time.get(market) or {}
            # match case-insensitive
            for name, info in bucket.items():
                if str(name).upper() == str(ativo).upper() and isinstance(info, dict) and info.get("open"):
                    return True, market

        return False, "fechado"

    def _open_order(self, ativo: str, entrada: float, direcao: str, expiracao: int):
        self._refresh_actives()
        actives = _get_actives_map()

        resolved = resolve_active_name(ativo, actives)
        if not resolved:
            self.last_error = (
                f"Ativo '{ativo}' nao encontrado na API. "
                f"Tente EURUSD, EURUSD-OTC ou EURUSD-op."
            )
            print(self.last_error)
            return False, self.last_error

        aberto, market = self._is_open(resolved)
        if not aberto:
            # tenta alternativas do mesmo par
            base = resolved.upper().replace("-OTC", "").replace("-OP", "")
            for alt in (base, f"{base}-OTC", f"{base}-op"):
                alt_resolved = resolve_active_name(alt, actives)
                if not alt_resolved or alt_resolved == resolved:
                    continue
                ok2, market2 = self._is_open(alt_resolved)
                if ok2:
                    resolved = alt_resolved
                    market = market2
                    aberto = True
                    break

        if not aberto:
            self.last_error = (
                f"Ativo '{resolved}' fechado agora. "
                f"Mercado normal so abre em horario comercial."
            )
            print(self.last_error)
            return False, self.last_error

        direcao = (direcao or "call").lower()
        if direcao not in ("call", "put"):
            direcao = "call"

        print(f">> Abrindo ordem em '{resolved}' (origem '{ativo}', market={market})")

        if self.tipo.startswith("digital"):
            check, order_id = self.api.buy_digital_spot_v2(
                resolved, entrada, direcao, expiracao
            )
            return check, order_id

        try:
            check, order_id = self.api.buy(entrada, resolved, direcao, expiracao)
            return check, order_id
        except KeyError:
            self.last_error = f"Opcode ausente para '{resolved}'."
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
