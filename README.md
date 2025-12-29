# Prime Flow AI

Prime Flow AI is a rules-based, real-time institutional options flow intelligence engine. It ingests live or historical flow, enriches events with market context, evaluates configurable scalp/day/swing strategies, and produces high-quality alerts suitable for Telegram/webhooks. Secrets (API keys, webhooks) are expected from environment variables.

## Architecture at a Glance

- **Configuration** – YAML-first loader with JSON fallback and ticker-level overrides (`flow_bot/config.py`).
- **Domain models** – Dataclasses for flow events, signals, and paper positions (`flow_bot/models.py`).
- **Flow client abstraction** – Stubs for Polygon/Massive streaming and historical pulls (`flow_bot/flow_client.py`), including a hook to watch the top 500 symbols by share volume when providers expose screeners.
- **Context engine** – Hooks for RVOL, VWAP, trend flags, and regime detection (`flow_bot/context_engine.py`).
- **Strategies** – Scalp, day-trade, and swing evaluators using shared scoring (`flow_bot/strategies/`).
- **Signal engine** – Orchestrates context + strategies to emit signals (`flow_bot/signal_engine.py`).
- **Alerts & routing** – Format human-friendly alerts and map them to channels (`flow_bot/alerts.py`, `flow_bot/routes.py`).
- **Paper trading** – Simple TP/SL/timeout tracking for signals (`flow_bot/paper_trading.py`).
- **Logging & heartbeat** – CSV logging for signals/paper trades and a lightweight status snapshot (`flow_bot/logging_utils.py`, `flow_bot/heartbeat.py`).
- **Entry points** – Live loop and replay CLI drivers (`flow_bot/main_live.py`, `flow_bot/main_replay.py`, `flow_bot/replay.py`).

## Configuration

The default `config.yaml` covers experiment metadata, runtime limits, market regime thresholds, per-ticker overrides, strategy thresholds, and routing channel mappings. Telegram chat IDs and bot tokens are pulled from environment variables; no secrets are hardcoded.

- Load configuration with `load_config()` (defaults to `config.yaml`, or pass a custom path).
- Merge per-ticker overrides and mode configs via `get_ticker_config(global_cfg, ticker, mode)`.
- Environment secrets are centralized via `load_api_keys()`, reading `POLYGON_MASSIVE_KEY` (or legacy `POLYGON_API_KEY` / `MASSIVE_API_KEY`). `load_config()` injects keys under `config["api_keys"]` so every module uses one source of truth.

### Environment variables

Set these before running live or replay modes:

- `POLYGON_MASSIVE_KEY` (preferred) or `POLYGON_API_KEY` / `MASSIVE_API_KEY` — provider credentials for Polygon/Massive data.
- `TELEGRAM_BOT_TOKEN` — Telegram Bot API token used for all alerts.
- `TELEGRAM_CHAT_ID_ALERTS` — the single Telegram chat ID that receives every alert (scalps/day-trades/swings/main).

Example highlights:

- `scalp.min_notional`, `day_trade.max_dte`, `swing.min_strength` control each strategy’s gates.
- `tickers.overrides.*` can override per-ticker thresholds when enabled.
- `routing.channels.*` maps logical channels (scalps/swings/main) to the `TELEGRAM_CHAT_ID_ALERTS` environment variable so every alert lands in the same chat.

## Core Data Flow

1. **Ingest** – `FlowClient` (stub) will stream live flow or fetch historical slices.
2. **Context** – `ContextEngine` attaches VWAP/trend/RVOL and market regime metadata per event.
3. **Strategies** – Each event is passed to `ScalpMomentumStrategy`, `DayTrendStrategy`, and `SwingAccumulationStrategy`, which apply rule filters and scoring.
4. **Signals** – Valid strategies emit `Signal` objects containing tags, rules triggered, and context.
5. **Alerting** – `routes.route_signal` picks alert mode/channel; `alerts.format_*` builds human-readable text; `routes.send_alert` forwards through the Telegram Bot API using `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID_ALERTS`.
6. **Paper Trading & Logging** – `PaperTradingEngine` opens/updates paper positions; `SignalLogger` (and TODO paper-trade logger) append CSV rows; `Heartbeat` summarizes throughput.

