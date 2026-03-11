"""
Deriv Jump Indices Backtesting Engine
Jump indices have sudden price jumps at random intervals.

Instruments:
  - Jump 10 Index       [JD10]
  - Jump 25 Index       [JD25]
  - Jump 50 Index       [JD50]
  - Jump 75 Index       [JD75]
  - Jump 100 Index      [JD100]

Fetches 2+ years of real candle data from Deriv WebSocket API.
Uses 4H candles to maximize data coverage (~4380 bars = 2 years).
"""

import asyncio
import json
import pandas as pd
import numpy as np
import websockets
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Deriv API - Data Fetching
# ---------------------------------------------------------------------------

DERIV_WS = "wss://ws.derivws.com/websockets/v3?app_id=1089"

JUMP_INSTRUMENTS = {
    "JD10":  {"name": "Jump 10 Index",  "pip": 0.01},
    "JD25":  {"name": "Jump 25 Index",  "pip": 0.01},
    "JD50":  {"name": "Jump 50 Index",  "pip": 0.01},
    "JD75":  {"name": "Jump 75 Index",  "pip": 0.01},
    "JD100": {"name": "Jump 100 Index", "pip": 0.01},
}


async def _fetch_candles(symbol, granularity=14400, count=5000):
    """
    Fetch candle data from Deriv API.
    granularity: 60=1m, 300=5m, 900=15m, 3600=1h, 14400=4h, 86400=1d
    Fetches in batches to get 2+ years of data.
    """
    all_candles = []
    end_time = int(datetime.now().timestamp())

    # For 2+ years: 4H candles => ~4380 bars needed, fetch 3 batches of 5000
    batches_needed = 4
    for batch in range(batches_needed):
        try:
            async with websockets.connect(DERIV_WS) as ws:
                request = {
                    "ticks_history": symbol,
                    "adjust_start_time": 1,
                    "count": count,
                    "end": str(end_time),
                    "granularity": granularity,
                    "style": "candles",
                }
                await ws.send(json.dumps(request))
                response = json.loads(await ws.recv())

                if "error" in response:
                    print(f"  API Error for {symbol}: {response['error']['message']}")
                    break

                candles = response.get("candles", [])
                if not candles:
                    break

                all_candles = candles + all_candles
                end_time = candles[0]["epoch"] - 1
                print(f"    Batch {batch+1}: {len(candles)} candles (total: {len(all_candles)})")

        except Exception as e:
            print(f"  Connection error: {e}")
            break

    if not all_candles:
        return None

    df = pd.DataFrame(all_candles)
    df["time"] = pd.to_datetime(df["epoch"], unit="s")
    df.set_index("time", inplace=True)
    df = df.rename(columns={"open": "Open", "high": "High",
                             "low": "Low", "close": "Close"})
    df["Open"] = df["Open"].astype(float)
    df["High"] = df["High"].astype(float)
    df["Low"] = df["Low"].astype(float)
    df["Close"] = df["Close"].astype(float)
    df["Volume"] = 1

    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()
    return df


def fetch_candles(symbol, granularity=14400, count=5000):
    """Synchronous wrapper."""
    return asyncio.run(_fetch_candles(symbol, granularity, count))


# ---------------------------------------------------------------------------
# Indicators (custom, no external deps)
# ---------------------------------------------------------------------------

