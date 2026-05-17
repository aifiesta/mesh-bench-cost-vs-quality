# mesh-bench: cost vs quality

A small, sharp, fully reproducible benchmark across five LLMs on two real workloads. Code generation and customer support. Every call routed through [Mesh API](https://meshapi.ai) so the runner, rate-limiting, and billing are identical across providers.

This is the first in a series of benchmark repos under [aifiesta](https://github.com/aifiesta). Each repo in the series is a single, self-contained question (one dataset, one methodology, one blog post). The umbrella index is at [aifiesta/mesh-benchmarks](https://github.com/aifiesta/mesh-benchmarks).

## Headline result, pilot edition (n=5 per task)

| Model | Task A pass | Task A $/correct | Task B quality (1 to 5) | Task B $/qual-pt |
| --- | --- | --- | --- | --- |
| **GPT-4o-mini** | **5/5** | **$0.0001** | 3.03 ± 0.07 | **$0.00019** |
| DeepSeek V4 Pro | 5/5 | $0.00201 | 3.07 ± 0.13 | $0.00322 |
| Claude Opus 4.7 | 5/5 | $0.00563 | **3.53 ± 0.00** | $0.01363 |
| GPT-5.5 | 5/5 | $0.00859 | 3.33 ± 0.13 | $0.01856 |
| Gemini 2.5 Pro | 2/5 | $0.10090 | 3.17 ± 0.20 | $0.02288 |

Four of five models tied at 100% on the code test. The cheapest one came out 86x cheaper than GPT-5.5 per correct answer. Claude Opus 4.7's tokenizer billed roughly 60% more input tokens than OpenAI's for the same English text. Gemini 2.5 Pro billed roughly 96% of its output as hidden reasoning that never reached the response body. Full write-up: see `blog_post.html`.

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
- Future benchmarks in the series: see [aifiesta/mesh-benchmarks](https://github.com/aifiesta/mesh-benchmarks).

## Contributing

If you run this against your own workload and get different numbers, please open an issue with the CSVs and we'll fold corrections into v2. PRs welcome for: additional models, additional task definitions, tokenizer-inflation measurements on controlled corpora, judge-bias studies.

Issues, PRs, and replies on social are all good channels for feedback.
