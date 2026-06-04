"""
Unified backtesting engine for the Deriv Trading Dashboard swarm.

One engine, two data sources (Deriv synthetic indices over WebSocket and
market instruments over yfinance), three strategy families (EMA crossover,
RSI mean-reversion, MACD momentum), ATR-based stop-loss / take-profit, and a
grid search that ranks every parameter combination by a single quality score.

The engine is deterministic: same data plus same grid yields the same ranking.
"""

import asyncio
import json
import numpy as np
import pandas as pd
import yfinance as yf
import websockets


DERIV_WS = "wss://ws.derivws.com/websockets/v3?app_id=1089"

DERIV_GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}


class DataUnavailable(Exception):
    """Raised when an instrument's history cannot be fetched."""


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

async def _fetch_deriv(symbol, granularity, batches):
    candles = []
    end_time = None
    for _ in range(batches):
        async with websockets.connect(DERIV_WS) as ws:
            request = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 5000,
                "end": "latest" if end_time is None else str(end_time),
                "granularity": granularity,
                "style": "candles",
            }
            await ws.send(json.dumps(request))
            response = json.loads(await ws.recv())
            if "error" in response:
                raise DataUnavailable(response["error"]["message"])
            batch = response.get("candles", [])
            if not batch:
                break
            candles = batch + candles
            end_time = batch[0]["epoch"] - 1
    if not candles:
        raise DataUnavailable(f"no candles for {symbol}")
    frame = pd.DataFrame(candles)
    frame = frame.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    frame["Volume"] = 1.0
    return frame[["Open", "High", "Low", "Close", "Volume"]].reset_index(drop=True)


def fetch_deriv(symbol, timeframe="1h", batches=2):
    granularity = DERIV_GRANULARITY[timeframe]
    return asyncio.run(_fetch_deriv(symbol, granularity, batches))


