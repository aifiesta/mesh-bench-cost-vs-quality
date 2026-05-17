"""
Judge: scores model outputs.

Task A (code): programmatic. Extracts code from output, runs hidden tests in a subprocess
               with a timeout. Score = number of passing tests / total tests. Binary pass = all-pass.

Task B (support): LLM-as-judge via Claude Opus 4.7. Runs each rating twice (temp 0.0 and temp 0.3)
                  so we get variance bars. Scores 1-5 on tone, accuracy, completeness.

Usage:
    python judge.py --task task_a_code.json   --runs runs_task_a.csv --out judged_task_a.csv
    python judge.py --task task_b_support.json --runs runs_task_b.csv --out judged_task_b.csv
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

MESH_BASE_URL = os.environ.get("MESH_BASE_URL", "https://api.mesh.ai/v1")
JUDGE_MODEL = "anthropic/claude-opus-4.7"
TEST_TIMEOUT_SEC = 8  # per item

# --- Task A: programmatic ----------------------------------------------------

CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)

def extract_code(output: str) -> str:
    """Pull the Python code out of model output. Falls back to raw output."""
    m = CODE_BLOCK_RE.search(output)
    if m:
        return m.group(1).strip()
    return output.strip()

def run_tests_programmatic(code: str, tests: list[dict]) -> dict:
    """Run code against tests in a subprocess. Returns {passed, total, errors}."""
    # Build a runner script
    test_payload = json.dumps(tests)
    runner_src = f'''
import json, sys, traceback
TESTS = json.loads({json.dumps(test_payload)})

# --- model code ---
{code}
# --- end model code ---

passed = 0
errors = []
for i, t in enumerate(TESTS):
    try:
        out = solve(*t["input"])
        # Normalize for set-of-lists comparisons (group anagrams, etc.)
        def norm(x):
            if isinstance(x, list) and x and isinstance(x[0], list):
                return sorted([sorted(map(str, sub)) if all(isinstance(e, str) for e in sub) else sorted(sub) for sub in x])
            return x
        if norm(out) == norm(t["output"]):
            passed += 1
        else:
            errors.append(f"test {{i}}: got {{out!r}} expected {{t['output']!r}}")
    except Exception as e:
        errors.append(f"test {{i}}: {{type(e).__name__}}: {{e}}")
print(json.dumps({{"passed": passed, "total": len(TESTS), "errors": errors[:3]}}))
'''
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(runner_src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=TEST_TIMEOUT_SEC,
        )
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        try:
            return json.loads(last)
        except json.JSONDecodeError:
            return {"passed": 0, "total": len(tests), "errors": [r.stderr[:200] or "no output"]}
    except subprocess.TimeoutExpired:
        return {"passed": 0, "total": len(tests), "errors": ["timeout"]}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

# --- Task B/C: LLM judge -----------------------------------------------------

JUDGE_PROMPT = """You are evaluating a customer support reply.

ORIGINAL USER MESSAGE:
{message}

RUBRIC GUIDANCE (what a good reply does):
{rubric}

THE REPLY YOU ARE EVALUATING:
{reply}

Score on three dimensions, integers 1-5 (5 = excellent, 1 = terrible). Be strict; average answers score 3, not 4.

- tone: warm without being sycophantic, appropriate to the user's emotional state, not robotic.
- accuracy: only uses policies given to the agent, doesn't invent rules, handles 'unknown' cases honestly.
- completeness: addresses the actual ask, asks needed clarifying questions, doesn't add irrelevant filler.

