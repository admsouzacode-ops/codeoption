# Deploy no Dokploy (sem senha no GitHub)

## 1. Tipo de aplicacao

Crie um servico do tipo **Application** (Docker) apontando para este repositorio.

- Build: Dockerfile
- O processo fica rodando em loop (`python main.py`)
- Nao e um site HTTP: se o Dokploy exigir healthcheck HTTP, desative ou use um check generico de processo

## 2. Environment Variables (obrigatorio)

Coloque **somente no painel do Dokploy** (nunca no GitHub):

```env
IQ_EMAIL=seu_email_real@exemplo.com
IQ_PASSWORD=sua_senha_real

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

## 3. Importante

- Use `IQ_ACCOUNT=PRACTICE` no inicio
- Nao coloque email/senha no `config.txt` do repositorio (esta publico)
- O codigo le primeiro as variaveis de ambiente; `config.txt` e so fallback local

## 4. Se o deploy falhar

Verifique nos logs:

1. `IQ_EMAIL` / `IQ_PASSWORD` definidos?
2. Build do Docker concluiu?
3. Container reiniciando em loop? (credencial errada ou API offline)
4. Healthcheck HTTP ativo em app que nao expoe porta? -> desative o healthcheck

## 5. Logs esperados no sucesso

```
Conectado | Conta: PRACTICE | Saldo: ...
Monitorando EURUSD-OTC | estrategia=escadinha ...
```
