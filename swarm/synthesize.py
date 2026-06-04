"""Build an honest leaderboard ranked by out-of-sample performance.

Reads every swarm_out/<unit>.json (validated engine output) and writes
swarm_out/leaderboard.json + swarm_out/LEADERBOARD.md, ranking by walk-forward
out-of-sample profit factor and flagging which strategies survived validation.
"""

import glob
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "swarm_out"


def param_summary(p):
    if p["strategy"] == "EMA":
        return f"EMA {p['fast']}/{p['slow']}"
    if p["strategy"] == "RSI":
        return f"RSI {p['period']} ({p['oversold']}/{p['overbought']})"
    return "MACD"


def collect():
    rows = []
    for path in glob.glob(str(OUT / "w*.json")):
        data = json.loads(Path(path).read_text())
        for rec in data.get("instruments", []):
            if "best" not in rec:
                continue
            ho = (rec.get("holdout") or {}).get("out_of_sample")
            wf = (rec.get("walk_forward") or {}).get("out_of_sample")
            ins = rec["best"]["result"]
            rows.append({
                "symbol": rec["symbol"],
                "label": rec["label"],
                "source": rec["source"],
                "strategy": rec["best"]["params"]["strategy"],
                "params": rec["best"]["params"],
                "params_summary": param_summary(rec["best"]["params"]),
                "cost_pct": round(rec.get("cost", 0) * 100, 4),
                "in_sample": ins,
                "holdout": ho,
                "walk_forward": wf,
                "survives": rec.get("verdict", {}).get("survives", False),
                "reasons": rec.get("verdict", {}).get("reasons", []),
            })
    # rank: survivors first, then by walk-forward profit factor
    def key(r):
        wf_pf = (r["walk_forward"] or {}).get("profit_factor", 0)
        return (r["survives"], wf_pf)
    rows.sort(key=key, reverse=True)
    return rows


def md(rows):
    lines = [
        "# Honest Strategy Leaderboard — Out-of-Sample Validated",
        "",
        "Every strategy is optimized only on training data, then judged on data it never saw,",
        "after deducting spread/slippage costs. **Survivors stay profitable out-of-sample AND",
        "on walk-forward.** In-sample numbers are shown only to expose the overfitting gap.",
        "",
        "| Verdict | Instrument | Strategy | In-sample Ret% | Holdout PF / Ret% / trades | Walk-forward PF / Ret% / trades |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        ho = r["holdout"]; wf = r["walk_forward"]
        ho_s = f"{ho['profit_factor']} / {ho['total_return_pct']}% / {ho['trades']}" if ho else "n/a"
        wf_s = f"{wf['profit_factor']} / {wf['total_return_pct']}% / {wf['trades']}" if wf else "n/a"
        verdict = "✅ SURVIVES" if r["survives"] else "❌ fails"
        lines.append(f"| {verdict} | {r['label']} ({r['symbol']}) | {r['params_summary']} "
                     f"| {r['in_sample']['total_return_pct']}% | {ho_s} | {wf_s} |")
    survivors = [r for r in rows if r["survives"]]
    lines += ["", f"## {len(survivors)} of {len(rows)} strategies survived validation", ""]
    for r in survivors:
        wf = r["walk_forward"]
        note = " ⚠️ synthetic RNG — treat any 'edge' with extreme skepticism" if r["source"] == "deriv" else ""
        lines.append(f"- **{r['label']}** ({r['params_summary']}): walk-forward PF "
                     f"{wf['profit_factor']}, +{wf['total_return_pct']}% over {wf['trades']} unseen trades.{note}")
    lines += ["", "Everything else overfits: it looks profitable on the data it was tuned on, "
              "but loses money once costs are charged and it trades data it never saw."]
    return "\n".join(lines)


def main():
    rows = collect()
    (OUT / "leaderboard.json").write_text(json.dumps(rows, indent=2))
    (OUT / "LEADERBOARD.md").write_text(md(rows))
    survivors = [r for r in rows if r["survives"]]
    print(f"{len(survivors)}/{len(rows)} survived. Wrote leaderboard.json + LEADERBOARD.md")
    for r in rows:
        wf = r["walk_forward"]
        print(f"  {'OK ' if r['survives'] else 'XX '}{r['symbol']:9} wf_PF="
              f"{(wf or {}).get('profit_factor','n/a')}")


if __name__ == "__main__":
    main()
