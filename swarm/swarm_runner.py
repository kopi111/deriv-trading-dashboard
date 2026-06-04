"""
15-agent swarm runner for the Deriv Trading Dashboard.

Runtime: headless `claude -p` workers driven from Python (the house style).
Phase A: 10 backtest agents, one work unit each -> swarm_out/<unit>.json + .md
Phase B:  5 upgrade agents that consume Phase A output and upgrade the project.

Workers run with bypassPermissions so they can run python and edit files
without prompting. Concurrency is capped to keep data providers happy.
"""

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "swarm_out"
LOGS = OUT / "logs"
MODEL = "sonnet"
MAX_PARALLEL = 4

PHASE_A = [
    "w01-vol75", "w02-vol100", "w03-vol-mid", "w04-vol-1s", "w05-step",
    "w06-metals", "w07-fx-commodity", "w08-fx-majors", "w09-crypto", "w10-equity",
]

BACKTEST_PROMPT = """You are a quantitative backtest agent in a swarm. Working directory is the repo root.

Your work unit is: {unit}

Steps (do exactly this, nothing else):
1. Run: python3 swarm/run_instrument.py {unit}
   This grid-searches EMA/RSI/MACD strategies and writes swarm_out/{unit}.json.
2. Read swarm_out/{unit}.json.
3. Write swarm_out/{unit}.md — a concise markdown report. For EACH instrument in the unit include:
   - Instrument name and symbol, number of candles tested
   - BEST strategy: family + parameters (EMA fast/slow, or RSI period/oversold/overbought, or MACD)
   - Risk management: Stop Loss = N x ATR(14), Take Profit = M x ATR(14)
   - Plain-English entry rules (BUY and SELL)
   - Backtest metrics: trades, win rate, total return %, profit factor, expectancy %, max drawdown %, sharpe
   - One sentence on WHY it works for this instrument
   If an instrument has an "error" field, note the data error instead.
Keep it factual and tight. No preamble, no disclaimer boilerplate.
"""

PHASE_B = {
    "w11-synthesis": """You are the synthesis agent. Working directory is the repo root.
Read every file matching swarm_out/w0*.json and swarm_out/w10*.json.
Produce TWO outputs:
1. swarm_out/leaderboard.json — a JSON array, one object per instrument that has a 'best' result, with keys:
   symbol, label, source, strategy, params (the full params object), trades, win_rate,
   total_return_pct, profit_factor, expectancy_pct, max_drawdown_pct, sharpe, score.
   Sort the array by score descending.
2. swarm_out/LEADERBOARD.md — a markdown ranking table of all instruments (best strategy each),
   sorted by score, plus a short 'Top 3 picks' section naming the single best overall strategy,
   the safest (lowest drawdown with PF>1.3), and the most profitable (highest total return).
Be precise; pull numbers straight from the JSON.""",

    "w12-rsi-page": """You are a frontend upgrade agent. Working directory is the repo root.
Read swarm_out/leaderboard.json. In rsi-strategy.html, locate the optimized-settings data/table
and update it so the per-instrument RSI settings and backtest stats (win rate, profit factor, sharpe,
trades) reflect the NEW backtested numbers from leaderboard.json for any RSI-strategy instruments.
Only change the data values and any visible 'last backtested' date to today (2026-06-04).
Do NOT restructure the page or break its theming/JS. Preserve existing formatting and indentation.""",

    "w13-leaderboard-page": """You are a frontend agent. Working directory is the repo root.
Create a NEW page strategy-leaderboard.html that displays the backtested strategy leaderboard.
- Match the existing site's look: open index.html and rsi-strategy.html to copy the header, nav links,
  dark-purple theme, fonts and card/table styling. Add a 'Leaderboard' nav link consistent with the others.
- Embed the contents of swarm_out/leaderboard.json as a JS const (read the file and inline it) so the page
  works on GitHub Pages with no backend.
- Render a sortable ranked table: rank, instrument, strategy, params summary, win rate, profit factor,
  total return %, max drawdown %, sharpe, score. Highlight the #1 row.
- Add the same theme switcher behavior other pages use if trivial; otherwise keep default dark theme.
Make it production-quality and self-contained.""",

    "w14-docs": """You are a docs agent. Working directory is the repo root.
Read swarm_out/LEADERBOARD.md and swarm_out/leaderboard.json.
1. Update README.md: refresh the strategy/win-rate tables and the 'Tips / Best performing' lines to match
   the new backtest results, add a short 'Strategy Leaderboard' section pointing to strategy-leaderboard.html,
   and update any dates to 2026-06-04. Keep the existing structure and tone.
2. Regenerate IMPORTANT_DERIV_STRATEGIES.txt so its per-instrument strategy blocks and the QUICK REFERENCE
   TABLE reflect the new best strategies and metrics for the Deriv synthetic indices (R_*, 1HZ*, stpRNG).
Keep factual; pull numbers from the JSON. Do not add AI attribution.""",

    "w15-quality": """You are a code-quality agent. Working directory is the repo root.
1. Create requirements.txt pinning the Python deps actually imported across the repo's .py files
   (pandas, numpy, yfinance, ta, websockets, websocket-client as used). Check imports with grep first.
2. Create swarm/README.md explaining the swarm: engine.py, instruments.py, run_instrument.py,
   swarm_runner.py, and how to re-run (python3 swarm/swarm_runner.py). Note outputs land in swarm_out/.
3. Add a one-paragraph 'Risk Disclaimer' note to swarm/README.md (educational use, past performance, demo first).
Do not modify other files. Keep it concise.""",
}


def run_worker(worker_id, prompt):
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path = LOGS / f"{worker_id}.log"
    cmd = [
        "claude", "-p", prompt,
        "--model", MODEL,
        "--permission-mode", "bypassPermissions",
        "--add-dir", str(REPO),
    ]
    start = time.monotonic()
    with log_path.open("w") as log:
        proc = subprocess.run(cmd, cwd=str(REPO), stdout=log,
                              stderr=subprocess.STDOUT, text=True)
    elapsed = round(time.monotonic() - start, 1)
    return worker_id, proc.returncode, elapsed


def run_phase(name, jobs):
    print(f"\n=== PHASE {name}: {len(jobs)} agents ===", flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        futures = {pool.submit(run_worker, wid, prompt): wid for wid, prompt in jobs}
        for future in as_completed(futures):
            wid, code, elapsed = future.result()
            status = "ok" if code == 0 else f"exit {code}"
            print(f"  [{status:>7}] {wid}  ({elapsed}s)", flush=True)
            results.append((wid, code))
    return results


def main():
    OUT.mkdir(exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else "all"

    if only in ("all", "a"):
        jobs_a = [(unit, BACKTEST_PROMPT.format(unit=unit)) for unit in PHASE_A]
        run_phase("A (backtest)", jobs_a)
    if only in ("all", "b"):
        # Synthesis first: the other Phase B agents read swarm_out/leaderboard.json.
        run_phase("B1 (synthesis)", [("w11-synthesis", PHASE_B["w11-synthesis"])])
        consumers = [(wid, p) for wid, p in PHASE_B.items() if wid != "w11-synthesis"]
        run_phase("B2 (upgrade)", consumers)

    print("\nSwarm complete. Outputs in swarm_out/ (logs in swarm_out/logs/).")


if __name__ == "__main__":
    main()
