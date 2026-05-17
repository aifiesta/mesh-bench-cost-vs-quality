"""
Cost estimator. Run a tiny dryrun, then project the full benchmark cost from
ACTUAL token counts (not estimated ones).

Usage:
    # Step 1: dryrun 2 items per task (small spend, ~10 calls)
    python runner.py --task task_a_code.json --out dryrun_a.csv --limit 2
    python runner.py --task task_b_support.json --out dryrun_b.csv --limit 2

    # Step 2: project full-run cost
    python cost_estimator.py --dryruns dryrun_a.csv dryrun_b.csv \
                             --full-items 30 --judge-passes 2

Output: per-model projected cost + total. Tells you whether to proceed.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def to_int(x: str, default: int = 0) -> int:
    try:
        return int(float(x)) if x not in ("", None) else default
    except ValueError:
        return default


def to_float(x: str, default: float = 0.0) -> float:
    try:
        return float(x) if x not in ("", None) else default
    except ValueError:
        return default


def estimate(dryrun_paths: list[str], full_items: int, judge_passes: int,
             budget_cap: float | None = None) -> dict:
    """Project full-run cost from a small dryrun."""
    # Per (task, model): collect avg input/output tokens
    by_task_model: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for path in dryrun_paths:
        with open(path) as f:
            for row in csv.DictReader(f):
                key = (Path(row["task_file"]).stem, row["model_name"])
                by_task_model[key].append(row)

    if not by_task_model:
        print("No dryrun data found.")
        return {}

    # Compute per-call avg, then scale to full_items
    breakdown = []
    total_runner = 0.0
    total_runner_tokens_out = 0
    for (task, model), rows in by_task_model.items():
        n = len(rows)
        avg_in = sum(to_int(r["input_tokens"]) for r in rows) / n
        avg_out = sum(to_int(r["output_tokens"]) for r in rows) / n
        in_price = to_float(rows[0]["input_price"])
        out_price = to_float(rows[0]["output_price"])
        # Projected cost for full_items
        per_call_cost = (avg_in * in_price + avg_out * out_price) / 1e6
        projected = per_call_cost * full_items
        total_runner += projected
        total_runner_tokens_out += avg_out * full_items
        breakdown.append({
            "task": task,
            "model": model,
            "dryrun_calls": n,
            "avg_input_tokens": round(avg_in, 0),
            "avg_output_tokens": round(avg_out, 0),
            "per_call_cost_usd": round(per_call_cost, 5),
            "projected_30item_cost_usd": round(projected, 3),
        })

    # Judge cost: 1 Opus call per support output, × judge_passes (1 or 2)
    # Skip Task A in judge cost (programmatic). Only count rows whose task != task_a_code.
    n_judge_calls = 0
    for (task, model), rows in by_task_model.items():
        if "task_a" in task:
            continue
        n_judge_calls += full_items  # one judge call per item per model
    n_judge_calls *= judge_passes
    # Conservative judge cost: ~600 input tokens, ~80 output tokens, Opus pricing
    judge_in_price = 5.0
    judge_out_price = 25.0
    judge_cost_per_call = (600 * judge_in_price + 80 * judge_out_price) / 1e6
    total_judge = n_judge_calls * judge_cost_per_call

    grand_total = total_runner + total_judge

    result = {
        "breakdown": sorted(breakdown, key=lambda x: -x["projected_30item_cost_usd"]),
        "totals": {
            "runner_usd": round(total_runner, 2),
            "judge_calls": n_judge_calls,
            "judge_cost_per_call_usd": round(judge_cost_per_call, 5),
            "judge_total_usd": round(total_judge, 2),
            "grand_total_usd": round(grand_total, 2),
        },
        "settings": {
            "full_items_per_task": full_items,
            "judge_passes": judge_passes,
            "budget_cap_usd": budget_cap,
        },
    }
    return result


def render_report(r: dict) -> str:
    if not r:
        return "(no data)"
    lines = []
    lines.append("=" * 72)
    lines.append("PROJECTED FULL-RUN COST")
    lines.append("=" * 72)
    lines.append(f"Items per task:       {r['settings']['full_items_per_task']}")
    lines.append(f"Judge passes:         {r['settings']['judge_passes']} (1 = single temp, 2 = variance bars)")
    lines.append("")
    lines.append(f"{'Task':<18} {'Model':<22} {'in tok':>7} {'out tok':>8} {'$/call':>10} {'30-item $':>12}")
    lines.append("-" * 80)
    for b in r["breakdown"]:
        lines.append(
            f"{b['task']:<18} {b['model']:<22} {b['avg_input_tokens']:>7.0f} "
            f"{b['avg_output_tokens']:>8.0f} ${b['per_call_cost_usd']:>9.5f} "
            f"${b['projected_30item_cost_usd']:>11.3f}"
        )
    t = r["totals"]
    lines.append("-" * 80)
    lines.append(f"Runner subtotal:                                                          ${t['runner_usd']:>7.2f}")
    lines.append(f"Judge: {t['judge_calls']} calls @ ${t['judge_cost_per_call_usd']:.5f}                                ${t['judge_total_usd']:>7.2f}")
    lines.append("=" * 72)
    lines.append(f"GRAND TOTAL                                                               ${t['grand_total_usd']:>7.2f}")
    lines.append("=" * 72)
    cap = r["settings"].get("budget_cap_usd")
    if cap is not None:
        if t["grand_total_usd"] > cap:
            lines.append(f"\n  WARNING: projected ${t['grand_total_usd']:.2f} EXCEEDS your cap of ${cap:.2f}")
            lines.append("  Options: --judge-passes 1, smaller --full-items, drop GPT-5.5 from runner.MODELS")
        else:
            lines.append(f"\n  OK: under your ${cap:.2f} cap (headroom: ${cap - t['grand_total_usd']:.2f})")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dryruns", nargs="+", required=True, help="One or more dryrun CSVs")
    p.add_argument("--full-items", type=int, default=30, help="Items per task in full run")
    p.add_argument("--judge-passes", type=int, default=2, choices=[1, 2],
                   help="1 = single temp, 2 = variance bars (doubles judge cost)")
    p.add_argument("--budget-cap", type=float, default=10.0, help="USD cap to compare against")
    p.add_argument("--json", action="store_true", help="Output JSON instead of table")
    args = p.parse_args()

    r = estimate(args.dryruns, args.full_items, args.judge_passes, args.budget_cap)
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print(render_report(r))


if __name__ == "__main__":
    main()
