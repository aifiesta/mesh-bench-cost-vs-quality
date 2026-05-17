"""
Mesh runner: hits Mesh API for each (task, model) pair and records outputs.

Usage:
    export MESH_API_KEY=sk-mesh-...
    export MESH_BASE_URL=https://api.mesh.ai/v1   # adjust if needed
    python runner.py --task task_a_code.json --out runs_task_a.csv
    python runner.py --task task_b_support.json --out runs_task_b.csv

Notes:
- Assumes Mesh API is OpenAI-compatible (chat.completions endpoint).
- If Mesh uses a different shape, edit `call_model()` only.
- Retries on transient errors up to 3x with exponential backoff.
- Records input_tokens, output_tokens, latency_ms, retries per call.
"""

import argparse
import csv
import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Any

# --- Config ---------------------------------------------------------------

MODELS = [
    # (mesh_model_id, display_name, input_price_per_M, output_price_per_M)
    # Prices are USD per 1M tokens, verified against api.meshapi.ai/v1/models on 2026-05-17.
    # Opus 4.7 uses Mesh's 15% discount tier ($5.00/$25.00 list -> $4.25/$21.25).
    ("openai/gpt-5.5",               "GPT-5.5",          5.00,  30.00),
    ("anthropic/claude-opus-4.7",    "Claude Opus 4.7",  4.25,  21.25),
    ("deepseek/deepseek-v4-pro",     "DeepSeek V4 Pro",  1.392,  2.784),
    ("google/gemini-2-5-pro",        "Gemini 2.5 Pro",   1.25,  10.00),
    ("openai/gpt-4o-mini",           "GPT-4o-mini",      0.15,   0.60),
]

MAX_RETRIES = 3
REQUEST_TIMEOUT = 120  # seconds

# --- Data classes ---------------------------------------------------------

@dataclass
class CallResult:
    task_file: str
    item_id: str
    model_id: str
    model_name: str
    prompt: str
    output: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    retries: int
    error: str
    input_price: float
    output_price: float

# --- Mesh API call --------------------------------------------------------

def make_client():
    from openai import OpenAI  # pip install openai
    api_key = os.environ.get("MESH_API_KEY")
    base_url = os.environ.get("MESH_BASE_URL", "https://api.mesh.ai/v1")
    if not api_key:
        raise SystemExit("MESH_API_KEY not set. Export it before running.")
    return OpenAI(api_key=api_key, base_url=base_url, timeout=REQUEST_TIMEOUT)

def call_model(client, model_id: str, prompt: str, max_tokens: int = 4096) -> dict:
    """
    Returns: {output, input_tokens, output_tokens, latency_ms, retries, error}
    """
    retries = 0
    last_err = ""
    t0 = time.time()
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            latency_ms = int((time.time() - t0) * 1000)
            usage = resp.usage
            return {
                "output": resp.choices[0].message.content or "",
                "input_tokens": getattr(usage, "prompt_tokens", 0),
                "output_tokens": getattr(usage, "completion_tokens", 0),
                "latency_ms": latency_ms,
                "retries": retries,
                "error": "",
            }
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            retries += 1
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
    return {
        "output": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "latency_ms": int((time.time() - t0) * 1000),
        "retries": retries,
        "error": last_err,
    }

# --- Main loop ------------------------------------------------------------

def run(task_file: str, out_file: str, limit: int | None = None,
        budget_cap_usd: float | None = None) -> None:
    with open(task_file) as f:
        task = json.load(f)
    items = task["items"]
    if limit:
        items = items[:limit]
    prompt_template = task["prompt_template"]

    client = make_client()
    rows: list[CallResult] = []
    spend = 0.0

    total = len(items) * len(MODELS)
    done = 0
    for item in items:
        prompt = prompt_template.format(**item)
        for (model_id, model_name, in_price, out_price) in MODELS:
            done += 1
            if budget_cap_usd is not None and spend >= budget_cap_usd:
                print(f"[BUDGET CAP] spent ${spend:.3f} >= cap ${budget_cap_usd:.2f}. Stopping.")
                break
            print(f"[{done}/{total}] {model_name} on {item['id']} (spend so far: ${spend:.3f})")
            r = call_model(client, model_id, prompt)
            call_cost = (r["input_tokens"] * in_price + r["output_tokens"] * out_price) / 1e6
            spend += call_cost
            rows.append(CallResult(
                task_file=task_file,
                item_id=item["id"],
                model_id=model_id,
                model_name=model_name,
                prompt=prompt,
                output=r["output"],
                input_tokens=r["input_tokens"],
                output_tokens=r["output_tokens"],
                latency_ms=r["latency_ms"],
                retries=r["retries"],
                error=r["error"],
                input_price=in_price,
                output_price=out_price,
            ))
        else:
            continue
        break  # outer break if inner broke on budget

    # Write CSV
    fieldnames = list(asdict(rows[0]).keys())
    with open(out_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))
    print(f"Wrote {len(rows)} rows to {out_file}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, help="Path to task JSON")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument("--limit", type=int, default=None, help="Limit items (smoke test)")
    p.add_argument("--budget-cap", type=float, default=None,
                   help="Stop run if total spend exceeds this USD amount (recommended: 5.0)")
    args = p.parse_args()
    run(args.task, args.out, args.limit, args.budget_cap)
    print(f"\nDone. Final spend (this run): tracked in CSV; run cost_estimator.py for projection.")
