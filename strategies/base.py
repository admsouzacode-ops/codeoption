"""Interface base para estrategias."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BaseStrategy(ABC):
    name: str = "base"

    def __init__(self, api, **kwargs):
        self.api = api
        self.kwargs = kwargs

    @abstractmethod
    def analyze(self, ativo: str, timeframe: int = 60) -> Optional[Tuple[str, str]]:
        """
        Analisa o mercado e retorna sinal.

        Returns:
            (direcao, motivo) onde direcao e 'call' ou 'put'.
            None se nao houver entrada.
        """
        raise NotImplementedError

    def wait_entry_window(self) -> bool:
        """Hook opcional para estrategias baseadas em horario (ex: MHI)."""
        return True
