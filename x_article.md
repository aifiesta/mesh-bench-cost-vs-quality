# A $0.15 model tied $30 models on code. Here's what we paid to find out.

Five LLMs. Two tasks. Fifty calls. We measured what they actually cost, not what the price card says.

The code task is **medium-difficulty algorithmic problems** (think LeetCode medium: sliding window, prefix sum, BFS on a small grid, basic factorization). For *really* complex work (multi-file refactors, ambiguous specs, long-horizon agentic loops, deep math), the picture likely flips and frontier models earn their price. This post is about the 80% of code calls that aren't that.

*Quick disclaimer:* what follows is what we found on our prompts, n=5/task, one judge, one afternoon. Reproducible end-to-end. If you run it and get different numbers, reply with the CSV.

---

## The four numbers that matter

**1. Four of five models passed 100% of the code test.**

GPT-4o-mini ($0.15/M input) and GPT-5.5 ($5/M input) both got 5 of 5. Same answers, 86x the price.

**2. Claude Opus 4.7's tokenizer billed ~60% more input tokens than OpenAI's** for identical English prompts.

A $5/M-input model is really charging ~$8/M-input on the text we sent. That hidden tax is not on Anthropic's price page.

**3. Gemini 2.5 Pro billed 19,165 "output tokens" across 5 code problems.**

Visible answer content: ~840 tokens. Roughly **96% hidden reasoning** that the API strips before the response reaches you. And the model still only got 2 of 5 problems right.

**4. On customer support, the best model (Opus 4.7) was 14% higher quality than the cheapest (GPT-4o-mini), and 72x more expensive per quality-point.**

A small quality bump that costs a fortune.

---

## The full result table

| Model | Code pass | Code $/correct | Support quality (1-5) | Support $/qual-pt |
| --- | --- | --- | --- | --- |
| **GPT-4o-mini** | **5/5** | **$0.0001** | 3.03 ± 0.07 | **$0.00019** |
| DeepSeek V4 Pro | 5/5 | $0.00201 | 3.07 ± 0.13 | $0.00322 |
| Claude Opus 4.7 | 5/5 | $0.00563 | **3.53 ± 0.00** | $0.01363 |
| GPT-5.5 | 5/5 | $0.00859 | 3.33 ± 0.13 | $0.01856 |
| Gemini 2.5 Pro | 2/5 | $0.10090 | 3.17 ± 0.20 | $0.02288 |

*Two stories in one table.* On code, four of five models tied at perfect, so cost is the only differentiator. On support, Opus wins quality by a hair (0.5 points on a 5-point scale) but costs 72x more per quality-point than the cheapest model.

The judge replicated itself perfectly on Opus (variance 0.00) and noisiest on Gemini (0.20). Nothing exceeded 0.2, so quality scores hold up.

*[INSERT CHART 1 HERE: chart_1_real_cost.png]*

---

## What we ran

**Task A: code generation.** Five original algorithmic problems with hidden test cases (longest increasing subarray, longest substring with 2 distinct chars, integers up to N with no prime factor > 5, count of connected 1s in a grid, count of subarrays with sum k). The model returns one Python function. We run it in a subprocess against hidden tests with an 8-second timeout. Pass/fail per test.

**Task B: customer support.** Five synthetic tickets for a fictional cloud-storage product. Each ticket has a rubric telling the judge what a correct reply should do, must not invent, and where ambiguity belongs. Claude Opus 4.7 rates each reply twice (temp 0.0 and 0.3) on tone, accuracy, completeness, 1-5 each.

Every call goes through Mesh API. One client, one key, one bill, five providers behind it. Switching models is changing a string. Without that, this post is a stack of SDKs and rate-limit dialects, and takes a week instead of an afternoon.

---

## Four hidden taxes the price card never mentions

### 1. The tokenizer tax

You'd assume "input tokens" is a property of your input. It isn't. It's a property of the tokenizer that turns your input into tokens, and every provider uses a different one.

Same 10 English prompts, sent to all five models:

| Model | Input tokens for 10 prompts | Delta vs OpenAI |
| --- | --- | --- |
| GPT-4o-mini (OpenAI) | 1,544 | baseline |
| GPT-5.5 (OpenAI) | 1,534 | -0.6% |
| DeepSeek V4 Pro | 1,582 | +2.5% |
| Gemini 2.5 Pro | 1,637 | +6.0% |
| **Claude Opus 4.7** | **2,468** | **+59.8%** |

Same text. Same words. Opus's tokenizer cuts English into ~60% more pieces, and you pay for every piece. Opus's effective input price on this corpus is closer to **$8/M-in**, not the $5/M-in on the card.

Your number will differ. Code-heavy traffic, multilingual, structured data, every workload tokenizes differently. Spend an hour, send 1,000 tokens of *your* actual traffic through each provider with `max_tokens=1`, read `usage.prompt_tokens`, write the ratio down. Plug it into your cost model. Update quarterly.

### 2. The reasoning tax (paying for thoughts you never see)

Some models "think" silently before they answer. Those reasoning tokens are real tokens, on your bill, even though you can't see them in the response.

