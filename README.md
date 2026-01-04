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

**Optimized Settings (15-Min Timeframe):**
| Index | RSI Period | Buy Below | Sell Above | Win Rate |
|-------|------------|-----------|------------|----------|
| V10   | 5          | 20        | 80         | 52.8%    |
| V25   | 5          | 20        | 75         | 50.0%    |
| V50   | 9          | 35        | 65         | 53.7%    |
| V75   | 5          | 25        | 75         | 50.6%    |
| V100  | 5          | 25        | 80         | 52.6%    |

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

1. **Best performing index:** V50 with 53.7% win rate
2. **Best risk-adjusted:** V75 with 1.53 Sharpe ratio
3. **Use multiple confirmations:** Combine RSI signals with Price Action analysis
4. **Risk management:** Always use the suggested Stop Loss levels
5. **Timeframes:** 15-minute timeframe was used for backtesting

---

## Requirements

- Modern web browser (Chrome, Firefox, Edge, Safari)
- Internet connection for live Deriv API data
- No installation needed - runs in browser

---

## Disclaimer

This tool is for educational purposes only. Trading involves risk. Past performance does not guarantee future results. Always trade responsibly.