### Universe selection (top-volume focus)

`FlowClient.get_top_volume_tickers(limit=500)` is the intended entry point for pulling a fresh list of the highest-volume equities from Polygon/Massive screeners. Live and historical clients can use this to define the scanning universe without maintaining manual ticker lists. The stub currently returns an empty list until credentials/API integration are added.

## Running the Bot

### Live Mode

`flow_bot/main_live.py` wires together the flow client, signal engine, logging, alert routing, paper trading, and heartbeat loop. Provide `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID_ALERTS` env vars, replace `FlowClient.stream_live_flow()` with a real provider, then run:

```bash
python -m flow_bot.main_live
```

### Replay / Backtest Mode

`flow_bot/replay.py` and `flow_bot/main_replay.py` fetch historical flow (stubbed) and re-run strategy logic chronologically for backtesting or research:

```bash
python -m flow_bot.main_replay
```

Adjust `start`/`end` placeholders or extend with CLI args and real historical queries.

## Strategies Overview

- **ScalpMomentumStrategy** – Fast setups: DTE ≤ `scalp.max_dte`, notional ≥ `scalp.min_notional`, near-the-money strikes, RVOL and VWAP/trend alignment, sweeps/aggression favored, volume vs OI freshness checks.
- **DayTrendStrategy** – Holds intraday trend breaks: allows longer DTE, looks for sweeps in clusters, 15m trend confirmation, level breaks, and relative volume gates.
- **SwingAccumulationStrategy** – Larger, slower plays: DTE within swing window, premium/OTM guards, repeated buying memory, daily trend alignment, higher strength threshold.

All three share `score_signal` for consistent tags such as SIZE, SWEEP, AGGRESSIVE, VOL>OI, TREND_CONFIRMED.

## Alerts & Routing

`alerts.py` formats signals into short/medium/deep-dive variants; `choose_alert_mode` aligns style with signal kind. `routes.route_signal` maps SCALP → `telegram_scalps`, SWING → `telegram_swings`, default → `telegram_main`. `routes.send_alert` currently prints or can POST to webhook URLs from config (add your credentials and HTTP client of choice).

## Paper Trading

`PaperTradingEngine` opens positions per signal kind with default TP/SL/timeouts (e.g., ~2%/-1%/30m for scalps, wider for swings). Call `update_positions` with latest prices to close TP/SL/TIMEOUT outcomes and track exits.

## Logging & Monitoring

- `SignalLogger` writes CSV rows with timestamps, tickers, strength, tags, and experiment IDs.
- (TODO) Add a paper-trade logger alongside it.
- `Heartbeat` produces a status string with events/min and signal counts; send it to a chat channel or logs on an interval.

## Extending / Next Steps

- Implement real Polygon/Massive clients for streaming, historical fetches, and price lookups.
- Wire `routes.send_alert` to Telegram/Discord/Slack via webhooks.
- Expand context calculations (VWAP, MA trends, RVOL) using market data providers.
- Add CLI args/env vars for start/end dates in replay mode and live provider selection.
- Harden unit tests around strategy gates, scoring, and paper trade outcomes.

## Repository Layout

```
flow_bot/
  config.py          # Config loader and per-ticker merge helper
  models.py          # Dataclasses: FlowEvent, Signal, PaperPosition
  flow_client.py     # Provider abstraction (stubs for Polygon/Massive)
  context_engine.py  # VWAP/trend/RVOL/context hooks
  strategies/        # Strategy base + scalp/day/swing implementations
  scoring.py         # Shared scoring logic and tags
  signal_engine.py   # Runs context + strategies per event
  alerts.py          # Alert formatting helpers
  routes.py          # Alert routing + send stub
  logging_utils.py   # CSV loggers
  paper_trading.py   # Paper trading engine
  heartbeat.py       # Status snapshot helper
  main_live.py       # Live streaming entrypoint
  replay.py          # Historical replay driver
  main_replay.py     # Replay CLI wrapper
config.yaml          # Default thresholds, tickers, routing placeholders
```

