"""Catalog of instruments grouped into swarm work units."""

DERIV = "deriv"
YAHOO = "yahoo"

INSTRUMENTS = {
    # Deriv synthetic indices (WebSocket, hourly)
    "R_75":     {"label": "Volatility 75 Index",      "source": DERIV, "timeframe": "1h"},
    "R_100":    {"label": "Volatility 100 Index",     "source": DERIV, "timeframe": "1h"},
    "R_50":     {"label": "Volatility 50 Index",      "source": DERIV, "timeframe": "1h"},
    "R_25":     {"label": "Volatility 25 Index",      "source": DERIV, "timeframe": "1h"},
    "R_10":     {"label": "Volatility 10 Index",      "source": DERIV, "timeframe": "1h"},
    "1HZ75V":   {"label": "Volatility 75 (1s) Index", "source": DERIV, "timeframe": "1h"},
    "1HZ100V":  {"label": "Volatility 100 (1s) Index","source": DERIV, "timeframe": "1h"},
    "stpRNG":   {"label": "Step Index",               "source": DERIV, "timeframe": "1h"},
    # Market instruments (yfinance, daily)
    "GC=F":     {"label": "Gold (XAU/USD)",   "source": YAHOO, "period": "5y", "interval": "1d"},
    "CL=F":     {"label": "Crude Oil (WTI)",  "source": YAHOO, "period": "5y", "interval": "1d"},
    "AUDUSD=X": {"label": "AUD/USD",          "source": YAHOO, "period": "5y", "interval": "1d"},
    "EURUSD=X": {"label": "EUR/USD",          "source": YAHOO, "period": "5y", "interval": "1d"},
    "GBPUSD=X": {"label": "GBP/USD",          "source": YAHOO, "period": "5y", "interval": "1d"},
    "USDJPY=X": {"label": "USD/JPY",          "source": YAHOO, "period": "5y", "interval": "1d"},
    "BTC-USD":  {"label": "Bitcoin (BTC/USD)","source": YAHOO, "period": "5y", "interval": "1d"},
    "ETH-USD":  {"label": "Ethereum (ETH/USD)","source": YAHOO, "period": "5y", "interval": "1d"},
    "^GSPC":    {"label": "S&P 500",          "source": YAHOO, "period": "5y", "interval": "1d"},
}

# Round-trip trading cost (spread + slippage) as a fraction of entry price,
# charged on every trade. Conservative retail estimates per asset class.
COST = {
    "deriv":  0.0005,   # synthetic indices: ~0.05% round trip
    "yahoo":  0.0002,   # fx / commodities / equity proxy: ~0.02% round trip
}
COST_OVERRIDE = {
    "BTC-USD": 0.0015,  # crypto spreads are wider
    "ETH-USD": 0.0020,
    "AUDUSD=X": 0.00015,
    "EURUSD=X": 0.00012,
    "GBPUSD=X": 0.00015,
    "USDJPY=X": 0.00015,
}

def cost_for(symbol):
    if symbol in COST_OVERRIDE:
        return COST_OVERRIDE[symbol]
    return COST[INSTRUMENTS[symbol]["source"]]


# Work units: each backtest worker owns one group of instruments.
WORK_UNITS = {
    "w01-vol75":      ["R_75"],
    "w02-vol100":     ["R_100"],
    "w03-vol-mid":    ["R_50", "R_25", "R_10"],
    "w04-vol-1s":     ["1HZ75V", "1HZ100V"],
    "w05-step":       ["stpRNG"],
    "w06-metals":     ["GC=F", "CL=F"],
    "w07-fx-commodity":["AUDUSD=X"],
    "w08-fx-majors":  ["EURUSD=X", "GBPUSD=X", "USDJPY=X"],
    "w09-crypto":     ["BTC-USD", "ETH-USD"],
    "w10-equity":     ["^GSPC"],
}