def compute_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_atr(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_stoch_rsi(series, period=14, smooth_k=3, smooth_d=3):
    rsi = compute_rsi(series, period)
    rsi_min = rsi.rolling(period).min()
    rsi_max = rsi.rolling(period).max()
    stoch = (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10) * 100
    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


def compute_bollinger(series, period=20, std_dev=2):
    mid = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return mid + std_dev * std, mid, mid - std_dev * std


def compute_adx(df, period=14):
    """Compute ADX for trend strength."""
    high, low, close = df["High"], df["Low"], df["Close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    # When +DM > -DM, keep +DM, else 0 and vice versa
    plus_dm[(plus_dm < minus_dm)] = 0
    minus_dm[(minus_dm < plus_dm)] = 0

    atr = compute_atr(df, period)
    plus_di = 100 * compute_ema(plus_dm, period) / (atr + 1e-10)
    minus_di = 100 * compute_ema(minus_dm, period) / (atr + 1e-10)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = compute_ema(dx, period)
    return adx


def add_indicators(df):
    """Add all technical indicators."""
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    df["EMA_5"] = compute_ema(close, 5)
    df["EMA_9"] = compute_ema(close, 9)
    df["EMA_21"] = compute_ema(close, 21)
    df["EMA_50"] = compute_ema(close, 50)
    df["EMA_200"] = compute_ema(close, 200)

    df["RSI"] = compute_rsi(close, 14)
    df["StochRSI_K"], df["StochRSI_D"] = compute_stoch_rsi(close)
    df["MACD"], df["MACD_Signal"], df["MACD_Hist"] = compute_macd(close)

    df["BB_Upper"], df["BB_Mid"], df["BB_Lower"] = compute_bollinger(close)
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"]

    df["ATR"] = compute_atr(df, 14)
    df["ATR_Pct"] = df["ATR"] / close * 100

    df["ADX"] = compute_adx(df, 14)

    df["ROC_5"] = close.pct_change(5) * 100
    df["ROC_10"] = close.pct_change(10) * 100

    df["Resistance_20"] = high.rolling(20).max()
    df["Support_20"] = low.rolling(20).min()

    # Jump-specific: detect large candles (potential jump bars)
    df["Range"] = high - low
    df["Range_MA"] = df["Range"].rolling(20).mean()
    df["Jump_Bar"] = df["Range"] > df["Range_MA"] * 2.5  # candle 2.5x avg range

    df.dropna(inplace=True)
    return df


# ---------------------------------------------------------------------------
# Trade Exit
# ---------------------------------------------------------------------------

def _check_exit(row, pos, trailing_sl=None):
    """Check SL/TP. Returns (closed, pnl_pct, exit_price)."""
    sl = trailing_sl if trailing_sl is not None else pos["sl"]
    if pos["type"] == "BUY":
        if row["Low"] <= sl:
            pnl = (sl - pos["entry"]) / pos["entry"] * 100
            return True, pnl, sl
        if row["High"] >= pos["tp"]:
            pnl = (pos["tp"] - pos["entry"]) / pos["entry"] * 100
            return True, pnl, pos["tp"]
    else:
        if row["High"] >= sl:
            pnl = (pos["entry"] - sl) / pos["entry"] * 100
            return True, pnl, sl
        if row["Low"] <= pos["tp"]:
            pnl = (pos["entry"] - pos["tp"]) / pos["entry"] * 100
            return True, pnl, pos["tp"]
    return False, 0, 0


# ---------------------------------------------------------------------------
# STRATEGIES (tuned for Jump indices - wider SL to handle sudden jumps)
# ---------------------------------------------------------------------------

def strategy_ema_crossover(df, fast_p=9, slow_p=21, sl_atr=2.0, tp_atr=2.5):
    """EMA crossover - wider SL for jump volatility."""
    trades, pos = [], None
    fast = compute_ema(df["Close"], fast_p)
    slow = compute_ema(df["Close"], slow_p)

    for i in range(1, len(df)):
        r = df.iloc[i]
        if pos is None:
            if fast.iloc[i-1] <= slow.iloc[i-1] and fast.iloc[i] > slow.iloc[i]:
                pos = {
                    "type": "BUY", "entry": r["Close"],
                    "sl": r["Close"] - r["ATR"] * sl_atr,
                    "tp": r["Close"] + r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
            elif fast.iloc[i-1] >= slow.iloc[i-1] and fast.iloc[i] < slow.iloc[i]:
                pos = {
                    "type": "SELL", "entry": r["Close"],
                    "sl": r["Close"] + r["ATR"] * sl_atr,
                    "tp": r["Close"] - r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
        else:
            closed, pnl, _ = _check_exit(r, pos)
            if closed:
                pos["exit_date"] = r.name
                pos["pnl"] = round(pnl, 2)
                pos["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(pos)
                pos = None
    return trades


def strategy_rsi_reversal(df, oversold=30, overbought=70, sl_atr=2.0, tp_atr=2.5):
    """RSI mean reversion."""
    trades, pos = [], None
    for i in range(1, len(df)):
        r, p = df.iloc[i], df.iloc[i - 1]
        if pos is None:
            if p["RSI"] < oversold and r["RSI"] >= oversold:
                pos = {
                    "type": "BUY", "entry": r["Close"],
                    "sl": r["Close"] - r["ATR"] * sl_atr,
                    "tp": r["Close"] + r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
            elif p["RSI"] > overbought and r["RSI"] <= overbought:
                pos = {
                    "type": "SELL", "entry": r["Close"],
                    "sl": r["Close"] + r["ATR"] * sl_atr,
                    "tp": r["Close"] - r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
        else:
            closed, pnl, _ = _check_exit(r, pos)
            if closed:
                pos["exit_date"] = r.name
                pos["pnl"] = round(pnl, 2)
                pos["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(pos)
                pos = None
    return trades


def strategy_macd_momentum(df, sl_atr=2.0, tp_atr=2.0):
    """MACD histogram crossover."""
    trades, pos = [], None
    for i in range(1, len(df)):
        r, p = df.iloc[i], df.iloc[i - 1]
        if pos is None:
            if p["MACD_Hist"] <= 0 and r["MACD_Hist"] > 0 and r["MACD"] > r["MACD_Signal"]:
                pos = {
                    "type": "BUY", "entry": r["Close"],
                    "sl": r["Close"] - r["ATR"] * sl_atr,
                    "tp": r["Close"] + r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
            elif p["MACD_Hist"] >= 0 and r["MACD_Hist"] < 0 and r["MACD"] < r["MACD_Signal"]:
                pos = {
                    "type": "SELL", "entry": r["Close"],
                    "sl": r["Close"] + r["ATR"] * sl_atr,
                    "tp": r["Close"] - r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
        else:
            closed, pnl, _ = _check_exit(r, pos)
            if closed:
                pos["exit_date"] = r.name
                pos["pnl"] = round(pnl, 2)
                pos["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(pos)
                pos = None
    return trades


def strategy_bollinger_bounce(df, sl_atr=2.5, tp_atr=1.5):
    """BB bounce - mean reversion after price hits band."""
    trades, pos = [], None
    for i in range(1, len(df)):
        r, p = df.iloc[i], df.iloc[i - 1]
        if pos is None:
            if p["Close"] <= p["BB_Lower"] and r["Close"] > r["BB_Lower"] and r["RSI"] < 40:
                pos = {
                    "type": "BUY", "entry": r["Close"],
                    "sl": r["Close"] - r["ATR"] * sl_atr,
                    "tp": r["BB_Mid"],
                    "entry_date": r.name,
                }
            elif p["Close"] >= p["BB_Upper"] and r["Close"] < r["BB_Upper"] and r["RSI"] > 60:
                pos = {
                    "type": "SELL", "entry": r["Close"],
                    "sl": r["Close"] + r["ATR"] * sl_atr,
                    "tp": r["BB_Mid"],
                    "entry_date": r.name,
                }
        else:
            closed, pnl, _ = _check_exit(r, pos)
            if closed:
                pos["exit_date"] = r.name
                pos["pnl"] = round(pnl, 2)
                pos["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(pos)
                pos = None
    return trades


def strategy_jump_fade(df, sl_atr=2.0, tp_atr=1.5):
    """
    JUMP-SPECIFIC: Fade the jump.
    After a large jump bar, price often reverts partially.
    Enter opposite direction after a confirmed jump bar.
    """
    trades, pos = [], None
    for i in range(2, len(df)):
        r = df.iloc[i]
        prev = df.iloc[i - 1]

        if pos is None:
            # Previous bar was a jump bar
            if prev["Jump_Bar"]:
                jump_dir = prev["Close"] - prev["Open"]
                # Jump was up - fade it (sell)
                if jump_dir > 0 and r["RSI"] > 55:
                    pos = {
                        "type": "SELL", "entry": r["Close"],
                        "sl": r["Close"] + r["ATR"] * sl_atr,
                        "tp": r["Close"] - r["ATR"] * tp_atr,
                        "entry_date": r.name,
                    }
                # Jump was down - fade it (buy)
                elif jump_dir < 0 and r["RSI"] < 45:
                    pos = {
                        "type": "BUY", "entry": r["Close"],
                        "sl": r["Close"] - r["ATR"] * sl_atr,
                        "tp": r["Close"] + r["ATR"] * tp_atr,
                        "entry_date": r.name,
                    }
        else:
            closed, pnl, _ = _check_exit(r, pos)
            if closed:
                pos["exit_date"] = r.name
                pos["pnl"] = round(pnl, 2)
                pos["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(pos)
                pos = None
    return trades


def strategy_jump_continuation(df, sl_atr=2.0, tp_atr=3.0):
    """
    JUMP-SPECIFIC: Ride the jump momentum.
    After a jump bar in trend direction, price often continues.
    """
    trades, pos = [], None
    for i in range(2, len(df)):
        r = df.iloc[i]
        prev = df.iloc[i - 1]

        if pos is None:
            if prev["Jump_Bar"]:
                jump_dir = prev["Close"] - prev["Open"]
                # Jump up in uptrend - continuation
                if (jump_dir > 0 and r["Close"] > r["EMA_21"] and
                        r["EMA_21"] > r["EMA_50"] and r["RSI"] > 50 and r["RSI"] < 80):
                    pos = {
                        "type": "BUY", "entry": r["Close"],
                        "sl": r["Close"] - r["ATR"] * sl_atr,
                        "tp": r["Close"] + r["ATR"] * tp_atr,
                        "entry_date": r.name,
                    }
                # Jump down in downtrend - continuation
                elif (jump_dir < 0 and r["Close"] < r["EMA_21"] and
                      r["EMA_21"] < r["EMA_50"] and r["RSI"] < 50 and r["RSI"] > 20):
                    pos = {
                        "type": "SELL", "entry": r["Close"],
                        "sl": r["Close"] + r["ATR"] * sl_atr,
                        "tp": r["Close"] - r["ATR"] * tp_atr,
                        "entry_date": r.name,
                    }
        else:
            closed, pnl, _ = _check_exit(r, pos)
            if closed:
                pos["exit_date"] = r.name
                pos["pnl"] = round(pnl, 2)
                pos["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(pos)
                pos = None
    return trades


def strategy_trend_pullback(df, sl_atr=2.5, tp_atr=2.0):
    """Trend pullback to EMA 21 with trailing stop."""
    trades, pos, trailing_sl = [], None, None
    for i in range(2, len(df)):
        r = df.iloc[i]
        if pos is None:
            trailing_sl = None
            bull_stack = r["EMA_9"] > r["EMA_21"] > r["EMA_50"]
            bear_stack = r["EMA_9"] < r["EMA_21"] < r["EMA_50"]
            near_ema21 = abs(r["Close"] - r["EMA_21"]) < r["ATR"] * 0.6
            strong_trend = r["ADX"] > 20

            if (bull_stack and near_ema21 and strong_trend and
                    r["StochRSI_K"] < 30 and r["Close"] > r["EMA_21"]):
                pos = {
                    "type": "BUY", "entry": r["Close"],
                    "sl": r["EMA_21"] - r["ATR"] * 0.5,
                    "tp": r["Close"] + r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
            elif (bear_stack and near_ema21 and strong_trend and
                  r["StochRSI_K"] > 70 and r["Close"] < r["EMA_21"]):
                pos = {
                    "type": "SELL", "entry": r["Close"],
                    "sl": r["EMA_21"] + r["ATR"] * 0.5,
                    "tp": r["Close"] - r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
        else:
            if pos["type"] == "BUY":
                profit = r["High"] - pos["entry"]
                if profit >= r["ATR"]:
                    new_trail = r["High"] - r["ATR"]
                    if trailing_sl is None or new_trail > trailing_sl:
                        trailing_sl = new_trail
            else:
                profit = pos["entry"] - r["Low"]
                if profit >= r["ATR"]:
                    new_trail = r["Low"] + r["ATR"]
                    if trailing_sl is None or new_trail < trailing_sl:
                        trailing_sl = new_trail

            closed, pnl, _ = _check_exit(r, pos, trailing_sl)
            if closed:
                pos["exit_date"] = r.name
                pos["pnl"] = round(pnl, 2)
                pos["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(pos)
                pos = None
                trailing_sl = None
    return trades


def strategy_breakout(df, sl_atr=2.0, tp_atr=2.5):
    """Breakout of 20-period high/low with momentum."""
    trades, pos = [], None
    for i in range(2, len(df)):
        r, p = df.iloc[i], df.iloc[i - 1]
        if pos is None:
            bb_expanding = r["BB_Width"] > df.iloc[max(0, i-5):i]["BB_Width"].mean()

            if (r["Close"] > p["Resistance_20"] and bb_expanding and
                    r["RSI"] > 50 and r["RSI"] < 80 and r["MACD_Hist"] > 0):
                pos = {
                    "type": "BUY", "entry": r["Close"],
                    "sl": r["Close"] - r["ATR"] * sl_atr,
                    "tp": r["Close"] + r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
            elif (r["Close"] < p["Support_20"] and bb_expanding and
                  r["RSI"] < 50 and r["RSI"] > 20 and r["MACD_Hist"] < 0):
                pos = {
                    "type": "SELL", "entry": r["Close"],
                    "sl": r["Close"] + r["ATR"] * sl_atr,
                    "tp": r["Close"] - r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
        else:
            closed, pnl, _ = _check_exit(r, pos)
            if closed:
                pos["exit_date"] = r.name
                pos["pnl"] = round(pnl, 2)
                pos["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(pos)
                pos = None
    return trades


def strategy_optimized_trend(df, ema_len=20, adx_thresh=25, rsi_low=35,
                              rsi_high=65, sl_atr=3.0, tp_atr=2.0):
    """Parameterized trend-following (best on EUR/USD, testing on jumps)."""
    trades, pos = [], None
    ema = compute_ema(df["Close"], ema_len)

    for i in range(2, len(df)):
        r = df.iloc[i]
        if pos is None:
            uptrend = r["Close"] > ema.iloc[i] and ema.iloc[i] > ema.iloc[i - 1]
            downtrend = r["Close"] < ema.iloc[i] and ema.iloc[i] < ema.iloc[i - 1]

            if uptrend and r["ADX"] > adx_thresh and rsi_low < r["RSI"] < rsi_high:
                pos = {
                    "type": "BUY", "entry": r["Close"],
                    "sl": r["Close"] - r["ATR"] * sl_atr,
                    "tp": r["Close"] + r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
            elif downtrend and r["ADX"] > adx_thresh and (100 - rsi_high) < r["RSI"] < (100 - rsi_low):
                pos = {
                    "type": "SELL", "entry": r["Close"],
                    "sl": r["Close"] + r["ATR"] * sl_atr,
                    "tp": r["Close"] - r["ATR"] * tp_atr,
                    "entry_date": r.name,
                }
        else:
            closed, pnl, _ = _check_exit(r, pos)
            if closed:
                pos["exit_date"] = r.name
                pos["pnl"] = round(pnl, 2)
                pos["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(pos)
                pos = None
    return trades


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def calc_stats(trades):
    if not trades:
        return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0,
                "total_return": 0, "avg_win": 0, "avg_loss": 0,
                "profit_factor": 0, "max_dd": 0, "avg_rr": 0, "expectancy": 0}

    wins = [t for t in trades if t["result"] == "WIN"]
    losses = [t for t in trades if t["result"] == "LOSS"]
    total_ret = sum(t["pnl"] for t in trades)

    gp = sum(t["pnl"] for t in wins) if wins else 0
    gl = abs(sum(t["pnl"] for t in losses)) if losses else 0
    aw = gp / len(wins) if wins else 0
    al = gl / len(losses) if losses else 0

    cumulative = np.cumsum([t["pnl"] for t in trades])
    peak = np.maximum.accumulate(cumulative)
    dd = peak - cumulative
    max_dd = float(np.max(dd)) if len(dd) > 0 else 0

    return {
        "total": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "total_return": round(total_ret, 2),
        "avg_win": round(aw, 2),
        "avg_loss": round(-al, 2),
        "profit_factor": round(gp / gl, 2) if gl > 0 else float("inf"),
        "max_dd": round(max_dd, 2),
        "avg_rr": round(aw / al, 2) if al > 0 else 0,
        "expectancy": round(total_ret / len(trades), 2),
    }


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def optimize_instrument(symbol, df, min_trades=15):
    """Sweep parameters for one Jump instrument."""
    results = []

    # EMA Crossover sweep
    for fast, slow in [(5, 13), (5, 21), (9, 21), (7, 21), (12, 26)]:
        for sl in [1.5, 2.0, 2.5, 3.0, 3.5]:
            for tp in [0.75, 1.0, 1.5, 2.0, 2.5, 3.0]:
                trades = strategy_ema_crossover(df, fast, slow, sl, tp)
                if len(trades) >= min_trades:
                    s = calc_stats(trades)
                    results.append({"strategy": f"EMA({fast}/{slow})",
                                    "params": f"SL:{sl} TP:{tp}", **s})

    # RSI sweep
    for os_val in [25, 30, 35]:
        for ob_val in [65, 70, 75]:
            for sl in [1.5, 2.0, 2.5, 3.0]:
                for tp in [0.75, 1.0, 1.5, 2.0, 2.5]:
                    trades = strategy_rsi_reversal(df, os_val, ob_val, sl, tp)
                    if len(trades) >= min_trades:
                        s = calc_stats(trades)
                        results.append({"strategy": f"RSI({os_val}/{ob_val})",
                                        "params": f"SL:{sl} TP:{tp}", **s})

    # MACD sweep
    for sl in [1.5, 2.0, 2.5, 3.0]:
        for tp in [0.75, 1.0, 1.5, 2.0, 2.5, 3.0]:
            trades = strategy_macd_momentum(df, sl, tp)
            if len(trades) >= min_trades:
                s = calc_stats(trades)
                results.append({"strategy": "MACD", "params": f"SL:{sl} TP:{tp}", **s})

    # Jump Fade sweep
    for sl in [1.5, 2.0, 2.5, 3.0]:
        for tp in [0.75, 1.0, 1.5, 2.0, 2.5]:
            trades = strategy_jump_fade(df, sl, tp)
            if len(trades) >= min_trades:
                s = calc_stats(trades)
                results.append({"strategy": "JumpFade",
                                "params": f"SL:{sl} TP:{tp}", **s})

    # Jump Continuation sweep
    for sl in [1.5, 2.0, 2.5, 3.0]:
        for tp in [1.5, 2.0, 2.5, 3.0, 4.0]:
            trades = strategy_jump_continuation(df, sl, tp)
            if len(trades) >= min_trades:
                s = calc_stats(trades)
                results.append({"strategy": "JumpContinuation",
                                "params": f"SL:{sl} TP:{tp}", **s})

    # Optimized Trend sweep
    for ema_len in [20, 30, 50]:
        for adx_thresh in [20, 25]:
            for rsi_low, rsi_high in [(30, 70), (35, 65), (35, 75)]:
                for sl in [2.0, 2.5, 3.0, 3.5]:
                    for tp in [1.0, 1.5, 2.0, 2.5]:
                        trades = strategy_optimized_trend(
                            df, ema_len, adx_thresh, rsi_low, rsi_high, sl, tp
                        )
                        if len(trades) >= min_trades:
                            s = calc_stats(trades)
                            results.append({
                                "strategy": f"OptTrend(E{ema_len})",
                                "params": f"ADX>{adx_thresh} RSI({rsi_low}/{rsi_high}) SL:{sl} TP:{tp}",
                                **s
                            })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_all():
    """Fetch data and run backtests for all Jump indices."""
    all_best = {}

    for symbol, info in JUMP_INSTRUMENTS.items():
        print(f"\n{'='*90}")
        print(f"  {info['name']} [{symbol}]")
        print(f"{'='*90}")

        print(f"  Fetching 4H candles from Deriv API (2+ years)...")
        df = fetch_candles(symbol, granularity=14400, count=5000)

        if df is None or len(df) < 200:
            print(f"  ERROR: Insufficient data ({0 if df is None else len(df)} bars)")
            continue

        df = add_indicators(df)
        days = (df.index[-1] - df.index[0]).days
        jump_bars = df["Jump_Bar"].sum()

        print(f"  Data: {len(df)} bars ({days} days / {days/365:.1f} years)")
        print(f"  Range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
        print(f"  Price: {df['Close'].min():.2f} - {df['Close'].max():.2f}")
        print(f"  Current: {df['Close'].iloc[-1]:.2f} | RSI: {df['RSI'].iloc[-1]:.1f} | "
              f"ATR: {df['ATR'].iloc[-1]:.2f} ({df['ATR_Pct'].iloc[-1]:.2f}%)")
        print(f"  Jump Bars Detected: {jump_bars} ({jump_bars/len(df)*100:.1f}%)")

        # Run default strategies
        print(f"\n  --- Default Strategies ---")
        strategies = {
            "EMA Crossover (9/21)": strategy_ema_crossover(df),
            "RSI Reversal (30/70)": strategy_rsi_reversal(df),
            "MACD Momentum": strategy_macd_momentum(df),
            "Bollinger Bounce": strategy_bollinger_bounce(df),
            "Jump Fade": strategy_jump_fade(df),
            "Jump Continuation": strategy_jump_continuation(df),
            "Trend Pullback": strategy_trend_pullback(df),
            "Breakout": strategy_breakout(df),
            "Optimized Trend": strategy_optimized_trend(df),
        }

        print(f"  {'Strategy':<25} {'#':>5} {'WR%':>6} {'Return':>8} {'PF':>6} {'R:R':>5} {'Expect':>7}")
        print(f"  {'-'*65}")
        for name, trades in sorted(strategies.items(),
                                    key=lambda x: calc_stats(x[1])["total_return"],
                                    reverse=True):
            s = calc_stats(trades)
            pf_str = f"{s['profit_factor']:>5.2f}" if s['profit_factor'] < 100 else "  inf"
            print(f"  {name:<25} {s['total']:>5} {s['win_rate']:>5.1f}% "
                  f"{s['total_return']:>7.1f}% {pf_str} "
                  f"{s['avg_rr']:>5.2f} {s['expectancy']:>6.2f}%")

        # Optimize
        print(f"\n  --- Optimizing (this may take a moment)... ---")
        opt = optimize_instrument(symbol, df)

        if not opt:
            print(f"  No configs with enough trades found")
            continue

        df_opt = pd.DataFrame(opt)
        profitable = df_opt[df_opt["total_return"] > 0]
        print(f"  Configs tested: {len(df_opt)} | Profitable: {len(profitable)}")

        # Balanced score
        df_opt["score"] = (
            (df_opt["win_rate"] / 100) *
            df_opt["profit_factor"].clip(upper=10) *
            df_opt["expectancy"].clip(lower=0) *
            np.log(df_opt["total"].clip(lower=1))
        )

        top = df_opt.sort_values("score", ascending=False).head(10)
        print(f"\n  TOP 10 BY BALANCED SCORE:")
        print(f"  {'Strategy':<22} {'Params':<35} {'#':>5} {'WR%':>6} {'Ret%':>8} {'PF':>6} {'R:R':>5} {'Exp':>7}")
        print(f"  {'-'*95}")
        for _, r in top.iterrows():
            pf_str = f"{r['profit_factor']:>5.2f}" if r['profit_factor'] < 100 else "  inf"
            print(f"  {r['strategy']:<22} {r['params']:<35} "
                  f"{r['total']:>5} {r['win_rate']:>5.1f}% "
                  f"{r['total_return']:>7.1f}% {pf_str} "
                  f"{r['avg_rr']:>5.2f} {r['expectancy']:>6.2f}%")

        # Top by total return
        top_ret = df_opt.sort_values("total_return", ascending=False).head(5)
        print(f"\n  TOP 5 BY TOTAL RETURN:")
        print(f"  {'Strategy':<22} {'Params':<35} {'#':>5} {'WR%':>6} {'Ret%':>8} {'PF':>6}")
        print(f"  {'-'*85}")
        for _, r in top_ret.iterrows():
            pf_str = f"{r['profit_factor']:>5.2f}" if r['profit_factor'] < 100 else "  inf"
            print(f"  {r['strategy']:<22} {r['params']:<35} "
                  f"{r['total']:>5} {r['win_rate']:>5.1f}% "
                  f"{r['total_return']:>7.1f}% {pf_str}")

        best = df_opt.sort_values("score", ascending=False).iloc[0]
        all_best[symbol] = {
            "name": info["name"],
            "strategy": best["strategy"],
            "params": best["params"],
            "trades": int(best["total"]),
            "win_rate": best["win_rate"],
            "total_return": best["total_return"],
            "profit_factor": best["profit_factor"],
            "expectancy": best["expectancy"],
            "max_dd": best["max_dd"],
            "avg_rr": best["avg_rr"],
        }

    # Final Summary
    print(f"\n\n{'*'*95}")
    print(f"  BEST STRATEGY FOR EACH JUMP INDEX (2+ YEARS BACKTEST)")
    print(f"{'*'*95}")
    print(f"{'Symbol':<8} {'Name':<18} {'Strategy':<22} {'Params':<32} {'#':>5} {'WR%':>6} {'Ret%':>8} {'PF':>6}")
    print(f"{'-'*95}")
    for sym, r in all_best.items():
        pf_str = f"{r['profit_factor']:>5.2f}" if r['profit_factor'] < 100 else "  inf"
        print(f"{sym:<8} {r['name']:<18} {r['strategy']:<22} {r['params']:<32} "
              f"{r['trades']:>5} {r['win_rate']:>5.1f}% "
              f"{r['total_return']:>7.1f}% {pf_str}")

    for sym, r in all_best.items():
        print(f"\n  {r['name']}:")
        print(f"    Strategy: {r['strategy']} | {r['params']}")
        print(f"    Trades: {r['trades']} | Win Rate: {r['win_rate']}%")
        print(f"    Total Return: {r['total_return']}% | PF: {r['profit_factor']}")
        print(f"    R:R: {r['avg_rr']} | Expectancy: {r['expectancy']}%/trade")
        print(f"    Max Drawdown: {r['max_dd']}%")

    print(f"\n{'*'*95}")
    return all_best


if __name__ == "__main__":
    run_all()
