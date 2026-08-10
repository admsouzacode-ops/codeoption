"""Gerenciamento de ordens, martingale e soros.

Nao chama get_all_open_time na hora do buy (trava o bot).
Tenta BINARY e depois DIGITAL em variantes do ativo.
"""

from __future__ import annotations

import sys
import time
from typing import Dict, List, Optional, Tuple

from .risk import RiskManager


def _log(msg: str) -> None:
    print(f"[order] {msg}", flush=True)
    sys.stdout.flush()


def _get_actives_map() -> Dict:
    try:
        import iqoptionapi.constants as constants

        return constants.ACTIVES or {}
    except Exception:
        return {}


def resolve_active_name(ativo: str, actives: Optional[Dict] = None) -> Optional[str]:
    raw = (ativo or "").strip()
    if not raw:
        return None

    actives = actives if actives is not None else _get_actives_map()
    if not actives:
        upper = raw.upper()
        if upper.endswith("-OP"):
            return upper[:-3] + "-op"
        return upper

    if raw in actives:
        return raw

    upper_map = {str(k).upper(): k for k in actives.keys()}
    upper = raw.upper()
    if upper in upper_map:
        return upper_map[upper]

    base = upper.replace("-OTC", "").replace("-OP", "")
    for cand in (base, f"{base}-OTC", f"{base}-op", f"{base}-OP", raw, upper):
        if cand in actives:
            return cand
        if cand.upper() in upper_map:
            return upper_map[cand.upper()]

    if upper.endswith("-OP"):
        return upper[:-3] + "-op"
    return upper


