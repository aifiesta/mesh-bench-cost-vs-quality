# Pilot Report. Mesh Dollar-Per-Task Benchmark

Date: 2026-05-17
Scope: 5 items × 5 models × 2 tasks (50 final calls + 25 LLM-judge calls)
Final-state pilot spend (Mesh-billed for kept calls): **$0.43**
Total session burn including discarded re-runs and GPT-5.4 detour: **≈ $1.25**

---

## TL;DR

| Rank | Best $/correct on Task A | Best $/quality-point on Task B |
|---|---|---|
| 1 | **GPT-4o-mini**, $0.0001 / correct | **GPT-4o-mini**, $0.00019 / qpt |
| 2 | DeepSeek V4 Pro, $0.00201 | DeepSeek V4 Pro, $0.00329 |
| 3 | Claude Opus 4.7, $0.00563 | Claude Opus 4.7, $0.01363 |
| 4 | GPT-5.5, $0.00859 | GPT-5.5, $0.0182 |
| 5 | Gemini 2.5 Pro, $0.1009 | Gemini 2.5 Pro, $0.02362 |

- Pricing-ladder mismatch with the original blog premise: a $0.15/M-input model wins both tracks at n=5.
- GPT-5.5 ties for the top of the Task A pass-rate group (5/5) but costs 86× more per correct answer than GPT-4o-mini (which also passes all 5).
- Gemini 2.5 Pro's $/correct is **1009× worse** than GPT-4o-mini's, driven almost entirely by hidden reasoning tokens (see "Hidden costs observed" below).
- Claude Opus 4.7 wins Task B quality (3.53), narrowly ahead of GPT-5.5 (3.4); both cost ~70× more per quality-point than GPT-4o-mini (3.07).

> **Caveat for blog:** n=5 per task. Two of the five Task A items (A03, A04, A05) only have 4 tests; others have 5. Pass rates are noisy at this sample size. Results should be labeled "pilot, illustrative" until the 30-item run completes.

---

## Setup actuals

