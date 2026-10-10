# GROK BOT — Django Paper Trading

Dark glassmorphic dashboard and backend for **short-term scalp decisions** with a **Jev (TypeSafe) fast gate** and **xAI Grok** confirmation. Runs in **PAPER mode** by default: simulated balances, fees, slippage, and fills at scanned market prices.

## Features

- **Scanner**: DexScreener (boosts, profiles, search/pairs) + GeckoTerminal trending pools, with liquidity/volume/ratio/age/FDV filters and basic rug checks (GoPlus, RugCheck.xyz on Solana).
- **Decision pipeline**: Per candidate — indicators + safety → **Jev** (`TYPESAFE_API_KEY`, [Jev API](https://jevtypesafeai.com/jev/api)) → high-confidence buys only → **Grok** (`XAI_API_KEY`) → trade only when both agree (in `jev+grok` mode) → risk guard → paper fill. Jev also runs **exit checks** on open positions. Modes: `jev+grok`, `grok-only`, `jev-only`, `mock`.
- **Agents**: Named strategies (ODEN, VIRA, KESH, …) with per-agent start/stop; Celery ticks drive the pipeline (mock rules when API keys are missing).
- **Risk guard**: Max position %, open positions, daily loss kill switch, trades/hour, mandatory SL/TP, min confidence, price sanity — rejections logged.
- **Paper engine**: Starting balance, add/reset funds, SL/TP/timeout exits; exchange adapter interface with live stub disabled.
- **Dashboard**: Balance, net P&L after fees, win-rate vs target (default 50/60 ≈ 83%), fees, balance chart, token status + activity log (Jev/Grok lines with confidence + latency), daily target bar, agent cards, positions/executions/trades, kill switch, 4s polling.

## Quick start (local)

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py bootstrap
python manage.py runserver 0.0.0.0:8000
```

`bootstrap` runs migrations, **validates all trading config** (fails fast with clear errors), and seeds demo data.

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

**Timed paper session** (scanner + agents + summary; not run automatically):

```bash
python manage.py run_paper_session --minutes 10 --interval 20
```

Prints trades, win rate vs target, P&L, fees, and per-model decision counts/latency. Does **not** call live providers beyond normal scanner/agent ticks.

## Settings

All tunables live in `.env` (defaults) and can be overridden on the dashboard **Settings** panel (saved to `AppSettings.config` in the database). Provider status is shown in the **Provider health** panel (`GET /api/health/`).

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Services: `web` (8000), `worker`, `beat`, `redis`, `postgres`. Leave `DATABASE_URL` empty in `.env` to use SQLite inside the container only if you override compose env.

## Environment

| Variable | Description |
|----------|-------------|
| `TYPESAFE_API_KEY` | Jev gate; `jv_live_*` → `jevtypesafeai.com/api/v1/decide`, else `api.typesafe.ai/v1/systemone` |
| `JEV_MODEL` | Pin model e.g. `jev-1.13.0` |
| `DECIDER_MODE` | `jev+grok`, `grok-only`, `jev-only`, or `mock` |
| `JEV_BUY_CONFIDENCE_THRESHOLD` | Min Jev buy confidence (default 0.72) |
| `XAI_API_KEY` | xAI Grok key for second-stage sizing/SL/TP |
| `XAI_BASE_URL` | Default `https://api.x.ai/v1` |
| `XAI_MODEL` | e.g. `grok-3-mini` |
| `GROK_MIN_CONFIDENCE` | Min Grok confidence (default 0.65) |
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
- `trading/` — models, services (scanner, jev, grok, pipeline, risk, paper), tasks, views
- `templates/` + `static/` — GROK BOT UI
- `tests/` — risk guard, paper engine, Jev endpoint, decision pipeline

## Live trading

Not enabled. `trading.services.exchange.live_stub.LiveExchangeAdapter` is a placeholder; keep `PAPER_MODE=1` until a audited live adapter is implemented.
