# IQ Option System — Multi Estratégias

Sistema modular para IQ Option com:
- Martingale
- Soros
- Stop Win / Stop Loss
- Estratégia inicial: **Escadinha**
- Configuração por **environment variables** (Dokploy)

Base de API: repositório [lukefeix/Rob-de-MHI-para-IQoption-Aulas-Completas](https://github.com/lukefeix/Rob-de-MHI-para-IQoption-Aulas-Completas)

## Aviso

- API **não oficial**. Risco de bloqueio de conta.
- Use **somente PRACTICE/DEMO** no início.
- Opções binárias têm alto risco de perda.

## Estrutura

```
iqoption-system/
├── iqoptionapi/
├── strategies/
│   ├── base.py
│   └── escadinha.py
├── core/
│   ├── connection.py
│   ├── order.py
│   ├── risk.py
│   └── settings.py      # ENV (Dokploy) + fallback config.txt
├── config.txt           # fallback local
├── .env.example
├── Dockerfile
├── main.py
└── requirements.txt
```

## Configuração no Dokploy

Defina estas variáveis de ambiente:

```env
IQ_EMAIL=seu_email@exemplo.com
IQ_PASSWORD=sua_senha
IQ_ACCOUNT=PRACTICE

IQ_ORDER_TYPE=binarias
IQ_ENTRY_AMOUNT=2
IQ_EXPIRATION=1
IQ_STOP_WIN=50
IQ_STOP_LOSS=30

IQ_MARTINGALE=true
IQ_MARTINGALE_LEVELS=2
IQ_MARTINGALE_FACTOR=2.0

IQ_SOROS=true
IQ_SOROS_LEVELS=2

IQ_STRATEGY=escadinha
IQ_ASSET=EURUSD-OTC
IQ_TIMEFRAME=60

IQ_MIN_CANDLES=3
IQ_EMA_FAST=9
IQ_EMA_SLOW=21
IQ_EMA_FILTER=true
```

## Executar local

```bash
pip install -r requirements.txt
python main.py
```

## Docker / Dokploy

```bash
docker build -t iqoption-system .
docker run --env-file .env iqoption-system
```

## Estratégia Escadinha

1. Detecta N velas consecutivas da mesma cor
2. Confirma tendência com EMA (opcional)
3. Aguarda fechamento da vela
4. Entra na próxima janela (mais seguro para Soros)

## Adicionar nova estratégia

1. Crie `strategies/nova.py` herdando de `BaseStrategy`
2. Implemente `analyze(ativo, timeframe)`
3. Registre em `strategies/__init__.py`
4. Selecione com `IQ_STRATEGY=nova`
