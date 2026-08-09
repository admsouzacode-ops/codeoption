"""Module for IQ option websocket training_balance_reset."""


def training_balance_reset(api, message):
    if message["name"] == "training_balance_reset":
        # Evento da conta demo; precisa existir para o import da API.
        api.training_balance_reset_raw = message
