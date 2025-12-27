# Prime Flow AI

Real-time institutional options flow intelligence with clear, rules-based logic. This project provides a modular foundation for streaming flow data, attaching market context, generating signals for scalps/day trades/swings, and routing formatted alerts.

## Architecture at a Glance

- **Configuration** – YAML-first loader with JSON fallback plus ticker-level overrides (`flow_bot/config.py`).
- **Domain models** – Dataclasses for flow events, signals, and paper positions (`flow_bot/models.py`).
- **Flow client abstraction** – Stubs for Polygon/Massive streaming and historical pulls (`flow_bot/flow_client.py`), with a volume screener hook to watch the top 500 symbols by share volume when providers expose that data.
- **Context engine** – Hooks for RVOL, VWAP, trend flags, and regime detection (`flow_bot/context_engine.py`).
- **Strategies** – Scalp, day-trade, and swing evaluators using shared scoring (`flow_bot/strategies/`).
- **Signal engine** – Orchestrates context + strategies to emit signals (`flow_bot/signal_engine.py`).
- **Alerts & routing** – Format human-friendly alerts and map them to channels (`flow_bot/alerts.py`, `flow_bot/routes.py`).
- **Paper trading** – Simple TP/SL/timeout tracking for signals (`flow_bot/paper_trading.py`).
- **Logging & heartbeat** – CSV logging for signals/paper trades and a lightweight status snapshot (`flow_bot/logging_utils.py`, `flow_bot/heartbeat.py`).
- **Entry points** – Live loop and replay CLI drivers (`flow_bot/main_live.py`, `flow_bot/main_replay.py`, `flow_bot/replay.py`).

## Configuration

The default `config.yaml` exposes experiment metadata, general runtime limits, market regime thresholds, per-ticker overrides, strategy thresholds, and routing channel placeholders. Update webhook URLs and thresholds there; no secrets are hardcoded.

- Load configuration with `load_config()` which defaults to `config.yaml` or accepts a custom path.
- Merge per-ticker overrides and mode configs via `get_ticker_config(global_cfg, ticker, mode)`.
- Environment secrets are centralized via `load_api_keys()` which reads `POLYGON_MASSIVE_KEY` (or legacy `POLYGON_API_KEY` / `MASSIVE_API_KEY`) from the environment for provider access. `load_config()` injects these under `config["api_keys"]` so all modules share one source of truth.

Example highlights:

- `scalp.min_premium`, `day_trade.max_dte`, `swing.min_strength` control each strategy’s gates.
- `tickers.overrides.TSLA.scalp.min_premium` demonstrates ticker-specific tuning.
- `routing.channels.*` holds webhook placeholders for Telegram/Discord/etc.

## Core Data Flow

1. **Ingest** – `FlowClient` (stub) will stream live flow or fetch historical slices.
2. **Context** – `ContextEngine` attaches VWAP/trend/RVOL and market regime metadata per event.
3. **Strategies** – Each event is passed to `ScalpMomentumStrategy`, `DayTrendStrategy`, and `SwingAccumulationStrategy`, which apply rule filters and scoring.
4. **Signals** – Valid strategies emit `Signal` objects containing tags, rules triggered, and context.
5. **Alerting** – `routes.route_signal` picks alert mode/channel; `alerts.format_*` builds human-readable text; `routes.send_alert` is stubbed to POST/print (add real webhooks).
6. **Paper Trading & Logging** – `PaperTradingEngine` opens/updates paper positions; `SignalLogger` (and TODO paper-trade logger) append CSV rows; `Heartbeat` summarizes throughput.

### Universe selection (top-volume focus)

- `FlowClient.get_top_volume_tickers(limit=500)` is the intended entry point for pulling a fresh list of the highest-volume equities from Polygon/Massive screeners. Live and historical clients can use this to define the scanning universe without maintaining manual ticker lists. The stub currently returns an empty list until credentials/API integration are added.

