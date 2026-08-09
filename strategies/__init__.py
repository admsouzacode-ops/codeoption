from .base import BaseStrategy
from .escadinha import EscadinhaStrategy

STRATEGY_REGISTRY = {
    "escadinha": EscadinhaStrategy,
}


def get_strategy(name: str, api, **kwargs):
    key = (name or "").strip().lower()
    if key not in STRATEGY_REGISTRY:
        available = ", ".join(sorted(STRATEGY_REGISTRY.keys()))
        raise ValueError(f"Estrategia '{name}' nao encontrada. Disponiveis: {available}")
    return STRATEGY_REGISTRY[key](api, **kwargs)


__all__ = ["BaseStrategy", "EscadinhaStrategy", "STRATEGY_REGISTRY", "get_strategy"]
