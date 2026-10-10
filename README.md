# GROK BOT — Django Paper Trading

Dark glassmorphic dashboard and backend for **short-term scalp decisions** powered by **xAI Grok** (OpenAI-compatible API). Runs in **PAPER mode** by default: simulated balances, fees, slippage, and fills at scanned market prices.

## Features

- **Scanner**: DexScreener (boosts, profiles, search/pairs) + GeckoTerminal trending pools, with liquidity/volume/ratio/age/FDV filters and basic rug checks (GoPlus, RugCheck.xyz on Solana).
- **Agents**: Named strategies (ODEN, VIRA, KESH, …) with per-agent start/stop; Celery worker ticks call Grok (or rule-based mock when `XAI_API_KEY` is unset).
- **Risk guard**: Max position %, open positions, daily loss kill switch, trades/hour, mandatory SL/TP, min confidence, price sanity — rejections logged.
- **Paper engine**: Starting balance, add/reset funds, SL/TP/timeout exits; exchange adapter interface with live stub disabled.
- **Dashboard**: Balance, P&L, win-rate ring, fees, balance chart, token status + activity log, daily target bar, agent cards, positions/executions/trades, kill switch, 4s polling.

## Quick start (local)

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
```

Open http://localhost:8000

### Background workers

**With Celery + Redis** (recommended for Docker):

```bash
celery -A grokbot worker -l info
celery -A grokbot beat -l info
```

**Without Celery** (dev loop):

```bash
python manage.py run_agent_loop --interval 30
```

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Services: `web` (8000), `worker`, `beat`, `redis`, `postgres`. Leave `DATABASE_URL` empty in `.env` to use SQLite inside the container only if you override compose env.

## Environment

| Variable | Description |
|----------|-------------|
| `XAI_API_KEY` | xAI API key; omit to use mock decider |
| `XAI_BASE_URL` | Default `https://api.x.ai/v1` |
| `XAI_MODEL` | e.g. `grok-3-mini` |
| `PAPER_STARTING_BALANCE` | Initial dummy USD |
| `SCAN_MIN_LIQUIDITY_USD` | Scanner LP floor (default 50k) |
| `RISK_*` | Risk guard thresholds |

See `.env.example` for the full list.

## API

- `GET /api/dashboard/` — dashboard JSON
- `POST /api/agents/<id>/start/` | `/stop/`
- `POST /api/kill-switch/` — body `{"enabled": true}`
- `POST /api/paper/reset/` — body `{"amount": 1000}`
- `POST /api/paper/add-funds/` — body `{"amount": 100}`
- `POST /api/scan/` — trigger scan

## Tests

```bash
python manage.py test tests
```

## Project layout

- `grokbot/` — Django project + Celery
- `trading/` — models, services (scanner, grok, risk, paper), tasks, views
- `templates/` + `static/` — GROK BOT UI
- `tests/` — risk guard & paper engine

## Live trading

Not enabled. `trading.services.exchange.live_stub.LiveExchangeAdapter` is a placeholder; keep `PAPER_MODE=1` until a audited live adapter is implemented.
