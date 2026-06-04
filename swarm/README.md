# Deriv Trading Dashboard — Swarm

A 15-agent backtesting swarm that runs grid searches across all configured instruments and writes structured results to `swarm_out/`.

## Files

| File | Purpose |
|---|---|
| `engine.py` | Unified backtesting engine. Fetches OHLCV data from Deriv WebSocket (synthetic indices) or yfinance (market instruments), runs three strategy families (EMA crossover, RSI mean-reversion, MACD momentum) over an ATR-based stop-loss/take-profit grid, and ranks every parameter combination by a single quality score. |
| `instruments.py` | Catalog of all instruments (Deriv synthetic indices and Yahoo Finance tickers) grouped into named work units consumed by the runner. |
| `run_instrument.py` | Entry point for a single work unit. Loads the instruments in that unit, calls the engine grid search, and writes `swarm_out/<work-unit-id>.json`. Usage: `python3 swarm/run_instrument.py <work-unit-id>`. |
| `swarm_runner.py` | Orchestrates the full swarm. Phase A spawns 10 headless `claude -p` workers (one per work unit) to run backtests concurrently. Phase B spawns 5 upgrade agents that consume Phase A JSON output and apply improvements to the project. Concurrency is capped to avoid rate-limiting data providers. |

## Re-running the swarm

```bash
python3 swarm/swarm_runner.py
```

All output lands in `swarm_out/`: JSON result files per work unit, Markdown summaries, and worker logs under `swarm_out/logs/`.

---

**Risk Disclaimer:** This project is for educational and research purposes only. All backtests use historical data, and past performance is not indicative of future results. The strategies and signals produced by this software do not constitute financial advice and should never be used to trade real money without independent professional evaluation. Always run in demo/paper-trading mode first and ensure you fully understand any strategy before risking capital.
