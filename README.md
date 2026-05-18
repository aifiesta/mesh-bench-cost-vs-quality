# mesh-bench: cost vs quality

A small, sharp, fully reproducible benchmark across five LLMs on two real workloads. Code generation and customer support. Every call routed through [Mesh API](https://meshapi.ai) so the runner, rate-limiting, and billing are identical across providers.

## The tasks

**Task A: code generation.** 30 original algorithmic problems, medium difficulty, written from scratch to limit training-set contamination (the *exact* problem strings aren't on the internet, though the *patterns* obviously are). Each problem ships hidden test cases (4 to 5 per problem). The model receives a prompt with a function signature like `def solve(nums: list[int]) -> int` plus a short natural-language description, and must return one complete Python function inside a fenced code block. The judge extracts the function, runs it in a subprocess against the hidden tests with an 8-second timeout, and scores it pass/fail per test. The pilot uses the first 5 problems (A01 to A05): longest strictly increasing subarray, longest substring with at most 2 distinct characters, integers up to N that have no prime factor greater than 5, count of connected groups of 1s in a binary grid, count of subarrays whose sum equals k. Classic patterns (sliding window, prefix sum, BFS, factorization) but with original phrasings and input shapes.

**Task B: customer support.** 30 synthetic tickets for a fictional cloud-storage product called *Nimbus* with three plans (Personal $9/mo, Pro $20/mo, Team $50/mo) and a small set of known policies (refund window, plan-gated features, account recovery, SLA tiers). Each ticket ships per-item rubric notes that tell the LLM judge what a correct reply should do, what it must not invent, and where ambiguity belongs. Categories include straightforward refunds, refund edge cases (charge outside policy window), account recovery, technical errors, billing math, feature questions gated by plan tier, angry user de-escalation, outage SLA disputes, data export, security incidents, feature requests, neutral product comparisons, and explicit "policy is silent on this" edge cases. The model writes one reply per ticket. Claude Opus 4.7 rates each reply twice (temperature 0.0 and 0.3) on tone, accuracy, and completeness (1 to 5 integer scores).

## Pilot results, n=5 per task

| Model | Task A pass | Task A $/correct | Task B quality (1 to 5) | Task B $/qual-pt |
| --- | --- | --- | --- | --- |
| **GPT-4o-mini** | **5/5** | **$0.0001** | 3.03 ± 0.07 | **$0.00019** |
| DeepSeek V4 Pro | 5/5 | $0.00201 | 3.07 ± 0.13 | $0.00322 |
| Claude Opus 4.7 | 5/5 | $0.00563 | **3.53 ± 0.00** | $0.01363 |
| GPT-5.5 | 5/5 | $0.00859 | 3.33 ± 0.13 | $0.01856 |
| Gemini 2.5 Pro | 2/5 | $0.10090 | 3.17 ± 0.20 | $0.02288 |

**What we found, in one paragraph.** GPT-4o-mini ($0.15/M input) won both axes. It got 5/5 on the code test and posted a customer-support quality score (3.03) within 14% of the most expensive model in the lineup, while costing 86x less per correct code answer than GPT-5.5 and 72x less per quality-point on support than Claude Opus 4.7. Four of five models tied at perfect on the code test, so the premium tiers bought no accuracy at this size, just higher bills. Claude Opus 4.7 led customer-support quality at 3.53 with a perfectly stable judge score (variance 0.00 across two passes), but the 0.5-point lead over the cheapest model cost roughly 72x more per quality-point. Gemini 2.5 Pro was the outlier in the wrong direction: 2/5 on the code test, and its invoice counted roughly 23x more output tokens than what actually appeared in its responses (hidden reasoning the API strips before sending the reply), which made it 1,009x more expensive per correct code answer than GPT-4o-mini. On the input side, Claude Opus 4.7's tokenizer reported 60% more tokens than OpenAI's for the exact same English prompts, which means its effective input price on this corpus is closer to $8/M than the $5/M on the price card. Full write-up with charts and methodology: see `blog_post.html`.

> Pilot, n=5/task. Headline gaps are big enough that the broad shape is unlikely to flip, but second-decimal differences absolutely could. Run the scripts yourself; if you get different numbers, open an issue.

## What's in here

| File | What it is |
| --- | --- |
| `task_a_code.json` | 30 original algorithmic problems with hidden tests (5 used in pilot) |
| `task_b_support.json` | 30 synthetic support tickets with per-item rubrics (5 used in pilot) |
| `runner.py` | Hits Mesh API for each (item, model) pair, writes a CSV row per call |
| `judge.py` | Programmatic test runner for Task A; LLM judge (Opus 4.7, two temps) for Task B |
| `aggregate.py` | Per-model summaries with hidden-cost adjustments |
| `cost_estimator.py` | Projects full-run cost from a small dry-run before you commit |
| `smoke_test.py` | End-to-end pipeline check against mocked Mesh responses (no API calls) |
| `make_charts.py` | Regenerates the four chart PNGs from `pilot_results.csv` |
| `pilot_a.csv` / `pilot_b.csv` | Raw per-call output from the pilot run (kept for transparency) |
| `judged_a.csv` / `judged_b.csv` | Same rows with judge scores attached |
| `pilot_results.csv` / `pilot_results.json` | Aggregated 10-row summary used by the blog tables |
| `chart_*.png` | The four charts in the blog post |
| `blog_post.html`, `blog_post.md` | The public write-up |
| `pilot_report.md` | Internal-style work log: issues found, decisions made, things flagged |

## Reproduce in 5 minutes

```bash
# 1. Install
pip install openai matplotlib pillow

# 2. Configure
cp .env.example .env
# Edit .env, set MESH_API_KEY and MESH_BASE_URL=https://api.meshapi.ai/v1

# 3. Verify (no API calls)
python3 smoke_test.py

# 4. Tiny live ping (~1 call, costs less than a cent)
python3 -c "
import os
from openai import OpenAI
c = OpenAI(api_key=os.environ['MESH_API_KEY'], base_url=os.environ['MESH_BASE_URL'])
r = c.chat.completions.create(model='openai/gpt-4o-mini',
    messages=[{'role':'user','content':'say pong'}], max_tokens=10)
print('OK:', r.choices[0].message.content)
"

# 5. Reproduce the pilot (n=5 per task, ~$0.45 total)
python3 runner.py --task task_a_code.json    --out pilot_a.csv --limit 5 --budget-cap 5
python3 runner.py --task task_b_support.json --out pilot_b.csv --limit 5 --budget-cap 5

# 6. Score and aggregate
python3 judge.py     --task task_a_code.json    --runs pilot_a.csv --out judged_a.csv
python3 judge.py     --task task_b_support.json --runs pilot_b.csv --out judged_b.csv
python3 aggregate.py --judged judged_a.csv judged_b.csv --out pilot_results.csv
python3 make_charts.py
```

## Cost projection for a full 30-item run

| Source | Estimated |
| --- | --- |
| Runner, all 5 models, both tasks, 30 items each | ~$2.00 |
| Judge, 300 Opus calls, 2 temps each | ~$1.50 |
| **Total full run** | **~$3.50** |

Budget cap is enforced by `--budget-cap` on `runner.py`. Smoke test before spending. `cost_estimator.py` projects full-run cost from a 2-item dry-run.

## Methodology in one paragraph

Every call uses temperature 0.2, max_tokens 4096, identical prompts across models. Token counts come from each provider's `usage` field (not estimated). Task A is scored programmatically: extract code from the fenced block, run in a subprocess against hidden tests with an 8-second timeout, all-or-nothing per test. Task B is scored by Claude Opus 4.7 as judge, run twice per item (temp 0.0 and 0.3), three integer scores 1 to 5 (tone, accuracy, completeness). Quality is the mean of the six numbers. Variance is the spread between the two passes. Effective cost applies an output-side tokenizer-inflation factor per model (currently placeholder, to be replaced with measured values in v2). Input-side inflation reported in the blog is real and measured on this run's prompts.

## What this benchmark deliberately does not cover

- **Latency is end-to-end wall clock, not isolated model service time.** Numbers include our network round-trip, Mesh's routing/processing overhead, and the upstream provider's queue + inference. To break those apart you'd need Mesh server-side telemetry or direct-to-provider calls; neither is in this pilot.
- n=5 per task in the pilot. Big enough to see headline gaps, too small for confidence intervals.
- Single judge model (Opus 4.7). Own-output bias risk mitigated with the 2-temp variance check, not eliminated. v2 will use a three-judge ensemble.
- No human eval. v2 will add a 100-item human calibration set.
- Task A scoring is binary. A nearly-right solution that fails one edge case scores zero.
- Pattern overlap with training data is likely (problems are original strings, but patterns sit in every model's training distribution).
- Single region, single time-of-day, single run. No confidence intervals; provider throttling varies by hour.
- No streaming, no time-to-first-token, no p95 latency. Different post.
- Output-side tokenizer inflation factors are placeholder; the input-side 60% Opus number is measured.
- Your favorite model is probably not in the lineup of five. Add a row to `MODELS` in `runner.py` and re-run; the scripts work with any Mesh-routable model.

## License

MIT. Datasets and scripts are free to use, modify, and republish. Attribution appreciated, not required.

## Roadmap

- v1: n=30 per task, three-judge ensemble, human calibration on 100 items, latency percentiles, two more models in the lineup. Will replace this README's headline table when it lands.

## Contributing

If you run this against your own workload and get different numbers, please open an issue with the CSVs and we'll fold corrections into v2. PRs welcome for: additional models, additional task definitions, tokenizer-inflation measurements on controlled corpora, judge-bias studies.

Issues, PRs, and replies on social are all good channels for feedback.