Gemini 2.5 Pro is the worst case we measured: **19,165 billed output tokens across 5 code problems, ~840 tokens of visible answer.** That's ~96% you paid for and never saw. The model still got 2 of 5 right. A single Gemini call on Task A cost ~$0.04 vs ~$0.0001 for GPT-4o-mini. **400x more expensive, two-fifths the accuracy.**

GPT-5.5 also does internal reasoning (visibly less than Gemini, but it's there): 226 output tokens per Task A item vs 137 for GPT-4o-mini. That's 65% more billed output for similar-length final answers.

If your provider exposes a reasoning-effort knob, dial it down. "Thinking tokens" in marketing is "billed-but-invisible tokens" on your invoice.

### 3. The accuracy assumption that didn't hold

The intuitive cost model: *frontier models cost more but get more right, so $/correct evens out.* In our run, **it didn't**. Four of five models, including the cheap one, hit 100% on the code test. The premium tiers didn't pull ahead on accuracy. They pulled ahead on dollars-per-correct-answer in the wrong direction:

- GPT-4o-mini: $0.0001 per correct solution
- DeepSeek V4 Pro: 20x more
- Claude Opus 4.7: 56x more
- GPT-5.5: 86x more
- Gemini 2.5 Pro: 1,009x more

Honest disclaimer: five problems is small. On longer, gnarlier problems (multi-file refactors, ambiguous specs, deep reasoning), frontier models likely do pull ahead and the math flips. Take this as "the accuracy floor is lower than you think for common code," not "premium models are useless." The takeaway is: know where your floor is, then route accordingly.

*[INSERT CHART 2 HERE: chart_2_task_a.png]*

### 4. Quality saturation

On support, every model produced something workable. Quality range across all five: 3.03 to 3.53 (14% relative). Cost range over the same five: **80x**. Opus 4.7 buys a small quality bump for a huge cost bump. Worth it on calls where a bad reply is expensive (security, finance, brand-attached copy). A bad trade on the routine 80% of support volume where any of the five would have produced something fine.

The decision rule isn't "use the best model." It's **route the call by what it actually needs**. Most companies skip that step and pay frontier prices for everything. The over-spend is structural.

*[INSERT CHART 3 HERE: chart_3_task_b.png]*

---

## Latency, while we're at it

| Model | Code task avg | Support task avg |
| --- | --- | --- |
| GPT-4o-mini | 2.4 s | 2.3 s |
| Claude Opus 4.7 | 3.9 s | 7.1 s |
| GPT-5.5 | 5.5 s | 9.2 s |
| Gemini 2.5 Pro | 28.0 s | 13.7 s |
| DeepSeek V4 Pro | **28.4 s** | 16.2 s |

DeepSeek V4 Pro looks like a steal on $/correct (2nd best at $0.00201) but it took ~28s per code answer on average. For an interactive product, unshippable. For an overnight batch job, a bargain. Match the model to the use case.

---

## The combined picture

Average the two tasks (Task A pass rate scaled to a 0-5 quality score):

*[INSERT CHART 4 HERE: chart_4_cross_task.png]*

A three-order-of-magnitude cost gap with roughly the same quality on either end. The smartest model in the lineup costs 65x more per quality-point than the workhorse, for a 6% absolute quality improvement. That's a routing problem, not a model-selection problem.

---

## Decision rules for builders

1. **Default to the workhorse tier.** A $0.15/M model handled 100% of our code problems and got within 86% of the top quality score on support. Pay frontier prices for calls where being wrong is unusually expensive, not for calls where being right is unusually cheap.

2. **Measure your real tokenizer tax once.** Don't trust the price card. Our Opus 1.60x input-side ratio is specific to our English benchmark. Yours will differ.

3. **Watch for reasoning tokens.** Models that do invisible chain-of-thought can 5x or 50x your output bill. Monitor `usage.completion_tokens` against actual response length.

4. **Build a router, not a model choice.** Cheap default, expensive escalation path, heuristic for when to escalate. That structure handles the price card lying, tokenizer drift, and future model launches.

---

## What this benchmark deliberately does not tell you

- n=5 per task. Big enough to see headline gaps, too small for confidence intervals.
- Single judge model. Own-output bias risk mitigated by 2-temp variance, not eliminated. v2 will use a three-judge ensemble.
- No human eval. Coming in v2.
- Task A scoring is binary. Nearly-right with one failed edge case = zero.
- Pattern overlap with training data is likely. Exact prompts are original; patterns aren't.
- Single region, single time-of-day, single run.
- No streaming, no time-to-first-token, no p95 latency. Different post.
- Output-side tokenizer inflation factors are placeholder. The input-side 60% Opus number is measured.
- Five models. Your favorite probably isn't in the lineup. The scripts run any Mesh-routable model.

---

## Reproduce in 5 minutes

Everything: scripts, datasets, raw CSVs, charts, this post's markdown source.

**Repo:** github.com/aifiesta/mesh-bench-cost-vs-quality

Total cost for the whole benchmark including discarded re-runs during debugging: about $1.30. One Opus call is a quarter of a cent. A million of them adds up.

---

If you run this against your own workload and get different numbers, please reply with the CSV and we'll fold the corrections into v2. v1 ships shortly with n=30 per task, three-judge ensemble, human calibration on 100 items, latency percentiles, and two more models. Follow for the thread.
