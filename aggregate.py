"""
Aggregator: turns judged CSVs into the headline numbers for the blog.

Computes per (task, model):
- raw_cost        = (input_tokens * input_price + output_tokens * output_price) / 1e6
- effective_cost  = raw_cost with tokenizer-inflation adjustment (see TOKENIZER_INFLATION)
- pass_rate       (Task A only) = mean of all_pass
- quality_score   (Task B/C) = mean across (tone, accuracy, completeness) and both temps
- quality_variance(Task B/C) = stdev of per-item mean across the two temps
- cost_per_task   = effective_cost / n
- cost_per_correct(Task A) = effective_cost_total / n_correct, infinity if zero correct
- cost_per_quality(Task B/C) = effective_cost / quality_score
- retry_overhead  = mean retries per call

Hidden-cost adjustments live in one place (TOKENIZER_INFLATION) so it's easy to
update / argue with publicly. The 35% Opus 4.7 number is the headline finding;
adjust based on your actual tokenizer measurements.

Usage:
    python aggregate.py --judged judged_task_a.csv judged_task_b.csv --out results.csv
"""

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

# Effective-cost multipliers applied to output tokens.
# Source: based on tokenizer comparison against a fixed corpus of English text.
# Update these once you have real measurements.
TOKENIZER_INFLATION = {
    "GPT-5.5":          1.20,   # reasoning tokens get billed even when invisible
    "Claude Opus 4.7":  1.35,   # 35% more output tokens for equivalent text vs GPT tokenizer
    "DeepSeek V4 Pro":  1.00,
    "Gemini 2.5 Pro":   1.05,
    "GPT-4o-mini":      1.00,
}

def load_csv(path: str) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))

def to_float(x: str, default: float = 0.0) -> float:
    try:
        return float(x) if x not in ("", None) else default
    except ValueError:
        return default

def to_int(x: str, default: int = 0) -> int:
    try:
        return int(float(x)) if x not in ("", None) else default
    except ValueError:
        return default

def aggregate_one(rows: list[dict]) -> list[dict]:
    """Group rows by model. Return one summary dict per model."""
    if not rows:
        return []
    task_file = rows[0].get("task_file", "unknown")
    is_task_a = "task_a" in task_file.lower()

    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_model[r["model_name"]].append(r)

    out = []
    for model_name, rs in by_model.items():
        in_price = to_float(rs[0]["input_price"])
        out_price = to_float(rs[0]["output_price"])
        infl = TOKENIZER_INFLATION.get(model_name, 1.0)

        total_in_tok = sum(to_int(r["input_tokens"]) for r in rs)
        total_out_tok = sum(to_int(r["output_tokens"]) for r in rs)
        n_calls = len(rs)
        n_errors = sum(1 for r in rs if r.get("error", "").strip())
        total_retries = sum(to_int(r["retries"]) for r in rs)

        raw_cost = (total_in_tok * in_price + total_out_tok * out_price) / 1e6
        # Inflation applies to the OUTPUT side (where tokenizers diverge).
        eff_cost = (total_in_tok * in_price + total_out_tok * out_price * infl) / 1e6

        summary = {
            "task": "task_a" if is_task_a else Path(task_file).stem,
            "model": model_name,
            "n_calls": n_calls,
            "n_errors": n_errors,
            "total_input_tokens": total_in_tok,
            "total_output_tokens": total_out_tok,
            "tokenizer_inflation": infl,
            "raw_cost_usd": round(raw_cost, 4),
            "effective_cost_usd": round(eff_cost, 4),
            "retry_overhead_pct": round(100 * total_retries / max(n_calls, 1), 1),
            "avg_latency_ms": round(statistics.mean(to_int(r["latency_ms"]) for r in rs), 0),
        }

        if is_task_a:
            passes = [to_int(r.get("all_pass", "0")) for r in rs]
            pass_rate = sum(passes) / max(len(passes), 1)
            n_correct = sum(passes)
            summary["pass_rate"] = round(pass_rate, 3)
            summary["n_correct"] = n_correct
            summary["cost_per_task_usd"] = round(eff_cost / max(n_calls, 1), 5)
            summary["cost_per_correct_usd"] = round(eff_cost / n_correct, 5) if n_correct else None
            summary["quality_score"] = ""
            summary["quality_variance"] = ""
            summary["cost_per_quality_usd"] = ""
        else:
            # Mean across (tone, accuracy, completeness) per item, then mean both temps
            per_item_means = []
            per_item_variances = []
            for r in rs:
                t0 = [to_float(r.get(k, 0)) for k in ("tone_t0", "accuracy_t0", "completeness_t0")]
                t1 = [to_float(r.get(k, 0)) for k in ("tone_t1", "accuracy_t1", "completeness_t1")]
                t0_used = any(t0)
                t1_used = any(t1)
                m0 = statistics.mean(t0) if t0_used else 0
                m1 = statistics.mean(t1) if t1_used else 0
                if t0_used or t1_used:
                    n_passes = (1 if t0_used else 0) + (1 if t1_used else 0)
                    per_item_means.append((m0 + m1) / n_passes)
                    per_item_variances.append(abs(m0 - m1) if (t0_used and t1_used) else 0)
            q = statistics.mean(per_item_means) if per_item_means else 0
            qv = statistics.mean(per_item_variances) if per_item_variances else 0
            summary["pass_rate"] = ""
            summary["n_correct"] = ""
            summary["cost_per_task_usd"] = round(eff_cost / max(n_calls, 1), 5)
            summary["cost_per_correct_usd"] = ""
            summary["quality_score"] = round(q, 3)
            summary["quality_variance"] = round(qv, 3)
            summary["cost_per_quality_usd"] = round(eff_cost / q, 5) if q else None

        out.append(summary)

    out.sort(key=lambda x: x.get("cost_per_correct_usd") or x.get("cost_per_quality_usd") or 0)
    return out

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--judged", nargs="+", required=True, help="One or more judged CSVs")
    p.add_argument("--out", default="results.csv")
    args = p.parse_args()

    all_summaries = []
    for path in args.judged:
        rows = load_csv(path)
        all_summaries.extend(aggregate_one(rows))

    if not all_summaries:
        print("No data.")
        return

    fieldnames = list(all_summaries[0].keys())
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_summaries)
    print(f"Wrote {len(all_summaries)} summary rows to {args.out}")

    # Also dump pretty JSON for quick review
    json_out = args.out.replace(".csv", ".json")
    with open(json_out, "w") as f:
        json.dump(all_summaries, f, indent=2)
    print(f"Pretty JSON: {json_out}")

if __name__ == "__main__":
    main()