class OrderManager:
    def __init__(
        self,
        api,
        risk: RiskManager,
        tipo: str = "auto",
        martingale_niveis: int = 0,
        martingale_fator: float = 2.0,
        usar_soros: bool = False,
        niveis_soros: int = 0,
        currency: str = "$",
    ):
        self.api = api
        self.risk = risk
        self.tipo = (tipo or "auto").lower()
        self.martingale_niveis = max(0, int(martingale_niveis))
        self.martingale_fator = float(martingale_fator)
        self.usar_soros = bool(usar_soros)
        self.niveis_soros = max(0, int(niveis_soros))
        self.currency = currency

        self.nivel_soros = 0
        self.valor_soros = 0.0
        self.lucro_op_atual = 0.0
        self.last_error = ""
        self.last_tipo_usado = ""

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

    def _refresh_actives_light(self) -> None:
        """So opcodes — get_all_open_time trava e nao deve rodar no buy."""
        try:
            self.api.update_ACTIVES_OPCODE()
        except Exception as exc:
            _log(f"update_ACTIVES_OPCODE: {exc}")

    def _candidates(self, ativo: str) -> List[str]:
        actives = _get_actives_map()
        resolved = resolve_active_name(ativo, actives) or (ativo or "").strip()
        base = resolved.upper().replace("-OTC", "").replace("-OP", "")
        out: List[str] = []
        for c in (resolved, f"{base}-op", base, f"{base}-OTC", ativo):
            r = resolve_active_name(c, actives) or c
            if r and r not in out:
                out.append(r)
        return out

    def _try_binary(self, ativo: str, entrada: float, direcao: str, expiracao: int):
        _log(f"BINARY buy({entrada}, {ativo}, {direcao}, {expiracao})")
        try:
            check, order_id = self.api.buy(entrada, ativo, direcao, expiracao)
            _log(f"binary -> check={check} id={order_id}")
            return bool(check), order_id
        except KeyError as exc:
            msg = f"Opcode ausente '{ativo}': {exc}"
            _log(msg)
            return False, msg
        except Exception as exc:
            _log(f"binary Exception: {exc}")
            return False, str(exc)

    def _try_digital(self, ativo: str, entrada: float, direcao: str, expiracao: int):
        _log(f"DIGITAL buy_digital_spot_v2({ativo}, {entrada}, {direcao}, {expiracao})")
        try:
            check, order_id = self.api.buy_digital_spot_v2(ativo, entrada, direcao, expiracao)
            _log(f"digital -> check={check} id={order_id}")
            return bool(check), order_id
        except Exception as exc:
            _log(f"digital Exception: {exc}")
            return False, str(exc)

    def _open_order(self, ativo: str, entrada: float, direcao: str, expiracao: int):
        self._refresh_actives_light()

        direcao = (direcao or "call").lower()
        if direcao not in ("call", "put"):
            direcao = "call"

        force_digital = self.tipo.startswith("digital")
        force_binary = self.tipo.startswith("binar") or self.tipo.startswith("turbo")

        errors: List[str] = []
        for name in self._candidates(ativo):
            _log(f"tentando ativo '{name}' (origem '{ativo}')")

            if not force_digital:
                check, order_id = self._try_binary(name, entrada, direcao, expiracao)
                if check:
                    self.last_tipo_usado = "binary"
                    self.last_error = ""
                    return True, order_id, "binary"
                errors.append(f"binary/{name}: {order_id}")

            if not force_binary:
                check, order_id = self._try_digital(name, entrada, direcao, expiracao)
                if check:
                    self.last_tipo_usado = "digital"
                    self.last_error = ""
                    return True, order_id, "digital"
                errors.append(f"digital/{name}: {order_id}")

        self.last_error = " | ".join(str(e) for e in errors[-6:]) or "Falha ao abrir ordem"
        _log(f"falha em todas tentativas: {self.last_error}")
        return False, self.last_error, ""

    def _wait_result(self, order_id, tipo_usado: str, expiracao: int) -> Optional[float]:
        # exp 1 min -> espera ate ~90s; nao fica infinito
        timeout = max(75, int(expiracao) * 60 + 30)
        start = time.time()
        while True:
            time.sleep(0.5)
            try:
                if tipo_usado == "digital":
                    status, resultado = self.api.check_win_digital_v2(order_id)
                else:
                    status, resultado = self.api.check_win_v4(order_id)
            except Exception as exc:
                _log(f"check_win erro: {exc}")
                if time.time() - start > timeout:
                    return None
                continue

            if status:
                return float(resultado or 0)

            if time.time() - start > timeout:
                _log("timeout aguardando resultado")
                return None

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
        self.last_tipo_usado = ""

        _log(f"execute {direcao.upper()} {ativo} valor={entrada} exp={expiracao}")

        for i in range(self.martingale_niveis + 1):
            if not self.risk.can_trade:
                break

            check, order_id, tipo_usado = self._open_order(
                ativo, entrada, direcao, expiracao
            )

            if not check:
                msg = order_id if isinstance(order_id, str) else self.last_error
                _log(f"erro ao abrir ordem: {msg}")
                self.last_error = str(msg)
                break

            label = "entrada" if i == 0 else f"gale {i}"
            _log(
                f"ordem aberta ({label}/{tipo_usado}) | {ativo} | "
                f"{direcao.upper()} | {self.currency}{entrada:.2f} | id={order_id}"
            )

            resultado = self._wait_result(order_id, tipo_usado, expiracao)
            if resultado is None:
                self.last_error = "Timeout aguardando resultado"
                break

            resultado_final = float(resultado)
            self.risk.register(resultado_final)

            if self.usar_soros:
                self.valor_soros += resultado_final
                self.lucro_op_atual += resultado_final

            if resultado_final > 0:
                _log(f"WIN ({label}) {resultado_final:+.2f} total={self.risk.lucro_total:.2f}")
            elif resultado_final == 0:
                _log(f"EMPATE ({label}) total={self.risk.lucro_total:.2f}")
            else:
                _log(f"LOSS ({label}) {resultado_final:+.2f} total={self.risk.lucro_total:.2f}")

            if resultado_final <= 0 and i + 1 <= self.martingale_niveis:
                if resultado_final < 0:
                    entrada = round(abs(float(entrada) * self.martingale_fator), 2)

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
