"""
EUR/USD Optimizer - Parameter sweep for top 3 strategies:
1. Optimized Trend
2. EMA Crossover (9/21)
3. BB Squeeze
"""

from backtest_eurusd import (
    fetch_eurusd_data, add_indicators, calc_stats,
    strategy_optimized_trend, strategy_ema_crossover, strategy_bb_squeeze,
    PIP
)
from ta.trend import EMAIndicator
import itertools
import numpy as np


def optimize_ema_crossover(df):
    """Sweep SL/TP ATR multipliers for EMA Crossover."""
    print("\n>>> Optimizing EMA Crossover (9/21)...")
    best = []
    for sl_mult in [1.0, 1.5, 2.0, 2.5, 3.0]:
        for tp_mult in [0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]:
            trades = strategy_ema_crossover(df, sl_atr_mult=sl_mult, tp_atr_mult=tp_mult)
            stats = calc_stats(trades)
            if stats["total"] >= 10:
                score = (stats["win_rate"] / 100) * stats["profit_factor"] * max(stats["expectancy_pips"], 0.01) * np.log(stats["total"] + 1)
                best.append({
                    "params": f"SL={sl_mult}x, TP={tp_mult}x",
                    "stats": stats,
                    "score": score,
                    "trades": trades,
                })
    best.sort(key=lambda x: x["score"], reverse=True)
    return best[:10]


def optimize_bb_squeeze(df):
    """Sweep SL/TP ATR multipliers for BB Squeeze."""
    print("\n>>> Optimizing BB Squeeze...")
    best = []
    for sl_mult in [1.0, 1.5, 2.0, 2.5, 3.0]:
        for tp_mult in [0.5, 0.75, 1.0, 1.5, 2.0, 2.5]:
            trades = strategy_bb_squeeze(df, sl_atr_mult=sl_mult, tp_atr_mult=tp_mult)
            stats = calc_stats(trades)
            if stats["total"] >= 10:
                score = (stats["win_rate"] / 100) * stats["profit_factor"] * max(stats["expectancy_pips"], 0.01) * np.log(stats["total"] + 1)
                best.append({
                    "params": f"SL={sl_mult}x, TP={tp_mult}x",
                    "stats": stats,
                    "score": score,
                    "trades": trades,
                })
    best.sort(key=lambda x: x["score"], reverse=True)
    return best[:10]


def optimize_trend(df):
    """Sweep all params for Optimized Trend."""
    print("\n>>> Optimizing Trend Strategy...")
    best = []
    for ema_len in [20, 30, 50, 75, 100]:
        for adx_thresh in [15, 20, 25]:
            for rsi_low, rsi_high in [(30, 70), (35, 75), (40, 70), (35, 65), (30, 65)]:
                for sl_mult in [1.5, 2.0, 2.5, 3.0, 3.5]:
                    for tp_mult in [0.5, 0.75, 1.0, 1.5, 2.0]:
                        trades = strategy_optimized_trend(
                            df, ema_len=ema_len, adx_thresh=adx_thresh,
                            rsi_low=rsi_low, rsi_high=rsi_high,
                            sl_atr_mult=sl_mult, tp_atr_mult=tp_mult
                        )
                        stats = calc_stats(trades)
                        if stats["total"] >= 15:
                            score = (stats["win_rate"] / 100) * stats["profit_factor"] * max(stats["expectancy_pips"], 0.01) * np.log(stats["total"] + 1)
                            best.append({
                                "params": f"EMA={ema_len}, ADX>{adx_thresh}, RSI({rsi_low}/{rsi_high}), SL={sl_mult}x, TP={tp_mult}x",
                                "stats": stats,
                                "score": score,
                                "trades": trades,
                            })
    best.sort(key=lambda x: x["score"], reverse=True)
    return best[:10]


def print_results(title, results):
    print(f"\n{'='*100}")
    print(f"  {title} - TOP CONFIGURATIONS")
    print(f"{'='*100}")
    print(f"{'#':<3} {'Parameters':<50} {'Trades':>6} {'WR%':>6} {'Pips':>9} {'PF':>6} {'R:R':>5} {'Expect':>7} {'MaxDD':>7}")
    print(f"{'-'*100}")
    for i, r in enumerate(results, 1):
        s = r["stats"]
        print(f"{i:<3} {r['params']:<50} {s['total']:>6} {s['win_rate']:>5.1f}% "
              f"{s['total_pips']:>8.1f} {s['profit_factor']:>5.2f} "
              f"{s['avg_rr']:>5.2f} {s['expectancy_pips']:>6.1f}p {s['max_drawdown_pips']:>6.1f}p")

    if results:
        best = results[0]
        s = best["stats"]
        print(f"\n  BEST: {best['params']}")
        print(f"  {s['total']} trades | {s['win_rate']}% WR | {s['total_pips']} pips | PF {s['profit_factor']} | Expect {s['expectancy_pips']}p/trade")
        print(f"  Avg Win: {s['avg_win_pips']}p | Avg Loss: {s['avg_loss_pips']}p | Max DD: {s['max_drawdown_pips']}p")

        # Show last 10 trades
        print(f"\n  Last 10 trades:")
        print(f"  {'Date':<12} {'Type':<5} {'Entry':>8} {'PnL':>8} {'Result':<5}")
        for t in best["trades"][-10:]:
            date_str = t["entry_date"].strftime("%Y-%m-%d") if hasattr(t["entry_date"], "strftime") else str(t["entry_date"])[:10]
            print(f"  {date_str:<12} {t['type']:<5} {t['entry']:>8.5f} {t['pnl']:>7.1f}p {t['result']:<5}")


if __name__ == "__main__":
    print("Fetching EUR/USD 5Y daily data...")
    df = fetch_eurusd_data(period="5y")
    df = add_indicators(df)
    print(f"Data loaded: {len(df)} bars")

    ema_results = optimize_ema_crossover(df)
    bb_results = optimize_bb_squeeze(df)
    trend_results = optimize_trend(df)

    print_results("EMA CROSSOVER (9/21)", ema_results)
    print_results("BB SQUEEZE", bb_results)
    print_results("OPTIMIZED TREND", trend_results)

    # Final comparison of best from each
    print(f"\n{'='*100}")
    print(f"  FINAL COMPARISON - BEST FROM EACH STRATEGY")
    print(f"{'='*100}")
    all_best = []
    if ema_results:
        all_best.append(("EMA Crossover", ema_results[0]))
    if bb_results:
        all_best.append(("BB Squeeze", bb_results[0]))
    if trend_results:
        all_best.append(("Optimized Trend", trend_results[0]))

    all_best.sort(key=lambda x: x[1]["stats"]["total_pips"], reverse=True)
    print(f"{'Strategy':<20} {'Params':<45} {'Trades':>6} {'WR%':>6} {'Pips':>9} {'PF':>6} {'Expect':>7}")
    print(f"{'-'*100}")
    for name, r in all_best:
        s = r["stats"]
        print(f"{name:<20} {r['params']:<45} {s['total']:>6} {s['win_rate']:>5.1f}% "
              f"{s['total_pips']:>8.1f} {s['profit_factor']:>5.2f} {s['expectancy_pips']:>6.1f}p")