| Variable | Initial scaffold guess | Actual |
|---|---|---|
| `MESH_BASE_URL` | `https://api.mesh.ai/v1` | **`https://api.meshapi.ai/v1`** (mesh.ai doesn't resolve) |
| Key location | env export | loaded from project-local `.env` |
| Model namespace | `openai/...`, `anthropic/opus-...` | `openai/...` ✓, `anthropic/claude-opus-...` (prefix wrong in guesses) |

### Model lineup actually run

| Slot | runner.py guess | Pilot used | Prices (in / out per 1M) |
|---|---|---|---|
| Frontier OpenAI | `openai/gpt-5.5` ($5/$30) | **`openai/gpt-5.5`** ($5/$30) | Confirmed by Mesh dashboard back-solve* |
| Frontier Anthropic | `anthropic/opus-4.7` ($5/$25) | **`anthropic/claude-opus-4.7`** | $4.25/$21.25 (15% Mesh discount applied) |
| Mid-tier | `deepseek/v4-pro` ($1.74/$3.48) | **`deepseek/deepseek-v4-pro`** | $1.392/$2.784 (Mesh /models; runner had wrong price) |
| Mid-tier | `google/gemini-2.5-pro` ($1.25/$5) | **`google/gemini-2-5-pro`** (hyphenated) | $1.25/$10 (runner had output price 2× too low) |
| Cheap | `openai/gpt-4o-mini` ($0.15/$0.60) | unchanged ✓ | unchanged |

\* GPT-5.5 is **routable but not exposed by `/models`**. Pricing recovered from a sanity-ping call cost reported on the Mesh log dashboard: 21→57 tokens billed at $0.001815, which solves cleanly with the family-standard 6× ratio to $5/$30 per 1M.

(`openai/gpt-5.5-pro` *is* in `/models` at $30/$180 but returned `upstream_error` HTTP 500 on every call during initial probing; we don't use it.)

---

## Per-model results

### Task A, code (programmatic test runner)

| Model | n_pass / n | Pass rate | Avg latency | Effective cost | $/correct |
|---|---|---|---|---|---|
| Claude Opus 4.7 | 5/5 | 100% | 3.9 s | $0.0282 (1.35× inflation) | $0.00563 |
| DeepSeek V4 Pro | 5/5 | 100% | 28.4 s | $0.0101 | $0.00201 |
| GPT-5.5 | 5/5 | 100% | 5.5 s | $0.0430 (1.20× inflation) | $0.00859 |
| GPT-4o-mini | 5/5 | 100% | 2.4 s | $0.0005 | $0.0001 |
| Gemini 2.5 Pro | 2/5 | 40% | 28.0 s | $0.2018 | $0.1009 |

- GPT-4o-mini now hits 5/5 too (vs 4/5 in the earlier prompt-bug run): the failure on A03 in the prior pass was real but A03 only had 4 tests, at n=5 this rounds noisy.
- DeepSeek V4 Pro is **5–10× slower** than the OpenAI models. Doesn't affect $/correct but matters for any interactive workflow.
- Gemini's 2 passes (A01, A04) were the simplest items; misses (A02, A03, A05) were truncated mid-answer despite `max_tokens=4096`.

### Task B, customer support (LLM judge, 1-pass at temp 0.0)

| Model | Quality (1–5) | Effective cost | $/quality-pt |
|---|---|---|---|
| Claude Opus 4.7 | **3.53** | $0.0482 | $0.01363 |
| GPT-5.5 | 3.40 | $0.0619 (1.20× inflation) | $0.0182 |
| GPT-4o-mini | 3.07 | $0.0006 | $0.00019 |
| Gemini 2.5 Pro | 3.07 | $0.0724 | $0.02362 |
| DeepSeek V4 Pro | 3.00 | $0.0099 | $0.00329 |

- Variance bars unavailable: pilot used `--judge-passes 1` per handoff doc. Full run will use 2-pass for variance.
- Opus's 0.13-point lead over GPT-5.5 is well within likely judge noise, don't read too much into it at n=5.

---

## Hidden costs observed in pilot

The blog's premise, that $/Mtok lies because of reasoning tokens and tokenizer divergence, is **directly observable in this n=5 pilot**:

### 1. Gemini 2.5 Pro hidden reasoning
- Mesh strips Gemini's chain-of-thought from the response body but **bills the full token count**.
- Task A average output: 3,833 tokens billed, ~250 chars (~80 tokens) of visible code.
- That's **~98% of output spend on tokens the user never sees**, even though `supports_thinking: false` in /models.
- Cost impact: $0.20 for 5 Task A items vs. $0.0005 for GPT-4o-mini → **400× more expensive**, partly because 3 of those answers were truncated before the visible code finished.

### 2. Opus 4.7 input-token inflation
- 5 Task B prompts: identical English text in, but Anthropic tokenizer produces **1,769 input tokens** vs. ~1,100 for everyone else (≈60% more).
- This is an **input-side** observation; the existing `TOKENIZER_INFLATION[Opus 4.7] = 1.35` only multiplies output. On real corpora the headline 1.35× number should be re-measured to capture both sides.

### 3. GPT-5.5 reasoning overhead (smaller than Gemini but real)
- Task A average output: 226 tokens vs. ~135 for GPT-4o-mini on the same problems.
- Task B average output: 314 tokens vs. ~138 for GPT-4o-mini.
- Aggregate.py applies 1.20× inflation to GPT-5.5 (placeholder per handoff). Empirical ratio in pilot is 1.65× output-tokens vs. GPT-4o-mini, the gap is even wider than the placeholder.

### 4. DeepSeek latency penalty
- DeepSeek V4 Pro averages 28 s (Task A) and 16 s (Task B), 5–10× slower than GPT models.
- Doesn't affect $/correct, but matters for any user-facing workflow.

---

## Issues discovered during pilot (and what I changed)

| # | Issue | Fix | File |
|---|---|---|---|
| 1 | `MESH_BASE_URL` guess (`api.mesh.ai`) DNS-fails | Use `api.meshapi.ai/v1` via env | runtime only |
| 2 | All 5 model IDs were wrong-namespace guesses | Replaced with `/models`-verified IDs | `runner.py` |
| 3 | `openai/gpt-5.5-pro` 500s `upstream_error` on every call (15 attempts in initial probe) | Discovered `openai/gpt-5.5` (unlisted but live) works. Used it instead. | `runner.py` |
| 4 | DeepSeek list price wrong: $1.74/$3.48 vs actual $1.392/$2.784 | Use Mesh /models values | `runner.py` |
| 5 | Gemini output price wrong: $5 vs actual $10 | Use Mesh /models values | `runner.py` |
| 6 | Opus 15% Mesh discount not applied ($5/$25 → $4.25/$21.25) | Applied per user decision | `runner.py` |
| 7 | `max_tokens=1024` truncated all Gemini answers (visible code cut mid-statement) | Raised to 4096 globally | `runner.py` |
| 8 | `judge.py` hardcoded `JUDGE_MODEL = "anthropic/opus-4.7"` → would 404 | Changed to `anthropic/claude-opus-4.7` | `judge.py` |
| 9 | Task A prompt said "Return ONLY the function body". GPT-5.x and Gemini followed it literally (no `def` line), failing every test | Changed to "Return ONLY the complete function (starting with the `def solve(...)` line)" | `task_a_code.json` prompt_template |
| 10 | `aggregate.py` divided by 2 even when only 1 judge pass was run → Task B quality scores halved | Divide by actual passes used | `aggregate.py` |

**Deliberately NOT changed** (per handoff doc):
- `TOKENIZER_INFLATION` multipliers in `aggregate.py`, still placeholder ("must be replaced with real measurements before publishing"). Note pilot empirics suggest GPT-5.5 is closer to 1.65× and Gemini's effective hidden-reasoning multiplier on hard items is more like 40×, these need controlled measurement before going into the blog.
- The 30 Task A problems and 30 Task B tickets themselves (only the Task A *prompt template* changed; items unchanged).
- Model lineup beyond the GPT-5.5-pro → GPT-5.5 swap.
- `blog_post_draft.md` and its `{{PLACEHOLDER}}` structure.

---

## Full-run cost projection

From `cost_estimator.py --dryruns pilot_a.csv pilot_b.csv --budget-cap 10` (will re-project after the GPT-5.5 swap; previous projection was $3.50 with GPT-5.4 in the slot, expect ~$5–6 with GPT-5.5 because it's 2× the price).

Headroom against $10 cap: comfortable. Safe to scale up.

---

## Open questions / decisions needed

1. **Scale to full 30 items?** Pilot looks clean (0 errors across 50 final calls). Re-projection with GPT-5.5 in the slot should be re-run before kicking off (~$5–6 estimate vs. the $3.50 from the GPT-5.4-slot projection).
2. **Tokenizer-inflation rewrite is the highest-leverage open item for the blog.** Headline finding. Needs ~$2 of dedicated measurement against a controlled corpus (~1k tokens English × 5 tokenizers) before any number can be published.
3. **Gemini 2.5 Pro on the lineup at all?** Its $/correct ($0.10) is so much worse than alternatives that it could either be the blog's villain (good story) or skew aggregated charts hard. Worth deciding intent before full 30 run. Alternative: try `google/gemini-3.1-pro-preview` ($2.00/$12, listed in /models), newer and might handle the truncation better.
4. **Add `"GPT-5.5": 1.20` is already in `aggregate.py`, but the empirical pilot ratio is closer to 1.65.** Update before publishing.

---

## What's on disk

```
pilot_a.csv               Task A pilot raw runs (25 rows, 0 errors, gpt-5.5 in lineup)
pilot_b.csv               Task B pilot raw runs (25 rows, 0 errors, gpt-5.5 in lineup)
judged_a.csv              Task A judged (programmatic, 25 rows)
judged_b.csv              Task B judged (LLM 1-pass, 25 rows)
pilot_results.csv         Aggregated 10 rows (5 models × 2 tasks)
pilot_results.json        Same as above, pretty JSON
pilot_*.gpt54.csv         Backup of the GPT-5.4 pilot before swapping to GPT-5.5
pilot_report.md           This document
```

API key handling: project-local `.env`, gitignored. Rotate keys between environments. Do not commit `.env` to any public repo.
