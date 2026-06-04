# Honest Strategy Leaderboard — Out-of-Sample Validated

Every strategy is optimized only on training data, then judged on data it never saw,
after deducting spread/slippage costs. **Survivors stay profitable out-of-sample AND
on walk-forward.** In-sample numbers are shown only to expose the overfitting gap.

| Verdict | Instrument | Strategy | In-sample Ret% | Holdout PF / Ret% / trades | Walk-forward PF / Ret% / trades |
|---|---|---|---|---|---|
| ✅ SURVIVES | Crude Oil (WTI) (CL=F) | RSI 5 (30/65) | 127.0% | 2.82 / 59.4% / 50 | 1.86 / 99.2% / 132 |
| ✅ SURVIVES | Volatility 75 Index (R_75) | EMA 5/21 | 112.2% | 1.53 / 36.8% / 75 | 1.24 / 53.9% / 400 |
| ✅ SURVIVES | Gold (XAU/USD) (GC=F) | RSI 9 (30/65) | 35.1% | 1.13 / 4.0% / 27 | 1.19 / 12.3% / 86 |
| ✅ SURVIVES | Ethereum (ETH/USD) (ETH-USD) | RSI 14 (30/65) | 151.5% | 1.18 / 20.0% / 21 | 1.09 / 25.0% / 76 |
| ❌ fails | Volatility 100 (1s) Index (1HZ100V) | RSI 5 (25/75) | 156.0% | 0.92 / -16.8% / 114 | 1.06 / 30.0% / 330 |
| ❌ fails | Volatility 100 Index (R_100) | RSI 9 (25/70) | 196.3% | 0.46 / -88.6% / 63 | 0.93 / -19.3% / 352 |
| ❌ fails | Volatility 50 Index (R_50) | MACD | 57.0% | 0.97 / -2.3% / 89 | 0.92 / -13.6% / 249 |
| ❌ fails | Volatility 75 (1s) Index (1HZ75V) | EMA 5/21 | 19.3% | 0.95 / -8.9% / 169 | 0.89 / -37.1% / 375 |
| ❌ fails | S&P 500 (^GSPC) | MACD | 22.7% | 0.83 / -6.8% / 42 | 0.88 / -7.8% / 70 |
| ❌ fails | EUR/USD (EURUSD=X) | RSI 14 (25/75) | 12.2% | 0.89 / -0.8% / 21 | 0.86 / -3.9% / 68 |
| ❌ fails | USD/JPY (USDJPY=X) | EMA 5/21 | 19.5% | 1.28 / 2.7% / 17 | 0.86 / -6.3% / 78 |
| ❌ fails | Volatility 25 Index (R_25) | EMA 9/21 | 20.8% | 0.94 / -1.8% / 69 | 0.85 / -15.7% / 285 |
| ❌ fails | Volatility 10 Index (R_10) | EMA 9/50 | 3.2% | 0.75 / -2.9% / 54 | 0.83 / -4.9% / 163 |
| ❌ fails | Bitcoin (BTC/USD) (BTC-USD) | EMA 9/21 | 111.3% | 0.46 / -58.2% / 43 | 0.79 / -38.1% / 85 |
| ❌ fails | Step Index (stpRNG) | EMA 5/21 | -2.8% | 0.94 / -0.5% / 56 | 0.76 / -5.8% / 151 |
| ❌ fails | GBP/USD (GBPUSD=X) | RSI 14 (20/80) | 7.5% | 1.29 / 3.2% / 18 | 0.72 / -9.7% / 43 |
| ❌ fails | AUD/USD (AUDUSD=X) | RSI 5 (20/80) | 13.4% | 1.48 / 2.7% / 19 | 0.59 / -23.7% / 64 |

## 4 of 17 strategies survived validation

- **Crude Oil (WTI)** (RSI 5 (30/65)): walk-forward PF 1.86, +99.2% over 132 unseen trades.
- **Volatility 75 Index** (EMA 5/21): walk-forward PF 1.24, +53.9% over 400 unseen trades. ⚠️ synthetic RNG — treat any 'edge' with extreme skepticism
- **Gold (XAU/USD)** (RSI 9 (30/65)): walk-forward PF 1.19, +12.3% over 86 unseen trades.
- **Ethereum (ETH/USD)** (RSI 14 (30/65)): walk-forward PF 1.09, +25.0% over 76 unseen trades.

Everything else overfits: it looks profitable on the data it was tuned on, but loses money once costs are charged and it trades data it never saw.