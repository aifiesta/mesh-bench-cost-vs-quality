"""
Smoke test for the benchmark pipeline.

Runs everything with MOCKED Mesh responses so we can verify:
1. task_a_code.json and task_b_support.json parse correctly
2. runner.py format string substitution works
3. judge.py programmatic test runner finds passing/failing code correctly
4. aggregate.py math is right on known inputs

No API key required. Run with:
    python smoke_test.py

A non-zero exit means a bug. DO NOT spend real API calls until this passes.
"""

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent

def ok(msg: str) -> None:
    print(f"  OK   {msg}")

def fail(msg: str) -> None:
    print(f"  FAIL {msg}")
    sys.exit(1)

# --- 1. Datasets parse and have required fields ----------------------------

def test_datasets() -> None:
    print("[1] dataset shape")
    for name in ("task_a_code.json", "task_b_support.json"):
        path = HERE / name
        with open(path) as f:
            d = json.load(f)
        assert "items" in d and "prompt_template" in d, f"{name} missing keys"
        assert len(d["items"]) == 30, f"{name} expected 30 items, got {len(d['items'])}"
        ok(f"{name}: {len(d['items'])} items, has prompt_template")

    # Task A items must have tests
    with open(HERE / "task_a_code.json") as f:
        a = json.load(f)
    for it in a["items"]:
        assert "signature" in it and "tests" in it and len(it["tests"]) >= 3, f"A item {it['id']} bad shape"
    ok("task_a items all have signature + >=3 tests")

    # Task B items have message + rubric
    with open(HERE / "task_b_support.json") as f:
        b = json.load(f)
    for it in b["items"]:
        assert "message" in it and "rubric" in it, f"B item {it['id']} bad shape"
    ok("task_b items all have message + rubric")

    # prompt_template substitution works
    sample_a = a["items"][0]
    a["prompt_template"].format(**sample_a)
    sample_b = b["items"][0]
    b["prompt_template"].format(**sample_b)
    ok("prompt_template.format(**item) succeeds for both tasks")

# --- 2. judge.py programmatic runner correctness ---------------------------

def test_programmatic_judge() -> None:
    print("[2] programmatic test runner")
    sys.path.insert(0, str(HERE))
    from judge import extract_code, run_tests_programmatic  # type: ignore

    # Correct solution for A01 (longest increasing subarray)
    correct = """
def solve(nums):
    if not nums: return 0
    best = cur = 1
    for i in range(1, len(nums)):
        if nums[i] > nums[i-1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best
"""
    # Wrap in code block to test extract_code
    wrapped = f"```python\n{correct}\n```"
    code = extract_code(wrapped)
    assert "def solve" in code, "extract_code lost the function"

    with open(HERE / "task_a_code.json") as f:
        a = json.load(f)
    a01_tests = a["items"][0]["tests"]
    r = run_tests_programmatic(code, a01_tests)
    assert r["passed"] == r["total"], f"correct solution failed: {r}"
    ok(f"correct A01 solution: {r['passed']}/{r['total']}")

    # Wrong solution: always returns 0
    wrong = "def solve(nums):\n    return 0\n"
    r = run_tests_programmatic(wrong, a01_tests)
    assert r["passed"] < r["total"], f"wrong solution passed everything: {r}"
    ok(f"wrong A01 solution: {r['passed']}/{r['total']} (correctly failed)")

    # Solution that raises
    bad = "def solve(nums):\n    raise ValueError('nope')\n"
    r = run_tests_programmatic(bad, a01_tests)
    assert r["passed"] == 0, f"exception-raising solution scored: {r}"
    ok("exception-raising solution: 0 (correctly caught)")

# --- 3. aggregator math ---------------------------------------------------

