"""
Forex Majors Backtesting Engine
Backtests 8 strategies across 5 major forex pairs:
  EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD

Strategies: EMA Crossover, RSI Reversal, MACD Momentum,
            Triple Confluence, Trend Pullback, Breakout Momentum,
            BB Squeeze, Optimized Trend

Includes parameter optimizer for top 3 strategies per pair.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.volatility import BollingerBands
from datetime import datetime
from itertools import product

# ---------------------------------------------------------------------------
# Forex pair definitions
# ---------------------------------------------------------------------------
PAIRS = {
    "EUR/USD": {"ticker": "EURUSD=X", "pip": 0.0001},
    "GBP/USD": {"ticker": "GBPUSD=X", "pip": 0.0001},
    "USD/JPY": {"ticker": "USDJPY=X", "pip": 0.01},
    "USD/CHF": {"ticker": "USDCHF=X", "pip": 0.0001},
    "AUD/USD": {"ticker": "AUDUSD=X", "pip": 0.0001},
}

# Module-level PIP (updated per pair before running strategies)
PIP = 0.0001


def fetch_data(ticker_symbol, period="5y", interval="1d"):
    """Fetch historical data via yfinance."""
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(period=period, interval=interval)
    df = df.dropna()
    return df


def add_indicators(df, pip_size):
    """Add technical indicators to dataframe."""
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # EMAs
    df["EMA_9"] = EMAIndicator(close, window=9).ema_indicator()
    df["EMA_21"] = EMAIndicator(close, window=21).ema_indicator()
    df["EMA_50"] = EMAIndicator(close, window=50).ema_indicator()
    df["EMA_200"] = EMAIndicator(close, window=200).ema_indicator()

    # RSI
    df["RSI"] = RSIIndicator(close, window=14).rsi()

    # Stochastic RSI
    stoch_rsi = StochRSIIndicator(close, window=14, smooth1=3, smooth2=3)
    df["StochRSI_K"] = stoch_rsi.stochrsi_k() * 100
    df["StochRSI_D"] = stoch_rsi.stochrsi_d() * 100

    # MACD
    macd = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df["MACD"] = macd.macd()
    df["MACD_Signal"] = macd.macd_signal()
    df["MACD_Hist"] = macd.macd_diff()

    # ADX
    adx = ADXIndicator(high, low, close, window=14)
    df["ADX"] = adx.adx()
    df["DI_Plus"] = adx.adx_pos()
    df["DI_Minus"] = adx.adx_neg()

    # Bollinger Bands
    bb = BollingerBands(close, window=20, window_dev=2)
    df["BB_Upper"] = bb.bollinger_hband()
    df["BB_Lower"] = bb.bollinger_lband()
    df["BB_Mid"] = bb.bollinger_mavg()
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"]

    # ATR
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(window=14).mean()

    # Support/Resistance
    df["Resistance_20"] = high.rolling(window=20).max()
    df["Support_20"] = low.rolling(window=20).min()

    # Volume MA
    if "Volume" in df.columns and df["Volume"].sum() > 0:
        df["Vol_MA"] = df["Volume"].rolling(window=20).mean()
    else:
        df["Volume"] = 1
        df["Vol_MA"] = 1

    # Candle patterns
    df["Body"] = abs(close - df["Open"])
    df["Range"] = high - low
    df["Body_Ratio"] = df["Body"] / df["Range"].replace(0, np.nan)

    # ATR in pips
    df["ATR_Pips"] = df["ATR"] / pip_size

    df.dropna(inplace=True)
    return df


# ---------------------------------------------------------------------------
# Exit logic
# ---------------------------------------------------------------------------

def _check_exit(row, position, pip_size, trailing_sl=None):
    """Check SL/TP exit. Returns (closed, pnl_pips, exit_price)."""
    if position["type"] == "BUY":
        sl = trailing_sl if trailing_sl is not None else position["sl"]
        if row["Low"] <= sl:
            pnl = (sl - position["entry"]) / pip_size
            return True, pnl, sl
        if row["High"] >= position["tp"]:
            pnl = (position["tp"] - position["entry"]) / pip_size
            return True, pnl, position["tp"]
    else:
        sl = trailing_sl if trailing_sl is not None else position["sl"]
        if row["High"] >= sl:
            pnl = (position["entry"] - sl) / pip_size
            return True, pnl, sl
        if row["Low"] <= position["tp"]:
            pnl = (position["entry"] - position["tp"]) / pip_size
            return True, pnl, position["tp"]
    return False, 0, 0


# ---------------------------------------------------------------------------
# STRATEGIES (all accept pip_size parameter)
# ---------------------------------------------------------------------------

def strategy_ema_crossover(df, pip_size, sl_atr_mult=1.5, tp_atr_mult=2.0):
    trades, position = [], None
    for i in range(1, len(df)):
        row, prev = df.iloc[i], df.iloc[i - 1]
        if position is None:
            if (prev["EMA_9"] <= prev["EMA_21"] and
                    row["EMA_9"] > row["EMA_21"] and
                    row["Close"] > row["EMA_50"]):
                position = {
                    "type": "BUY", "entry": row["Close"],
                    "sl": row["Close"] - row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] + row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
            elif (prev["EMA_9"] >= prev["EMA_21"] and
                  row["EMA_9"] < row["EMA_21"] and
                  row["Close"] < row["EMA_50"]):
                position = {
                    "type": "SELL", "entry": row["Close"],
                    "sl": row["Close"] + row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] - row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
        else:
            closed, pnl, _ = _check_exit(row, position, pip_size)
            if closed:
                position["exit_date"] = row.name
                position["pnl"] = round(pnl, 1)
                position["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(position)
                position = None
    return trades


def strategy_rsi_reversal(df, pip_size, rsi_oversold=30, rsi_overbought=70,
                           sl_atr_mult=1.5, tp_atr_mult=2.5):
    trades, position = [], None
    for i in range(1, len(df)):
        row, prev = df.iloc[i], df.iloc[i - 1]
        if position is None:
            if prev["RSI"] < rsi_oversold and row["RSI"] >= rsi_oversold:
                position = {
                    "type": "BUY", "entry": row["Close"],
                    "sl": row["Close"] - row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] + row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
            elif prev["RSI"] > rsi_overbought and row["RSI"] <= rsi_overbought:
                position = {
                    "type": "SELL", "entry": row["Close"],
                    "sl": row["Close"] + row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] - row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
        else:
            closed, pnl, _ = _check_exit(row, position, pip_size)
            if closed:
                position["exit_date"] = row.name
                position["pnl"] = round(pnl, 1)
                position["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(position)
                position = None
    return trades


def strategy_macd_momentum(df, pip_size, sl_atr_mult=1.5, tp_atr_mult=2.0):
    trades, position = [], None
    for i in range(1, len(df)):
        row, prev = df.iloc[i], df.iloc[i - 1]
        if position is None:
            if (prev["MACD_Hist"] <= 0 and row["MACD_Hist"] > 0 and
                    row["MACD"] > row["MACD_Signal"]):
                position = {
                    "type": "BUY", "entry": row["Close"],
                    "sl": row["Close"] - row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] + row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
            elif (prev["MACD_Hist"] >= 0 and row["MACD_Hist"] < 0 and
                  row["MACD"] < row["MACD_Signal"]):
                position = {
                    "type": "SELL", "entry": row["Close"],
                    "sl": row["Close"] + row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] - row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
        else:
            closed, pnl, _ = _check_exit(row, position, pip_size)
            if closed:
                position["exit_date"] = row.name
                position["pnl"] = round(pnl, 1)
                position["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(position)
                position = None
    return trades


def strategy_triple_confluence(df, pip_size, sl_atr_mult=2.0, tp_atr_mult=1.2):
    trades, position = [], None
    for i in range(2, len(df)):
        row, prev = df.iloc[i], df.iloc[i - 1]
        if position is None:
            uptrend = (row["EMA_50"] > row["EMA_200"] and
                       row["Close"] > row["EMA_50"])
            downtrend = (row["EMA_50"] < row["EMA_200"] and
                         row["Close"] < row["EMA_50"])

            if (uptrend and 35 < row["RSI"] < 60 and
                    row["MACD_Hist"] > prev["MACD_Hist"] and
                    row["MACD_Hist"] > 0 and row["ADX"] > 20):
                position = {
                    "type": "BUY", "entry": row["Close"],
                    "sl": row["Close"] - row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] + row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
            elif (downtrend and 40 < row["RSI"] < 65 and
                  row["MACD_Hist"] < prev["MACD_Hist"] and
                  row["MACD_Hist"] < 0 and row["ADX"] > 20):
                position = {
                    "type": "SELL", "entry": row["Close"],
                    "sl": row["Close"] + row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] - row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
        else:
            closed, pnl, _ = _check_exit(row, position, pip_size)
            if closed:
                position["exit_date"] = row.name
                position["pnl"] = round(pnl, 1)
                position["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(position)
                position = None
    return trades


def strategy_trend_pullback(df, pip_size, sl_atr_mult=2.5, tp_atr_mult=1.5):
    trades, position, trailing_sl = [], None, None
    for i in range(2, len(df)):
        row, prev = df.iloc[i], df.iloc[i - 1]
        if position is None:
            trailing_sl = None
            ema_stack_bull = (row["EMA_9"] > row["EMA_21"] > row["EMA_50"])
            ema_stack_bear = (row["EMA_9"] < row["EMA_21"] < row["EMA_50"])
            strong_trend = row["ADX"] > 25
            near_ema21 = abs(row["Close"] - row["EMA_21"]) < row["ATR"] * 0.5

            if (ema_stack_bull and strong_trend and near_ema21 and
                    row["StochRSI_K"] < 30 and row["Close"] > row["EMA_21"]):
                position = {
                    "type": "BUY", "entry": row["Close"],
                    "sl": row["EMA_21"] - row["ATR"] * 0.5,
                    "tp": row["Close"] + row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
            elif (ema_stack_bear and strong_trend and near_ema21 and
                  row["StochRSI_K"] > 70 and row["Close"] < row["EMA_21"]):
                position = {
                    "type": "SELL", "entry": row["Close"],
                    "sl": row["EMA_21"] + row["ATR"] * 0.5,
                    "tp": row["Close"] - row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
        else:
            if position["type"] == "BUY":
                profit = row["High"] - position["entry"]
                if profit >= row["ATR"] * 1.0:
                    new_trail = row["High"] - row["ATR"] * 1.0
                    if trailing_sl is None or new_trail > trailing_sl:
                        trailing_sl = new_trail
            else:
                profit = position["entry"] - row["Low"]
                if profit >= row["ATR"] * 1.0:
                    new_trail = row["Low"] + row["ATR"] * 1.0
                    if trailing_sl is None or new_trail < trailing_sl:
                        trailing_sl = new_trail

            closed, pnl, _ = _check_exit(row, position, pip_size, trailing_sl)
            if closed:
                position["exit_date"] = row.name
                position["pnl"] = round(pnl, 1)
                position["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(position)
                position = None
                trailing_sl = None
    return trades


def strategy_breakout_momentum(df, pip_size, sl_atr_mult=1.5, tp_atr_mult=1.0):
    trades, position = [], None
    for i in range(2, len(df)):
        row, prev = df.iloc[i], df.iloc[i - 1]
        if position is None:
            vol_spike = row["Volume"] > row["Vol_MA"] * 1.3
            bb_expanding = row["BB_Width"] > df.iloc[i - 5:i]["BB_Width"].mean()
            adx_rising = row["ADX"] > prev["ADX"] and row["ADX"] > 20

            if (row["Close"] > prev["Resistance_20"] and
                    vol_spike and adx_rising and bb_expanding and
                    50 < row["RSI"] < 80):
                position = {
                    "type": "BUY", "entry": row["Close"],
                    "sl": row["Close"] - row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] + row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
            elif (row["Close"] < prev["Support_20"] and
                  vol_spike and adx_rising and bb_expanding and
                  20 < row["RSI"] < 50):
                position = {
                    "type": "SELL", "entry": row["Close"],
                    "sl": row["Close"] + row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] - row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
        else:
            closed, pnl, _ = _check_exit(row, position, pip_size)
            if closed:
                position["exit_date"] = row.name
                position["pnl"] = round(pnl, 1)
                position["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(position)
                position = None
    return trades


def strategy_bb_squeeze(df, pip_size, sl_atr_mult=2.0, tp_atr_mult=1.0):
    trades, position = [], None

    bb_roll_min = df["BB_Width"].rolling(100).min()
    bb_roll_max = df["BB_Width"].rolling(100).max()
    df["BB_Pct"] = (df["BB_Width"] - bb_roll_min) / (bb_roll_max - bb_roll_min + 1e-10)

    for i in range(2, len(df)):
        row, prev = df.iloc[i], df.iloc[i - 1]
        if position is None:
            was_squeezed = any(df.iloc[i - j]["BB_Pct"] < 0.25
                               for j in range(1, 4) if i - j >= 0)
            if not was_squeezed:
                continue

            if (row["Close"] > row["BB_Upper"] and
                    row["EMA_50"] > prev["EMA_50"] and row["RSI"] > 50):
                position = {
                    "type": "BUY", "entry": row["Close"],
                    "sl": row["BB_Mid"] - row["ATR"] * 0.5,
                    "tp": row["Close"] + row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
            elif (row["Close"] < row["BB_Lower"] and
                  row["EMA_50"] < prev["EMA_50"] and row["RSI"] < 50):
                position = {
                    "type": "SELL", "entry": row["Close"],
                    "sl": row["BB_Mid"] + row["ATR"] * 0.5,
                    "tp": row["Close"] - row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
        else:
            closed, pnl, _ = _check_exit(row, position, pip_size)
            if closed:
                position["exit_date"] = row.name
                position["pnl"] = round(pnl, 1)
                position["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(position)
                position = None

    df.drop(columns=["BB_Pct"], inplace=True, errors="ignore")
    return trades


def strategy_optimized_trend(df, pip_size, ema_len=50, adx_thresh=20,
                              rsi_low=35, rsi_high=75,
                              sl_atr_mult=3.0, tp_atr_mult=0.75):
    ema = EMAIndicator(df["Close"], window=ema_len).ema_indicator()
    trades, position = [], None

    for i in range(2, len(df)):
        row, prev = df.iloc[i], df.iloc[i - 1]
        if position is None:
            uptrend = row["Close"] > ema.iloc[i] and ema.iloc[i] > ema.iloc[i - 1]
            downtrend = row["Close"] < ema.iloc[i] and ema.iloc[i] < ema.iloc[i - 1]

            if (uptrend and row["ADX"] > adx_thresh and
                    rsi_low < row["RSI"] < rsi_high):
                position = {
                    "type": "BUY", "entry": row["Close"],
                    "sl": row["Close"] - row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] + row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
            elif (downtrend and row["ADX"] > adx_thresh and
                  (100 - rsi_high) < row["RSI"] < (100 - rsi_low)):
                position = {
                    "type": "SELL", "entry": row["Close"],
                    "sl": row["Close"] + row["ATR"] * sl_atr_mult,
                    "tp": row["Close"] - row["ATR"] * tp_atr_mult,
                    "entry_date": row.name,
                }
        else:
            closed, pnl, _ = _check_exit(row, position, pip_size)
            if closed:
                position["exit_date"] = row.name
                position["pnl"] = round(pnl, 1)
                position["result"] = "WIN" if pnl > 0 else "LOSS"
                trades.append(position)
                position = None
    return trades


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def calc_stats(trades):
    """Calculate performance statistics (pips-based for forex)."""
    if not trades:
        return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0,
                "total_pips": 0, "avg_win_pips": 0, "avg_loss_pips": 0,
                "profit_factor": 0, "max_drawdown_pips": 0, "avg_rr": 0,
                "expectancy_pips": 0}

    wins = [t for t in trades if t["result"] == "WIN"]
    losses = [t for t in trades if t["result"] == "LOSS"]
    total_pips = sum(t["pnl"] for t in trades)

    gross_profit = sum(t["pnl"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["pnl"] for t in losses)) if losses else 0

    avg_win = gross_profit / len(wins) if wins else 0
    avg_loss = gross_loss / len(losses) if losses else 0
    avg_rr = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0

    # Max drawdown in pips
    cumulative = np.cumsum([t["pnl"] for t in trades])
    peak = np.maximum.accumulate(cumulative)
    drawdown = peak - cumulative
    max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0

    expectancy = total_pips / len(trades)

    return {
        "total": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "total_pips": round(total_pips, 1),
        "avg_win_pips": round(avg_win, 1),
        "avg_loss_pips": round(-avg_loss, 1),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf"),
        "max_drawdown_pips": round(max_dd, 1),
        "avg_rr": avg_rr,
        "expectancy_pips": round(expectancy, 1),
    }


# ---------------------------------------------------------------------------
# Run all strategies for a single pair
# ---------------------------------------------------------------------------

STRATEGY_FUNCS = {
    "EMA Crossover (9/21)": strategy_ema_crossover,
    "RSI Reversal": strategy_rsi_reversal,
    "MACD Momentum": strategy_macd_momentum,
    "Triple Confluence": strategy_triple_confluence,
    "Trend Pullback": strategy_trend_pullback,
    "Breakout Momentum": strategy_breakout_momentum,
    "BB Squeeze": strategy_bb_squeeze,
    "Optimized Trend": strategy_optimized_trend,
}


def run_all_strategies_for_pair(pair_name, pair_info, period="5y"):
    """Run all 8 strategies on a given pair."""
    pip_size = pair_info["pip"]
    df = fetch_data(pair_info["ticker"], period=period)
    df = add_indicators(df, pip_size)

    results = {}
    for name, func in STRATEGY_FUNCS.items():
        trades = func(df, pip_size)
        stats = calc_stats(trades)
        results[name] = {"trades": trades, "stats": stats}

    return results, df


# ---------------------------------------------------------------------------
# Parameter Optimizer
# ---------------------------------------------------------------------------

def optimize_strategy(df, pip_size, strategy_name, strategy_func):
    """Sweep parameters for a strategy and return top 5 configs."""
    # Define parameter grids per strategy
    sl_range = [1.0, 1.5, 2.0, 2.5, 3.0]
    tp_range = [0.75, 1.0, 1.5, 2.0, 2.5, 3.0]

    param_grids = {
        "EMA Crossover (9/21)": [
            {"sl_atr_mult": sl, "tp_atr_mult": tp}
            for sl in sl_range for tp in tp_range
        ],
        "RSI Reversal": [
            {"rsi_oversold": rso, "rsi_overbought": rso_h,
             "sl_atr_mult": sl, "tp_atr_mult": tp}
            for rso in [25, 30, 35]
            for rso_h in [65, 70, 75]
            for sl in [1.0, 1.5, 2.0]
            for tp in [1.5, 2.0, 2.5, 3.0]
        ],
        "MACD Momentum": [
            {"sl_atr_mult": sl, "tp_atr_mult": tp}
            for sl in sl_range for tp in tp_range
        ],
        "Triple Confluence": [
            {"sl_atr_mult": sl, "tp_atr_mult": tp}
            for sl in [1.5, 2.0, 2.5, 3.0]
            for tp in [0.75, 1.0, 1.2, 1.5, 2.0]
        ],
        "Trend Pullback": [
            {"sl_atr_mult": sl, "tp_atr_mult": tp}
            for sl in [1.5, 2.0, 2.5, 3.0]
            for tp in [1.0, 1.5, 2.0, 2.5]
        ],
        "Breakout Momentum": [
            {"sl_atr_mult": sl, "tp_atr_mult": tp}
            for sl in sl_range for tp in tp_range
        ],
        "BB Squeeze": [
            {"sl_atr_mult": sl, "tp_atr_mult": tp}
            for sl in [1.5, 2.0, 2.5, 3.0]
            for tp in [0.75, 1.0, 1.5, 2.0]
        ],
        "Optimized Trend": [
            {"ema_len": ema, "adx_thresh": adx, "rsi_low": rlo,
             "rsi_high": rhi, "sl_atr_mult": sl, "tp_atr_mult": tp}
            for ema in [30, 50, 70]
            for adx in [15, 20, 25]
            for rlo in [30, 35, 40]
            for rhi in [70, 75]
            for sl in [2.0, 3.0]
            for tp in [0.75, 1.0, 1.5]
        ],
    }

    grid = param_grids.get(strategy_name, [])
    if not grid:
        return []

    results = []
    for params in grid:
        trades = strategy_func(df, pip_size, **params)
        stats = calc_stats(trades)
        if stats["total"] >= 5:  # minimum trades filter
            results.append({
                "params": params,
                "total_pips": stats["total_pips"],
                "trades": stats["total"],
                "win_rate": stats["win_rate"],
                "profit_factor": stats["profit_factor"],
                "expectancy": stats["expectancy_pips"],
                "max_dd": stats["max_drawdown_pips"],
            })

    results.sort(key=lambda x: x["total_pips"], reverse=True)
    return results[:5]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def print_pair_results(pair_name, results, bar_count):
    """Print strategy results table for a pair."""
    print(f"\n{'='*90}")
    print(f"  {pair_name} Backtest Results (5y daily data, {bar_count} bars)")
    print(f"{'='*90}")
    print(f"  {'Strategy':<25} {'Trades':>6} {'WR%':>6} {'Pips':>10} "
          f"{'PF':>6} {'R:R':>5} {'Expect':>7} {'MaxDD':>8}")
    print(f"  {'-'*84}")

    sorted_results = sorted(results.items(),
                            key=lambda x: x[1]["stats"]["total_pips"],
                            reverse=True)
    for name, data in sorted_results:
        s = data["stats"]
        pf_str = f"{s['profit_factor']:>5.2f}" if s['profit_factor'] != float('inf') else "  inf"
        print(f"  {name:<25} {s['total']:>6} {s['win_rate']:>5.1f}% "
              f"{s['total_pips']:>9.1f} {pf_str} "
              f"{s['avg_rr']:>5.2f} {s['expectancy_pips']:>6.1f}p "
              f"{s['max_drawdown_pips']:>7.1f}p")

    return sorted_results


def print_optimizer_results(pair_name, strategy_name, opt_results):
    """Print optimizer top 5 for a strategy."""
    if not opt_results:
        print(f"    {strategy_name}: No valid configurations (min 5 trades)")
        return
    print(f"\n  Optimizer: {strategy_name}")
    print(f"  {'Rank':<5} {'Pips':>8} {'Trades':>6} {'WR%':>6} {'PF':>6} "
          f"{'Expect':>7} {'MaxDD':>8}  Params")
    print(f"  {'-'*90}")
    for rank, r in enumerate(opt_results, 1):
        pf_str = f"{r['profit_factor']:>5.2f}" if r['profit_factor'] != float('inf') else "  inf"
        params_str = ", ".join(f"{k}={v}" for k, v in r["params"].items())
        print(f"  {rank:<5} {r['total_pips']:>7.1f} {r['trades']:>6} "
              f"{r['win_rate']:>5.1f}% {pf_str} "
              f"{r['expectancy']:>6.1f}p {r['max_dd']:>7.1f}p  {params_str}")


if __name__ == "__main__":
    print("=" * 90)
    print("  FOREX MAJORS BACKTESTING ENGINE")
    print("  5 Pairs x 8 Strategies + Parameter Optimization")
    print("=" * 90)

    all_best = {}  # pair -> (strategy_name, stats)

    for pair_name, pair_info in PAIRS.items():
        pip_label = "0.01" if pair_info["pip"] == 0.01 else "0.0001"
        print(f"\n>>> Fetching {pair_name} ({pair_info['ticker']}, pip={pip_label}) ...")

        try:
            results, df = run_all_strategies_for_pair(pair_name, pair_info)
        except Exception as e:
            print(f"  ERROR fetching {pair_name}: {e}")
            continue

        # Print results table
        sorted_results = print_pair_results(pair_name, results, len(df))

        # Track best strategy
        if sorted_results:
            best_name, best_data = sorted_results[0]
            all_best[pair_name] = (best_name, best_data["stats"])

        # Optimizer: top 3 strategies by total pips
        top3_names = [name for name, _ in sorted_results[:3]]
        print(f"\n  --- Parameter Optimization (top 3 strategies) ---")

        for strat_name in top3_names:
            strat_func = STRATEGY_FUNCS[strat_name]
            opt_results = optimize_strategy(df, pair_info["pip"],
                                            strat_name, strat_func)
            print_optimizer_results(pair_name, strat_name, opt_results)

    # ---------------------------------------------------------------------------
    # Final comparison table
    # ---------------------------------------------------------------------------
    print(f"\n\n{'='*90}")
    print(f"  FINAL COMPARISON: Best Strategy Per Pair")
    print(f"{'='*90}")
    print(f"  {'Pair':<10} {'Best Strategy':<25} {'Trades':>6} {'WR%':>6} "
          f"{'Pips':>10} {'PF':>6} {'R:R':>5} {'Expect':>7} {'MaxDD':>8}")
    print(f"  {'-'*84}")

    for pair_name in PAIRS:
        if pair_name not in all_best:
            print(f"  {pair_name:<10} {'(no data)':<25}")
            continue
        strat_name, s = all_best[pair_name]
        pf_str = f"{s['profit_factor']:>5.2f}" if s['profit_factor'] != float('inf') else "  inf"
        print(f"  {pair_name:<10} {strat_name:<25} {s['total']:>6} "
              f"{s['win_rate']:>5.1f}% {s['total_pips']:>9.1f} {pf_str} "
              f"{s['avg_rr']:>5.2f} {s['expectancy_pips']:>6.1f}p "
              f"{s['max_drawdown_pips']:>7.1f}p")

    print(f"{'='*90}")
    print(f"\nDone. Backtest complete for all forex majors.")
