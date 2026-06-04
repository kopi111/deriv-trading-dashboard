"""Run a grid search for every instrument in one work unit and emit JSON.

Usage: python3 swarm/run_instrument.py <work-unit-id>
Writes swarm_out/<work-unit-id>.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine
from instruments import INSTRUMENTS, WORK_UNITS, cost_for

OUT_DIR = Path(__file__).resolve().parent.parent / "swarm_out"


def load(symbol):
    spec = INSTRUMENTS[symbol]
    if spec["source"] == "deriv":
        return engine.fetch_deriv(symbol, spec["timeframe"])
    return engine.fetch_yahoo(symbol, spec["period"], spec["interval"])


def run_unit(unit_id):
    symbols = WORK_UNITS[unit_id]
    findings = []
    for symbol in symbols:
        spec = INSTRUMENTS[symbol]
        cost = cost_for(symbol)
        record = {"symbol": symbol, "label": spec["label"], "source": spec["source"], "cost": cost}
        try:
            frame = load(symbol)
            ranked = engine.grid_search(frame, cost=cost)
            ho = engine.holdout(frame, cost=cost)
            wf = engine.walk_forward(frame, cost=cost)
            record["candles"] = len(frame)
            record["best"] = ranked[0]               # in-sample, cost-adjusted
            record["holdout"] = ho                    # 70/30 train/test
            record["walk_forward"] = wf               # anchored walk-forward
            record["verdict"] = engine.verdict(ho, wf)
        except Exception as exc:  # noqa: BLE001 - report any failure as data
            record["error"] = f"{type(exc).__name__}: {exc}"
        findings.append(record)
    return {"unit": unit_id, "instruments": findings}


def main():
    unit_id = sys.argv[1]
    OUT_DIR.mkdir(exist_ok=True)
    payload = run_unit(unit_id)
    out_path = OUT_DIR / f"{unit_id}.json"
    out_path.write_text(json.dumps(payload, indent=2))
    for record in payload["instruments"]:
        if "best" in record:
            ho = (record.get("holdout") or {}).get("out_of_sample")
            wf = (record.get("walk_forward") or {}).get("out_of_sample")
            v = record.get("verdict", {})
            tag = "SURVIVES" if v.get("survives") else "FAILS"
            ho_s = f"PF{ho['profit_factor']}/{ho['total_return_pct']}%/{ho['trades']}t" if ho else "n/a"
            wf_s = f"PF{wf['profit_factor']}/{wf['total_return_pct']}%/{wf['trades']}t" if wf else "n/a"
            print(f"{record['symbol']:9} {record['best']['params']['strategy']:5} "
                  f"[{tag:8}] holdout={ho_s:22} walkfwd={wf_s:22} {';'.join(v.get('reasons', []))}")
        else:
            print(f"{record['symbol']:9} ERROR {record.get('error')}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