## Running the Bot

### Live Mode

`flow_bot/main_live.py` wires together the flow client, signal engine, logging, alert routing, paper trading, and heartbeat loop. Replace `FlowClient.stream_live_flow()` and `routes.send_alert()` with real integrations, then run:

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

- **ScalpMomentumStrategy** – Fast setups: DTE ≤ `scalp.max_dte`, notional ≥ `scalp.min_premium`, near-the-money strikes, RVOL and VWAP/trend alignment, sweeps/aggression favored, volume vs OI freshness checks.
- **DayTrendStrategy** – Holds intraday trend breaks: allows longer DTE, looks for sweeps in clusters, 15m trend confirmation, level breaks, and relative volume gates.
- **SwingAccumulationStrategy** – Larger, slower plays: DTE within swing window, premium/OTM guards, repeated buying memory, daily trend alignment, higher strength threshold.

All three share `score_signal` for consistent tags such as SIZE, SWEEP, AGGRESSIVE, VOL>OI, TREND_CONFIRMED.

## Alerts & Routing

`alerts.py` formats signals into short/medium/deep-dive variants; `choose_alert_mode` aligns style with signal kind. `routes.route_signal` maps SCALP→`telegram_scalps`, SWING→`telegram_swings`, default→`telegram_main`. `routes.send_alert` currently prints or can POST to webhook URLs from config (add your credentials and HTTP client of choice).

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

## Sample Alert Outputs

Below are example alerts using the current sectioned formatting (flow, structure, intent, rationale, risk, regime, timestamp) with MM-DD-YYYY expiries and 12-hour ET times.

**Scalp (short)**
```
⚡ SCALP CALL – TSLA (Strength 7.9/10)
1000x @ $1.85 | Strike 245 exp 02-21-2025 | Notional $185,000 | Vol/OI 5000/2200 | SWEEP, AGGRESSIVE

Flow Intent (intraday): aggressive CALL flow; size looks like new money; tags: SWEEP, AGGRESSIVE, VOL>OI.
Price / Microstructure:
  Underlying $243.40 | OTM 0.8% | DTE 1 | Above VWAP
  Microstructure: pushing off VWAP; trend 1m/5m aligned; level pressure=yes.

Why this matters:
  sweep/aggression + VWAP/momentum alignment suggest tape control; favors a fast upside continuation instead of noise.

Risk & timing:
  invalidate on VWAP or trigger loss; suited for a 5–20 min scalp with tight stops.

Regime: trend=UP vol=HIGH
Time: 10:12:34 AM ET
```

**Day Trade (medium)**
```
📈 DAY TRADE PUT – AMD (Strength 8.3/10)
500x @ $2.40 | Strike 135 exp 03-14-2025 | Notional $120,000 | Vol/OI 12000/4500 | AGGRESSIVE

Flow Intent (session): assertive participation pressing the theme; vol vs OI 12000/4500; tags: AGGRESSIVE, VOL>OI, LEVEL_BREAK.
Price / Structure:
  Underlying $138.20 | OTM 1.3% | DTE 12 | Below VWAP | RVOL 1.8
  VWAP/EMA: overhead/drag; 15m trend uncertain; key level=break/hold; RVOL=1.8.

Why this is a good day-trade alert:
  flow + intraday structure and regime point to sellers control; timing favors continuation movement rather than random noise.

Risk & execution:
  invalidate on VWAP/15m trend break or failed level retest; intraday idea (approx. 30–180 minutes if structure holds).

Regime: trend=DOWN vol=ELEVATED
Time: 11:05:12 AM ET
```