Respond with ONLY a JSON object on one line: {{"tone": N, "accuracy": N, "completeness": N, "note": "<one short sentence>"}}"""

def make_client():
    from openai import OpenAI  # lazy: smoke_test imports judge.py without API SDK
    api_key = os.environ.get("MESH_API_KEY")
    if not api_key:
        raise SystemExit("MESH_API_KEY not set.")
    return OpenAI(api_key=api_key, base_url=MESH_BASE_URL, timeout=60)

def judge_one(client, message: str, rubric: str, reply: str, temperature: float) -> dict:
    prompt = JUDGE_PROMPT.format(message=message, rubric=rubric, reply=reply)
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=temperature,
            )
            txt = (r.choices[0].message.content or "").strip()
            # Strip any code fences
            txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.MULTILINE).strip()
            return json.loads(txt)
        except Exception as e:
            if attempt == 2:
                return {"tone": 0, "accuracy": 0, "completeness": 0, "note": f"judge_error: {e}"}
            time.sleep(2 ** attempt)
    return {"tone": 0, "accuracy": 0, "completeness": 0, "note": "judge_failed"}

# --- Main --------------------------------------------------------------------

def judge_task_a(task: dict, runs: list[dict], out_path: str) -> None:
    items_by_id = {it["id"]: it for it in task["items"]}
    rows = []
    for r in runs:
        item = items_by_id[r["item_id"]]
        code = extract_code(r["output"])
        result = run_tests_programmatic(code, item["tests"])
        passed = result["passed"]
        total = result["total"]
        rows.append({
            **r,
            "tests_passed": passed,
            "tests_total": total,
            "all_pass": int(passed == total and total > 0),
            "judge_note": "; ".join(result.get("errors", []))[:200],
            "tone_t0": "", "accuracy_t0": "", "completeness_t0": "",
            "tone_t1": "", "accuracy_t1": "", "completeness_t1": "",
        })
        print(f"  {r['model_name']} {r['item_id']}: {passed}/{total}")
    write_judged(rows, out_path)

def judge_task_bc(task: dict, runs: list[dict], out_path: str, judge_passes: int = 2) -> None:
    items_by_id = {it["id"]: it for it in task["items"]}
    client = make_client()
    rows = []
    for r in runs:
        item = items_by_id[r["item_id"]]
        message = item["message"] if "message" in item else item.get("question", "")
        rubric = item.get("rubric", "")
        j0 = judge_one(client, message, rubric, r["output"], temperature=0.0)
        if judge_passes == 2:
            j1 = judge_one(client, message, rubric, r["output"], temperature=0.3)
        else:
            j1 = {"tone": "", "accuracy": "", "completeness": "", "note": ""}
        rows.append({
            **r,
            "tests_passed": "", "tests_total": "", "all_pass": "",
            "tone_t0": j0.get("tone", 0),
            "accuracy_t0": j0.get("accuracy", 0),
            "completeness_t0": j0.get("completeness", 0),
            "tone_t1": j1.get("tone", ""),
            "accuracy_t1": j1.get("accuracy", ""),
            "completeness_t1": j1.get("completeness", ""),
            "judge_note": (j0.get("note", "") or "")[:200],
        })
        t1_str = f" t1={j1.get('tone')}/{j1.get('accuracy')}/{j1.get('completeness')}" if judge_passes == 2 else ""
        print(f"  {r['model_name']} {r['item_id']}: t0={j0.get('tone')}/{j0.get('accuracy')}/{j0.get('completeness')}{t1_str}")
    write_judged(rows, out_path)

def write_judged(rows: list[dict], out_path: str) -> None:
    if not rows:
        print("No rows to write.")
        return
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} judged rows to {out_path}")

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True)
    p.add_argument("--runs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--judge-passes", type=int, default=2, choices=[1, 2],
                   help="1 = single temp (cheaper), 2 = variance bars (default)")
    args = p.parse_args()

    with open(args.task) as f:
        task = json.load(f)
    with open(args.runs) as f:
        runs = list(csv.DictReader(f))

    if task["task_name"] == "task_a_code":
        judge_task_a(task, runs, args.out)
    else:
        judge_task_bc(task, runs, args.out, judge_passes=args.judge_passes)

if __name__ == "__main__":
    main()