def test_aggregator_math() -> None:
    print("[3] aggregator math")
    sys.path.insert(0, str(HERE))
    from aggregate import aggregate_one  # type: ignore

    # Build synthetic rows. Two models, two items each.
    # Model X (no inflation): 1000 in @ $1/M, 500 out @ $2/M = $0.002 per call, 2 calls = $0.004
    # Model Y (Claude Opus 4.7, infl 1.35): same tokens & prices = $0.004 raw, $0.0047 effective
    rows = [
        {"task_file": "runs_task_a.csv", "model_name": "DeepSeek V4 Pro", "input_price": "1.0", "output_price": "2.0",
         "input_tokens": "1000", "output_tokens": "500", "latency_ms": "100", "retries": "0", "error": "",
         "all_pass": "1", "item_id": "A01"},
        {"task_file": "runs_task_a.csv", "model_name": "DeepSeek V4 Pro", "input_price": "1.0", "output_price": "2.0",
         "input_tokens": "1000", "output_tokens": "500", "latency_ms": "100", "retries": "0", "error": "",
         "all_pass": "0", "item_id": "A02"},
        {"task_file": "runs_task_a.csv", "model_name": "Claude Opus 4.7", "input_price": "1.0", "output_price": "2.0",
         "input_tokens": "1000", "output_tokens": "500", "latency_ms": "200", "retries": "1", "error": "",
         "all_pass": "1", "item_id": "A01"},
        {"task_file": "runs_task_a.csv", "model_name": "Claude Opus 4.7", "input_price": "1.0", "output_price": "2.0",
         "input_tokens": "1000", "output_tokens": "500", "latency_ms": "200", "retries": "0", "error": "",
         "all_pass": "1", "item_id": "A02"},
    ]
    summaries = aggregate_one(rows)
    by_model = {s["model"]: s for s in summaries}

    ds = by_model["DeepSeek V4 Pro"]
    assert ds["raw_cost_usd"] == 0.004, f"DS raw cost: {ds['raw_cost_usd']}"
    assert ds["effective_cost_usd"] == 0.004, f"DS eff cost: {ds['effective_cost_usd']}"
    assert ds["pass_rate"] == 0.5, f"DS pass rate: {ds['pass_rate']}"
    assert ds["n_correct"] == 1
    assert ds["cost_per_correct_usd"] == 0.004, f"DS $/correct: {ds['cost_per_correct_usd']}"
    ok(f"DeepSeek: raw=${ds['raw_cost_usd']}, eff=${ds['effective_cost_usd']}, pass={ds['pass_rate']}")

    op = by_model["Claude Opus 4.7"]
    # Output cost inflated: 500 * 2 * 1.35 / 1M = 0.00135, plus 1000 * 1 / 1M = 0.001 per call
    # Per call effective = 0.00235, 2 calls = 0.0047
    assert op["raw_cost_usd"] == 0.004
    assert op["effective_cost_usd"] == 0.0047, f"Opus eff cost: {op['effective_cost_usd']}"
    assert op["pass_rate"] == 1.0
    assert op["cost_per_correct_usd"] == 0.00235, f"Opus $/correct: {op['cost_per_correct_usd']}"
    assert op["retry_overhead_pct"] == 50.0, f"Opus retry: {op['retry_overhead_pct']}"
    ok(f"Opus 4.7: raw=${op['raw_cost_usd']}, eff=${op['effective_cost_usd']} (35% inflation applied)")
    ok(f"Opus 4.7: retry overhead {op['retry_overhead_pct']}%")

# --- 4. End-to-end: mock runner → judge → aggregate ------------------------

def test_end_to_end_mock() -> None:
    print("[4] end-to-end with mocked Mesh outputs (Task A, 2 items, 2 models)")
    # Write a tiny mock runs CSV directly (skipping the actual Mesh call)
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        runs_csv = td_p / "runs_mock.csv"

        # Same correct solution for both items, but only one model gets it right on A02
        correct_sub = """def solve(nums):
    if not nums: return 0
    best = cur = 1
    for i in range(1, len(nums)):
        if nums[i] > nums[i-1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best"""
        wrong_sub = "def solve(nums):\n    return 0"

        fieldnames = ["task_file","item_id","model_id","model_name","prompt","output",
                      "input_tokens","output_tokens","latency_ms","retries","error",
                      "input_price","output_price"]
        with open(runs_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerow({"task_file": str(HERE / "task_a_code.json"), "item_id": "A01",
                        "model_id": "mock/cheap", "model_name": "DeepSeek V4 Pro",
                        "prompt": "...", "output": f"```python\n{correct_sub}\n```",
                        "input_tokens": "200", "output_tokens": "100", "latency_ms": "150",
                        "retries": "0", "error": "", "input_price": "1.74", "output_price": "3.48"})
            w.writerow({"task_file": str(HERE / "task_a_code.json"), "item_id": "A01",
                        "model_id": "mock/big", "model_name": "Claude Opus 4.7",
                        "prompt": "...", "output": f"```python\n{wrong_sub}\n```",
                        "input_tokens": "200", "output_tokens": "30", "latency_ms": "200",
                        "retries": "0", "error": "", "input_price": "5.0", "output_price": "25.0"})

        # Run judge
        judged = td_p / "judged_mock.csv"
        r = subprocess.run([sys.executable, str(HERE / "judge.py"),
                            "--task", str(HERE / "task_a_code.json"),
                            "--runs", str(runs_csv), "--out", str(judged)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            fail(f"judge.py failed: {r.stderr}")

        # Inspect judged
        with open(judged) as f:
            judged_rows = list(csv.DictReader(f))
        assert len(judged_rows) == 2, f"expected 2 judged rows, got {len(judged_rows)}"
        ds_row = next(r for r in judged_rows if r["model_name"] == "DeepSeek V4 Pro")
        op_row = next(r for r in judged_rows if r["model_name"] == "Claude Opus 4.7")
        assert ds_row["all_pass"] == "1", f"DS should pass A01, got all_pass={ds_row['all_pass']}"
        assert op_row["all_pass"] == "0", f"Opus (returning 0) should fail A01"
        ok("judge.py: cheap-with-correct-code passes, frontier-with-wrong-code fails")

        # Run aggregate
        results = td_p / "results.csv"
        r = subprocess.run([sys.executable, str(HERE / "aggregate.py"),
                            "--judged", str(judged), "--out", str(results)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            fail(f"aggregate.py failed: {r.stderr}")
        with open(results) as f:
            res_rows = list(csv.DictReader(f))
        assert len(res_rows) == 2, f"expected 2 result rows, got {len(res_rows)}"
        ok(f"aggregate.py produced {len(res_rows)} summary rows")

def main() -> None:
    test_datasets()
    test_programmatic_judge()
    test_aggregator_math()
    test_end_to_end_mock()
    print("\nAll smoke tests passed. Safe to run with real Mesh key.")

if __name__ == "__main__":
    main()