**Swing (deep dive)**
```
🧠 SWING CALL – META (Strength 9.2/10)
750x @ $9.40 | Strike 400 exp 04-18-2025 | Notional $6,300,000 | Vol/OI 20000/8000 | AGGRESSIVE, PERSISTENT_BUYER

Flow Intent (swing): persistent flow; DTE/OTM consistent with positioning; tags: AGGRESSIVE, PERSISTENT_BUYER; Cluster notional ≈ $6,300,000.
Price / Structure (HTF):
  Underlying $384.20 | OTM 4.1% | DTE 35 | Above VWAP | RVOL 1.2
  HTF posture: daily trend aligned; structure breakout/pullback; level posture=supportive; RVOL=1.2.

Why this is a good swing alert:
  size + repetition at HTF structure implies institutional participation; aligns with the prevailing trend in current regime and supports an accumulation thesis rather than short-term noise.

Risk & plan:
  invalidate on break of recent swing pivot/HTF level; holding window on the order of days to weeks; informational context, not advice.

Regime: trend=UP vol=MEDIUM
Time: 01:18:45 PM ET
```

## Sample Alert Outputs (current format)

**Scalp (short)**
```
⚡ SCALP CALL – TSLA (Strength 7.9/10)
1000x @ $1.85 | Strike 245 exp 02-21-2025 | Notional $185,000 | Vol/OI 5000/2200 | SWEEP, AGGRESSIVE

Flow Intent (intraday): aggressive CALL flow; size looks like new money; tags: SWEEP, AGGRESSIVE, VOL>OI.
Price / Microstructure:
  Underlying $243.40 | OTM 0.8% | DTE 1 | Above VWAP
  Microstructure: pushing off VWAP; trend 1m/5m aligned; level pressure=yes.

Why this matters:
  sweep/aggression + VWAP/momentum alignment suggest tape control; favors a fast upside continuation instead of noise.

Risk & timing:
  invalidate on VWAP or trigger loss; suited for a 5–20 min scalp with tight stops.

Regime: trend=UP vol=HIGH
Time: 10:12:34 AM ET
```

**Day Trade (medium)**
```
📈 DAY TRADE PUT – AMD (Strength 8.3/10)
500x @ $2.40 | Strike 135 exp 03-14-2025 | Notional $120,000 | Vol/OI 12000/4500 | AGGRESSIVE

Flow Intent (session): assertive participation pressing the theme; vol vs OI 12000/4500; tags: AGGRESSIVE, VOL>OI, LEVEL_BREAK.
Price / Structure:
  Underlying $138.20 | OTM 1.3% | DTE 12 | Below VWAP | RVOL 1.8
  VWAP/EMA: overhead/drag; 15m trend uncertain; key level=break/hold; RVOL=1.8.

Why this is a good day-trade alert:
  flow + intraday structure and regime point to sellers control; timing favors continuation movement rather than random noise.

Risk & execution:
  invalidate on VWAP/15m trend break or failed level retest; intraday idea (approx. 30–180 minutes if structure holds).

Regime: trend=DOWN vol=ELEVATED
Time: 11:05:12 AM ET
```

**Swing (deep dive)**
```
🧠 SWING CALL – META (Strength 9.2/10)
750x @ $9.40 | Strike 400 exp 04-18-2025 | Notional $6,300,000 | Vol/OI 20000/8000 | AGGRESSIVE, PERSISTENT_BUYER

Flow Intent (swing): persistent flow; DTE/OTM consistent with positioning; tags: AGGRESSIVE, PERSISTENT_BUYER; Cluster notional ≈ $6,300,000.
Price / Structure (HTF):
  Underlying $384.20 | OTM 4.1% | DTE 35 | Above VWAP | RVOL 1.2
  HTF posture: daily trend aligned; structure breakout/pullback; level posture=supportive; RVOL=1.2.

Why this is a good swing alert:
  size + repetition at HTF structure implies institutional participation; aligns with the prevailing trend in current regime and supports an accumulation thesis rather than short-term noise.

Risk & plan:
  invalidate on break of recent swing pivot/HTF level; holding window on the order of days to weeks; informational context, not advice.

Regime: trend=UP vol=MEDIUM
Time: 01:18:45 PM ET
```
