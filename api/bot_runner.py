"""Executa a estrategia em background e atualiza o AppState."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from core.connection import connect_iq, ensure_connected
from core.order import OrderManager
from core.risk import RiskManager
from core.settings import load_settings
from strategies import get_strategy

from api.state import state, time_br

TZ = ZoneInfo("America/Sao_Paulo")


class BotRunner:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._risk: Optional[RiskManager] = None
        self._api = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def update_stops(self, stop_win: float, stop_loss: float) -> None:
        if self._risk is not None:
            self._risk.update_stops(stop_win, stop_loss)

    def start(self) -> Dict:
        if self.is_running:
            return {"ok": False, "message": "Bot ja esta em execucao"}

        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return {"ok": True, "message": "Bot iniciado"}

    def stop(self) -> Dict:
        self._stop.set()
        with state.lock:
            state.bot_running = False
            state.last_signal = None
            state.confluence = None
            state.last_message = "Bot parado"
        return {"ok": True, "message": "Bot parado"}

    def _seed_state(self, cfg: dict) -> None:
        """Preenche state com ENV se ainda nao foi editado na UI."""
        with state.lock:
            if not state.asset:
                state.asset = cfg["ativo"]
            # se o asset ainda e o default e o ENV e diferente, respeita UI se ja mudou
            state.strategy = cfg["estrategia"]
            state.account = cfg["tipo_conta"]
            if not state.timeframe:
                state.timeframe = cfg["timeframe"]
            if not state.valor_entrada:
                state.valor_entrada = cfg["valor_entrada"]
            if not state.expiracao:
                state.expiracao = cfg["expiracao"]
            state.min_velas = state.min_velas or cfg["min_velas"]
            state.ema_rapida = state.ema_rapida or cfg["ema_rapida"]
            state.ema_lenta = state.ema_lenta or cfg["ema_lenta"]
            state.micro_mult = state.micro_mult or cfg.get("micro_mult", 5)
            state.macro_mult = state.macro_mult or cfg.get("macro_mult", 15)
            if not state.stop_win:
                state.stop_win = cfg["stop_win"]
            if not state.stop_loss:
                state.stop_loss = cfg["stop_loss"]

    def _loop(self) -> None:
        try:
            cfg = load_settings()
        except Exception as exc:
            with state.lock:
                state.error = str(exc)
                state.last_message = f"Erro config: {exc}"
                state.bot_running = False
            return

        self._seed_state(cfg)

        stop_win = float(state.stop_win or cfg["stop_win"])
        stop_loss = float(state.stop_loss or cfg["stop_loss"])

        with state.lock:
            state.bot_running = True
            state.error = None
            state.stop_win = stop_win
            state.stop_loss = stop_loss
            state.started_at = datetime.now(TZ).isoformat()
            state.last_signal = None
            state.confluence = None
            state.last_message = "Conectando..."

        try:
            api, _ = connect_iq(cfg["email"], cfg["senha"], cfg["tipo_conta"])
            self._api = api
            perfil = json.loads(json.dumps(api.get_profile_ansyc()))
            with state.lock:
                state.connected = True
                state.currency = str(perfil.get("currency_char", "R$"))
                state.user_name = str(perfil.get("name", ""))
                state.balance = float(api.get_balance())
                state.last_message = "Conectado. Monitorando..."
        except Exception as exc:
            with state.lock:
                state.connected = False
                state.bot_running = False
                state.error = str(exc)
                state.last_message = f"Falha na conexao: {exc}"
            self._api = None
            return

        risk = RiskManager(stop_win, stop_loss, state.currency)
        self._risk = risk

        ultimo_sinal_ts = 0.0

        while not self._stop.is_set() and risk.can_trade:
            try:
                # configs em tempo real da UI
                ativo = (state.asset or cfg["ativo"]).upper()
                timeframe = int(state.timeframe or cfg["timeframe"])
                valor_entrada = float(state.valor_entrada or cfg["valor_entrada"])
                expiracao = int(state.expiracao or cfg["expiracao"])

                risk.update_stops(state.stop_win, state.stop_loss)

                orders = OrderManager(
                    api=api,
                    risk=risk,
                    tipo=cfg["tipo"],
                    martingale_niveis=int(state.niveis_martingale if state.usar_martingale else 0),
                    martingale_fator=float(state.fator_martingale or cfg["fator_martingale"]),
                    usar_soros=bool(state.usar_soros),
                    niveis_soros=int(state.niveis_soros or 0),
                    currency=state.currency,
                )
                strategy = get_strategy(
                    state.strategy or cfg["estrategia"],
                    api,
                    min_velas=int(state.min_velas or cfg["min_velas"]),
                    ema_rapida=int(state.ema_rapida or cfg["ema_rapida"]),
                    ema_lenta=int(state.ema_lenta or cfg["ema_lenta"]),
                    usar_filtro_ema=bool(state.usar_filtro_ema),
                    micro_mult=int(state.micro_mult or 5),
                    macro_mult=int(state.macro_mult or 15),
                    exigir_confluencia=bool(state.exigir_confluencia),
                )

                if not ensure_connected(api, cfg["email"], cfg["senha"]):
                    with state.lock:
                        state.connected = False
                        state.last_message = "Reconectando..."
                    time.sleep(3)
                    continue

                with state.lock:
                    state.connected = True
                    state.balance = float(api.get_balance())
                    state.asset = ativo

                if hasattr(strategy, "diagnose"):
                    try:
                        diag = strategy.diagnose(ativo, timeframe)
                        with state.lock:
                            state.confluence = diag
                    except Exception:
                        pass

                result = strategy.analyze(ativo, timeframe)
                now_ts = time.time()

                if result and (now_ts - ultimo_sinal_ts) > timeframe:
                    direcao, motivo = result
                    with state.lock:
                        state.last_signal = {
                            "direction": direcao.upper(),
                            "reason": motivo,
                            "asset": ativo,
                            "time": time_br(),
                            "active": True,
                        }
                        state.last_message = f"Sinal {direcao.upper()} — entrando"

                    server_now = datetime.fromtimestamp(api.get_server_timestamp())
                    espera = max(1, timeframe - server_now.second)
                    time.sleep(espera + 1)

                    if self._stop.is_set():
                        break

                    lucro_antes = risk.lucro_total
                    orders.execute(
                        ativo=ativo,
                        valor_entrada=valor_entrada,
                        direcao=direcao,
                        expiracao=expiracao,
                    )
                    resultado = risk.lucro_total - lucro_antes

                    state.add_trade(
                        {
                            "asset": ativo,
                            "direction": direcao.upper(),
                            "resultado": round(resultado, 2),
                            "status": "WIN" if resultado > 0 else ("LOSS" if resultado < 0 else "EMPATE"),
                            "strategy": state.strategy or cfg["estrategia"],
                            "time": time_br(),
                        }
                    )

                    with state.lock:
                        state.lucro_dia = risk.lucro_total
                        state.last_signal = None
                        state.last_message = "Monitorando..."
                        state.balance = float(api.get_balance())

                    ultimo_sinal_ts = time.time()
                else:
                    with state.lock:
                        if state.last_signal is None:
                            state.last_message = f"Monitorando {ativo}..."
                    time.sleep(1)

            except Exception as exc:
                with state.lock:
                    state.error = str(exc)
                    state.last_message = f"Erro: {exc}"
                time.sleep(3)

        with state.lock:
            state.bot_running = False
            state.last_signal = None
            if risk.stop_reason == "STOP_WIN":
                state.last_message = "Stop Win atingido — bot parado"
            elif risk.stop_reason == "STOP_LOSS":
                state.last_message = "Stop Loss atingido — bot parado"
            elif not state.last_message.startswith("Bot parado"):
                state.last_message = "Bot finalizado"

        self._risk = None
        self._api = None


bot_runner = BotRunner()
