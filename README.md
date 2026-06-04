# Deriv Trading Dashboard

Live trading signals for Volatility Indices using real-time Deriv API data.

**Live Site:** https://kopi111.github.io/deriv-trading-dashboard/

---

## Pages

### 1. Live Dashboard (index.html)
Real-time candlestick chart with technical indicators.

**Features:**
- Live price updates via WebSocket
- Candlestick chart with zoom/pan
- RSI indicator below chart
- Multiple volatility index pairs (V10, V25, V50, V75, V100)
- Timeframe selection (1M, 5M, 15M, 1H, 4H, 1D)
- 5 color themes

**How to Use:**
1. Select a trading pair from the dropdown
2. Choose your timeframe
3. Watch live candles form in real-time
4. RSI indicator shows overbought (>70) and oversold (<30) zones

---

### 2. Price Action Analysis (price-action-analysis.html)
AI-powered price action trading signals.

**Features:**
- Analyzes trend direction (Higher Highs/Lows)
- Detects Break of Structure (BOS)
- Identifies Support & Resistance levels
- Recognizes candlestick patterns (Engulfing, Pin Bars, Morning/Evening Star)
- Calculates Entry, Stop Loss, Take Profit levels
- Confidence score for each signal

**How to Use:**
1. Wait for data to load (connects to Deriv API)
2. Cards show each index with trading bias:
   - **Strong Buy** (green) - High confidence long
   - **Buy** (light green) - Moderate long
   - **Neutral** (yellow) - No clear direction
   - **Sell** (orange) - Moderate short
   - **Strong Sell** (red) - High confidence short
3. Click any card to open chart with trade levels
4. Use timeframe buttons to analyze different periods
5. Click "Refresh" to get latest analysis

**Trade Levels Shown:**
- Entry (cyan line)
- Stop Loss (red line)
- Take Profit (green line)
- Support (yellow dashed)
- Resistance (orange dashed)

---

### 3. RSI Strategy Signals (rsi-strategy.html)
Backtested RSI strategy with optimized settings per index.

**Best Backtested Settings (15-Min Timeframe) — updated 2026-06-04:**
| Index | Best Strategy | Parameters | Win Rate | Return |
|-------|---------------|------------|----------|--------|
| V10   | EMA Crossover | Fast 9 / Slow 50, SL 2.0×ATR, TP 1.5×ATR | 67.6% | +10.2% |
| V25   | EMA Crossover | Fast 5 / Slow 21, SL 3.0×ATR, TP 1.5×ATR | 73.0% | +26.2% |
| V50   | MACD          | Default, SL 3.0×ATR, TP 2.0×ATR           | 65.6% | +67.1% |
| V75   | EMA Crossover | Fast 5 / Slow 21, SL 3.0×ATR, TP 1.5×ATR | 75.7% | +70.4% |
| V100  | RSI (9)       | Oversold 25 / Overbought 70, SL 3.0×ATR, TP 2.0×ATR | 66.6% | +152.0% |

**How to Use:**
1. Wait for RSI signals to load
2. Look for active signals:
   - **BUY** - RSI dropped below oversold level
   - **SELL** - RSI rose above overbought level
   - **WAIT** - RSI in neutral zone
3. Card shows:
   - Current RSI value with visual bar
   - Optimized settings for that index
   - Entry, SL, TP levels (when signal active)
   - Backtest performance stats
4. Click card to view chart with trade levels

**Backtest Stats Explained:**
- **Win Rate** - Percentage of winning trades
- **PF (Profit Factor)** - Gross profit / Gross loss (>1 is profitable)
- **Sharpe** - Risk-adjusted return (higher is better)
- **Trades** - Number of trades in backtest

---

### 4. Strategy Leaderboard (strategy-leaderboard.html)
Full ranked results from the multi-instrument backtest optimiser.

Shows the single best-performing strategy per instrument, sorted by composite score (win rate × return × Sharpe ÷ drawdown).

**Top 5 by composite score (2026-06-04 backtest):**
| Rank | Instrument | Strategy | Win Rate | Return | Sharpe | Score |
|------|-----------|----------|----------|--------|--------|-------|
| 1 | Volatility 100 (1s) — 1HZ100V | RSI(5, 25/75) | 54.7% | +470.6% | 2.52 | 237.89 |
| 2 | Crude Oil (WTI) — CL=F | RSI(5, 30/65) | 85.5% | +154.7% | 3.28 | 132.46 |
| 3 | Volatility 100 — R_100 | RSI(9, 25/70) | 66.6% | +152.0% | 2.53 | 104.22 |
| 4 | Volatility 75 — R_75 | EMA(5/21) | 75.7% | +70.4% | 2.73 | 81.32 |
| 5 | Bitcoin — BTC-USD | EMA(9/21) | 84.6% | +159.8% | 2.84 | 74.53 |

Full 17-instrument leaderboard: **[strategy-leaderboard.html](strategy-leaderboard.html)**

---

## Themes

Click theme buttons in header to switch:
- Dark Purple (default)
- Dark Blue
- Dark Green
- Light
- Midnight

Theme preference is saved in browser.

---

## Tips

1. **Highest return (Deriv):** 1HZ100V — RSI(5, 25/75) → +470.6% return, 574 trades, 54.7% win rate. Note: 82.5% max drawdown; strict position sizing required.
2. **Best standard Volatility Index:** R_100 — RSI(9, 25/70) → +152.0% return, 66.6% win rate, Sharpe 2.53.
3. **Safest (lowest drawdown):** R_10 — EMA(9/50) → only 1.42% max drawdown, Sharpe 3.16, 67.6% win rate.
4. **Best win rate:** R_75 — EMA(5/21) → 75.7% win rate, +70.4% return, 10.1% max drawdown.
5. **Use multiple confirmations:** Combine RSI/EMA signals with Price Action analysis.
6. **Risk management:** Always use the suggested Stop Loss levels; risk ≤2% of account per trade.
7. **Timeframes:** Backtest data is on 15-minute candles (updated 2026-06-04).

---

## Requirements

- Modern web browser (Chrome, Firefox, Edge, Safari)
- Internet connection for live Deriv API data
- No installation needed - runs in browser

---

## Disclaimer

This tool is for educational purposes only. Trading involves risk. Past performance does not guarantee future results. Always trade responsibly.