## Sample Alert Outputs (sectioned format)

Below are example alerts using the current sectioned formatting with MM-DD-YYYY expiries and 12-hour ET timestamps.

### Scalp (short)

```
⚡ SCALP CALL – TSLA
Strength: 7.9 / 10

### 📊 FLOW SUMMARY (what happened)
1000 contracts @ $1.85
Strike 245C | Exp 02-21-2025
Notional $185,000
Volume / OI: 5000 / 2200
Flow Character: SWEEP, AGGRESSIVE

---
### 🎯 FLOW INTENT (intraday)
Aggressive call buying with meaningful size that appears to be new positioning rather than noise.

---
### 📈 PRICE & MICROSTRUCTURE
- Underlying: $243.40
- OTM: 0.8%
- DTE: 1
- VWAP: Above
- Microstructure:
  - pushing off VWAP
  - 1m + 5m trends aligned
  - pressure at key level = YES

---
### ✅ WHY THIS MATTERS
Aggression + sweep behavior combined with VWAP alignment suggests strong tape control and favors fast continuation rather than chop.

---
### ⚠️ RISK & TIMING
Loses edge if VWAP breaks or trigger level fails.
Best suited for 5–20 minute intraday scalp.

---
### 🌡️ REGIME
Trend: UP
Volatility: HIGH

---
### ⏰ TIME
10:12:34 AM ET
```

### Day Trade (medium)

```
📉 DAY TRADE PUT – AMD
Strength: 8.3 / 10

### 📊 FLOW SUMMARY
500 contracts @ $2.40
Strike 135P | Exp 03-14-2025
Notional $120,000
Volume / OI: 12000 / 4500
Flow Character: AGGRESSIVE

---
### 🎯 FLOW INTENT (session)
Assertive selling participation pressing the downside theme with strong volume expansion vs open interest.

---
### 📈 PRICE & STRUCTURE
- Underlying: $138.20
- OTM: 1.3%
- DTE: 12
- VWAP: Below
- RVOL: 1.8
- Structure:
  - VWAP + EMA overhead
  - 15m trend uncertain
  - price interacting with key break level

---
### ✅ WHY THIS IS A GOOD DAY-TRADE ALERT
Flow, structure, and market regime indicate sellers currently control the narrative, increasing probability of continuation rather than random, one-off selling.

---
### ⚠️ RISK & EXECUTION
Invalid if price reclaims VWAP, breaks the 15m trend upward, or fails to hold the level retest.
Intended timeframe: 30–180 minutes assuming structure remains valid.

---
### 🌡️ REGIME
Trend: DOWN
Volatility: ELEVATED

---
### ⏰ TIME
11:05:12 AM ET
```

### Swing (deep dive)

```
🧠 SWING CALL – META
Strength: 9.2 / 10

### 📊 FLOW SUMMARY
750 contracts @ $9.40
Strike 400C | Exp 04-18-2025
Total Notional: $6,300,000
Volume / OI: 20000 / 8000
Flow Character: AGGRESSIVE, PERSISTENT BUYER

---
### 🎯 FLOW INTENT (swing)
Persistent upside call accumulation with maturity and distance consistent with deliberate swing positioning rather than short-term speculation.

---
### 📈 PRICE & HTF STRUCTURE
- Underlying: $384.20
- OTM: 4.1%
- DTE: 35
- VWAP: Above
- RVOL: 1.2
- High Timeframe Posture:
  - daily trend aligned
  - breakout → pullback behavior
  - key levels supportive

---
### ✅ WHY THIS IS A GOOD SWING ALERT
Size, repetition, and location within the broader structure strongly imply institutional participation. Alignment with the prevailing trend makes the accumulation thesis much stronger than random flow.

---
### ⚠️ RISK & PLAN
Invalid on break of recent swing pivot or failure of high timeframe structure.
Intended holding window: days to weeks. Informational context only, not financial advice.

---
### 🌡️ REGIME
Trend: UP
Volatility: MEDIUM

---
### ⏰ TIME
01:18:45 PM ET
```
