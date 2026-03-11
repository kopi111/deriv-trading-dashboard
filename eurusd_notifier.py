"""
EUR/USD Trade Signal Notifier
Monitors EUR/USD and sends Telegram alerts when optimized strategies trigger.

SETUP:
1. Open Telegram, search @BotFather
2. Send /newbot, follow prompts, copy the BOT TOKEN
3. Search your new bot and send /start
4. Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
5. Find your chat_id in the response
6. Set environment variables:
   export TELEGRAM_BOT_TOKEN="your_token_here"
   export TELEGRAM_CHAT_ID="your_chat_id_here"

RUN:
  python3 eurusd_notifier.py          # one-time check
  python3 eurusd_notifier.py --loop   # continuous monitoring (checks every 15 min)
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime
from backtest_eurusd import fetch_eurusd_data, add_indicators


# --- Telegram ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_telegram(message):
    """Send message via Telegram Bot API."""
    if not BOT_TOKEN or not CHAT_ID:
        print("[!] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        print(f"[ALERT] {message}")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }).encode()

    try:
        req = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get("ok"):
            print(f"[OK] Telegram sent")
            return True
        else:
            print(f"[!] Telegram error: {result}")
            return False
    except Exception as e:
        print(f"[!] Telegram failed: {e}")
        return False


# --- Signal Detection ---

def check_optimized_trend(df, i):
    """EMA=20, ADX>25, RSI(35/65), SL=3.5x ATR, TP=2.0x ATR"""
    row = df.iloc[i]
    prev = df.iloc[i - 1]

    # Use EMA_21 as closest to EMA_20 (already calculated)
    ema_now = row["EMA_21"]
    ema_prev = prev["EMA_21"]

    uptrend = row["Close"] > ema_now and ema_now > ema_prev
    downtrend = row["Close"] < ema_now and ema_now < ema_prev

    if uptrend and row["ADX"] > 25 and 35 < row["RSI"] < 65:
        sl = row["Close"] - row["ATR"] * 3.5
        tp = row["Close"] + row["ATR"] * 2.0
        return "BUY", row["Close"], sl, tp
    elif downtrend and row["ADX"] > 25 and 35 < row["RSI"] < 65:
        sl = row["Close"] + row["ATR"] * 3.5
        tp = row["Close"] - row["ATR"] * 2.0
        return "SELL", row["Close"], sl, tp
    return None, 0, 0, 0


def check_ema_crossover(df, i):
    """EMA 9/21 crossover, SL=3.0x ATR, TP=3.0x ATR"""
    row = df.iloc[i]
    prev = df.iloc[i - 1]

    if (prev["EMA_9"] <= prev["EMA_21"] and
            row["EMA_9"] > row["EMA_21"] and
            row["Close"] > row["EMA_50"]):
        sl = row["Close"] - row["ATR"] * 3.0
        tp = row["Close"] + row["ATR"] * 3.0
        return "BUY", row["Close"], sl, tp
    elif (prev["EMA_9"] >= prev["EMA_21"] and
          row["EMA_9"] < row["EMA_21"] and
          row["Close"] < row["EMA_50"]):
        sl = row["Close"] + row["ATR"] * 3.0
        tp = row["Close"] - row["ATR"] * 3.0
        return "SELL", row["Close"], sl, tp
    return None, 0, 0, 0


def check_bb_squeeze(df, i):
    """BB Squeeze breakout, SL=1.0x ATR, TP=1.0x ATR"""
    row = df.iloc[i]
    prev = df.iloc[i - 1]

    # Check if was squeezed recently
    bb_width_vals = df["BB_Width"].iloc[max(0, i-100):i]
    if len(bb_width_vals) < 20:
        return None, 0, 0, 0

    bb_min = bb_width_vals.min()
    bb_max = bb_width_vals.max()
    bb_range = bb_max - bb_min if bb_max > bb_min else 1e-10

    was_squeezed = False
    for j in range(1, 4):
        if i - j >= 0:
            pct = (df.iloc[i - j]["BB_Width"] - bb_min) / bb_range
            if pct < 0.25:
                was_squeezed = True
                break

    if not was_squeezed:
        return None, 0, 0, 0

    if (row["Close"] > row["BB_Upper"] and
            row["EMA_50"] > prev["EMA_50"] and row["RSI"] > 50):
        sl = row["BB_Mid"] - row["ATR"] * 0.5
        tp = row["Close"] + row["ATR"] * 1.0
        return "BUY", row["Close"], sl, tp
    elif (row["Close"] < row["BB_Lower"] and
          row["EMA_50"] < prev["EMA_50"] and row["RSI"] < 50):
        sl = row["BB_Mid"] + row["ATR"] * 0.5
        tp = row["Close"] - row["ATR"] * 1.0
        return "SELL", row["Close"], sl, tp
    return None, 0, 0, 0


def format_alert(strategy, signal, entry, sl, tp, row):
    """Format a trade alert message."""
    sl_pips = abs(entry - sl) / 0.0001
    tp_pips = abs(tp - entry) / 0.0001
    rr = tp_pips / sl_pips if sl_pips > 0 else 0

    emoji_dir = "🟢" if signal == "BUY" else "🔴"
    strength = ""
    if row["ADX"] > 30:
        strength = "💪 STRONG TREND"
    elif row["ADX"] > 25:
        strength = "📈 TRENDING"

    msg = f"""
{emoji_dir} *EUR/USD {signal} SIGNAL*
━━━━━━━━━━━━━━━━━━
📊 Strategy: *{strategy}*
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}