def fetch_yahoo(symbol, period="2y", interval="1d"):
    frame = yf.Ticker(symbol).history(period=period, interval=interval)
    frame = frame.dropna()
    if frame.empty:
        raise DataUnavailable(f"empty history for {symbol}")
    return frame[["Open", "High", "Low", "Close", "Volume"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

def ema(series, window):
    return series.ewm(span=window, adjust=False).mean()


def rsi(series, window=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    strength = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + strength))


def macd(series, fast=12, slow=26, signal=9):
    line = ema(series, fast) - ema(series, slow)
    signal_line = line.ewm(span=signal, adjust=False).mean()
    return line, signal_line


def average_true_range(frame, window=14):
    prev_close = frame["Close"].shift(1)
    true_range = pd.concat([
        frame["High"] - frame["Low"],
        (frame["High"] - prev_close).abs(),
        (frame["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return true_range.rolling(window).mean()


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------

def ema_cross_signals(frame, fast, slow):
    fast_line = ema(frame["Close"], fast)
    slow_line = ema(frame["Close"], slow)
    above = fast_line > slow_line
    longs = above & ~above.shift(1, fill_value=False)
    shorts = ~above & above.shift(1, fill_value=False)
    return longs, shorts


def rsi_reversion_signals(frame, period, oversold, overbought):
    values = rsi(frame["Close"], period)
    crossed_up = (values > oversold) & (values.shift(1) <= oversold)
    crossed_down = (values < overbought) & (values.shift(1) >= overbought)
    return crossed_up, crossed_down


def macd_signals(frame):
    line, signal_line = macd(frame["Close"])
    above = line > signal_line
    longs = above & ~above.shift(1, fill_value=False)
    shorts = ~above & above.shift(1, fill_value=False)
    return longs, shorts


# ---------------------------------------------------------------------------
# Trade simulation
# ---------------------------------------------------------------------------

def simulate(frame, longs, shorts, sl_mult, tp_mult, cost=0.0):
    """Return per-trade fractional returns, net of a round-trip `cost`
    (fraction of entry price) charged on every trade for spread + slippage."""
    atr = average_true_range(frame)
    high, low, close = frame["High"].values, frame["Low"].values, frame["Close"].values
    longs, shorts, atr = longs.values, shorts.values, atr.values
    returns = []
    open_trade = None
    for i in range(len(frame)):
        if open_trade is not None:
            direction, entry, stop, target = open_trade
            exit_price = None
            if direction == "long":
                if low[i] <= stop:
                    exit_price = stop
                elif high[i] >= target:
                    exit_price = target
            else:
                if high[i] >= stop:
                    exit_price = stop
                elif low[i] <= target:
                    exit_price = target
            if exit_price is not None:
                gross = (exit_price - entry) / entry if direction == "long" else (entry - exit_price) / entry
                returns.append(gross - cost)
                open_trade = None
        if open_trade is None and not np.isnan(atr[i]) and atr[i] > 0:
            if longs[i]:
                entry = close[i]
                open_trade = ("long", entry, entry - atr[i] * sl_mult, entry + atr[i] * tp_mult)
            elif shorts[i]:
                entry = close[i]
                open_trade = ("short", entry, entry + atr[i] * sl_mult, entry - atr[i] * tp_mult)
    return np.array(returns, dtype=float)


def metrics(returns):
    count = len(returns)
    if count == 0:
        return None
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_win = wins.sum()
    gross_loss = -losses.sum()
    equity = np.cumsum(returns)
    peak = np.maximum.accumulate(equity)
    drawdown = (peak - equity).max() * 100
    return {
        "trades": count,
        "win_rate": round(len(wins) / count * 100, 1),
        "total_return_pct": round(returns.sum() * 100, 1),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else 99.0,
        "expectancy_pct": round(returns.mean() * 100, 3),
        "max_drawdown_pct": round(float(drawdown), 2),
        "sharpe": round(float(returns.mean() / returns.std() * np.sqrt(count)), 2) if returns.std() > 0 else 0.0,
    }


def score(result):
    """Single ranking score: reward profit factor, return and trade count;
    penalise drawdown. Strategies with too few trades are discounted."""
    if result is None or result["trades"] < 20:
        return -1e9
    sample = min(result["trades"] / 100, 1.0)
    return (
        result["profit_factor"] * 25
        + result["total_return_pct"] * 0.5
        + result["sharpe"] * 5
        - result["max_drawdown_pct"] * 0.5
    ) * sample


# ---------------------------------------------------------------------------
# Grid search
# ---------------------------------------------------------------------------

def default_grid():
    grid = []
    for fast, slow in [(5, 21), (9, 21), (9, 50), (12, 26)]:
        for sl in (2.0, 3.0):
            for tp in (0.5, 1.0, 1.5, 2.5):
                grid.append({"strategy": "EMA", "fast": fast, "slow": slow, "sl": sl, "tp": tp})
    for period in (5, 9, 14):
        for oversold, overbought in [(25, 70), (25, 75), (30, 65), (20, 80), (30, 70)]:
            for sl in (2.0, 3.0):
                for tp in (0.5, 1.0, 2.0):
                    grid.append({"strategy": "RSI", "period": period, "oversold": oversold,
                                 "overbought": overbought, "sl": sl, "tp": tp})
    for sl in (2.0, 3.0):
        for tp in (1.0, 1.5, 2.0):
            grid.append({"strategy": "MACD", "sl": sl, "tp": tp})
    return grid


def run_combo(frame, combo, cost=0.0):
    if combo["strategy"] == "EMA":
        longs, shorts = ema_cross_signals(frame, combo["fast"], combo["slow"])
    elif combo["strategy"] == "RSI":
        longs, shorts = rsi_reversion_signals(frame, combo["period"], combo["oversold"], combo["overbought"])
    else:
        longs, shorts = macd_signals(frame)
    returns = simulate(frame, longs, shorts, combo["sl"], combo["tp"], cost)
    return metrics(returns)


def grid_search(frame, grid=None, cost=0.0):
    grid = grid or default_grid()
    ranked = []
    for combo in grid:
        result = run_combo(frame, combo, cost)
        ranked.append({"params": combo, "result": result, "score": round(score(result), 2)})
    ranked.sort(key=lambda row: row["score"], reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Out-of-sample validation
# ---------------------------------------------------------------------------

def _best_params(frame, cost):
    """Optimize over the grid on `frame` and return the winning param combo."""
    ranked = grid_search(frame, cost=cost)
    return ranked[0]["params"] if ranked and ranked[0]["score"] > -1e8 else None


def holdout(frame, cost=0.0, train_frac=0.70):
    """Optimize on the first `train_frac` of the data, then measure the SAME
    parameters on the unseen remainder. The test metrics are the honest ones."""
    split = int(len(frame) * train_frac)
    train, test = frame.iloc[:split], frame.iloc[split:]
    params = _best_params(train, cost)
    if params is None:
        return None
    return {
        "params": params,
        "in_sample": run_combo(train, params, cost),
        "out_of_sample": run_combo(test, params, cost),
    }


def walk_forward(frame, cost=0.0, folds=5):
    """Anchored walk-forward: repeatedly optimize on all data seen so far and
    trade the next fold out-of-sample, then aggregate every out-of-sample trade.
    This is the strongest test — params are never tuned on the data they trade."""
    n = len(frame)
    if n < folds * 40:
        return None
    bounds = [int(n * k / (folds + 1)) for k in range(1, folds + 2)]
    oos_returns, chosen = [], []
    for i in range(folds):
        train = frame.iloc[:bounds[i]]
        test = frame.iloc[bounds[i]:bounds[i + 1]]
        params = _best_params(train, cost)
        if params is None:
            continue
        chosen.append(params["strategy"])
        if params["strategy"] == "EMA":
            longs, shorts = ema_cross_signals(test, params["fast"], params["slow"])
        elif params["strategy"] == "RSI":
            longs, shorts = rsi_reversion_signals(test, params["period"], params["oversold"], params["overbought"])
        else:
            longs, shorts = macd_signals(test)
        oos_returns.extend(simulate(test, longs, shorts, params["sl"], params["tp"], cost).tolist())
    result = metrics(np.array(oos_returns, dtype=float)) if oos_returns else None
    return {"folds": folds, "strategies_chosen": chosen, "out_of_sample": result}


def verdict(holdout_result, wf_result, min_trades=15):
    """A strategy 'survives' if it stays profitable on data it was never tuned on."""
    reasons = []
    oos = holdout_result and holdout_result.get("out_of_sample")
    wf = wf_result and wf_result.get("out_of_sample")
    if not oos or oos["trades"] < min_trades:
        reasons.append("too few out-of-sample trades")
    else:
        if oos["profit_factor"] < 1.0:
            reasons.append(f"holdout PF {oos['profit_factor']} < 1")
        if oos["total_return_pct"] <= 0:
            reasons.append("holdout return <= 0")
    if not wf or wf["trades"] < min_trades:
        reasons.append("too few walk-forward trades")
    elif wf["profit_factor"] < 1.0:
        reasons.append(f"walk-forward PF {wf['profit_factor']} < 1")
    elif wf["total_return_pct"] <= 0:
        reasons.append("walk-forward return <= 0")
    return {"survives": len(reasons) == 0, "reasons": reasons}