💰 Entry: *{entry:.5f}*
🛑 Stop Loss: {sl:.5f} ({sl_pips:.0f} pips)
🎯 Take Profit: {tp:.5f} ({tp_pips:.0f} pips)
📐 Risk:Reward: 1:{rr:.1f}

📉 RSI: {row['RSI']:.1f}
📊 ADX: {row['ADX']:.1f} {strength}
📏 ATR: {row['ATR']*10000:.1f} pips
━━━━━━━━━━━━━━━━━━
⚠️ _Risk max 1-2% per trade_"""
    return msg.strip()


def scan_signals():
    """Fetch latest data and check all 3 strategies."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Scanning EUR/USD...")

    try:
        df = fetch_eurusd_data(period="1y", interval="1d")
        df = add_indicators(df)
    except Exception as e:
        print(f"[!] Data fetch error: {e}")
        return []

    i = len(df) - 1  # latest bar
    row = df.iloc[i]
    date_str = row.name.strftime("%Y-%m-%d") if hasattr(row.name, "strftime") else str(row.name)[:10]

    print(f"    Latest bar: {date_str} | Close: {row['Close']:.5f} | RSI: {row['RSI']:.1f} | ADX: {row['ADX']:.1f}")

    alerts = []

    strategies = [
        ("Optimized Trend", check_optimized_trend),
        ("EMA Crossover (9/21)", check_ema_crossover),
        ("BB Squeeze", check_bb_squeeze),
    ]

    for name, check_fn in strategies:
        signal, entry, sl, tp = check_fn(df, i)
        if signal:
            msg = format_alert(name, signal, entry, sl, tp, row)
            alerts.append(msg)
            print(f"    >>> {name}: {signal} @ {entry:.5f}")
        else:
            print(f"    --- {name}: No signal")

    return alerts


def main():
    loop_mode = "--loop" in sys.argv

    if not BOT_TOKEN or not CHAT_ID:
        print("=" * 50)
        print("  TELEGRAM SETUP REQUIRED")
        print("=" * 50)
        print("1. Open Telegram → search @BotFather")
        print("2. Send /newbot → follow prompts")
        print("3. Copy the bot token")
        print("4. Open your bot in Telegram → send /start")
        print(f"5. Visit: https://api.telegram.org/bot<TOKEN>/getUpdates")
        print("6. Copy your chat_id from the response")
        print("7. Run:")
        print('   export TELEGRAM_BOT_TOKEN="your_token"')
        print('   export TELEGRAM_CHAT_ID="your_chat_id"')
        print("=" * 50)
        print("\nRunning in console-only mode...\n")

    if loop_mode:
        print("Running in LOOP mode (checks every 15 minutes)")
        print("Press Ctrl+C to stop\n")

        # Send startup message
        send_telegram("🤖 *EUR/USD Notifier Started*\nMonitoring: Optimized Trend, EMA Crossover, BB Squeeze\nInterval: 15 minutes")

        while True:
            try:
                alerts = scan_signals()
                for msg in alerts:
                    send_telegram(msg)

                if not alerts:
                    print("    No signals. Sleeping 15 min...")

                time.sleep(900)  # 15 minutes
            except KeyboardInterrupt:
                print("\nStopped.")
                send_telegram("🛑 EUR/USD Notifier stopped")
                break
            except Exception as e:
                print(f"[!] Error: {e}")
                time.sleep(60)
    else:
        # One-time check
        alerts = scan_signals()
        for msg in alerts:
            send_telegram(msg)
        if not alerts:
            print("\nNo active signals right now.")
            send_telegram("📊 EUR/USD scan complete — no signals at this time.")


if __name__ == "__main__":
    main()
