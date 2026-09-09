# Cost - capability tradeoff reference

A daily-updating chart of what language-model capability actually costs.

The question it answers: **for a given level of capability, what is the cheapest
model that reaches it?** Models on the Pareto frontier are the answer at each
level. Everything below the frontier is dominated, meaning some other model is
both cheaper and better.

## Why another one of these

Existing views each pick one axis and one cost measure. This one lets you choose
both, and it is careful about what "cost" means.

- **Cost is holistic by default.** The headline measure is what one task on the
  Artificial Analysis Intelligence Index costs on a given model, averaged across
  the index. It counts the tokens actually consumed, so a verbose model that
  emits five times the reasoning tokens costs five times as much, which a
  per-token price hides.
- **Reasoning levels are separate marks.** Running a model at `high` versus
  `minimal` changes both its score and its bill, so they are not the same
  product and are not merged into one point.
- **Every mark links out**, to that model's Artificial Analysis page for the
  exact reasoning level, and to its OpenRouter page where one exists.

## How it works

`pipeline/build.py` reads three sources and writes one file, `site/data/models.json`:

| Source | What it contributes |
| --- | --- |
| Artificial Analysis leaderboard | capability scores, list prices, cost per task, reasoning effort |
| Epoch AI benchmark results | FrontierMath and other tasks Artificial Analysis does not run |
| OpenRouter model list | live provider pricing, model links |
| OpenRouter rankings | recent token usage, used for the popularity ranking |

Epoch records reasoning effort in its model identifiers too, so its scores join
onto the right variant rather than being smeared across a model family.

`site/index.html` is a single page with no build step and no runtime
dependencies. It fetches that JSON and draws the chart itself.

A GitHub Action rebuilds the dataset every morning, commits it, and redeploys the
page. If a source changes shape the build aborts and the job fails, so the
previously deployed site stays up rather than being replaced by a broken one.

## Choosing what to show

By default the chart shows every model a major lab released in the past year.
The frontier is computed over everything that passes the filters and is never
truncated, so a cheap outlier still appears even when it falls outside the
default scope.

Two filters narrow the set further: open weights against proprietary, and a
single developer.

## Running it locally

```bash
python pipeline/build.py            # refresh site/data/models.json
python -m http.server -d site 8731  # then open http://localhost:8731
```

## Tests

```bash
python -m unittest discover -s tests
node --test 'tests/*.test.mjs'
```

The Python tests cover the leaderboard parser and the record shaping against a
miniature fixture of the page payload. The JavaScript tests cover the Pareto
selection, the axis ticks and the number formatting.

## What is left out

Models Artificial Analysis has retired, and models it lists no price for at all,
never reach the page. A chart about cost has nothing to say about a model whose
cost is unknown on every axis.

## Caveats

Benchmark scores are a proxy for usefulness, not a measurement of it. The cost of
running the index is one measurement per model rather than an average over
repeated runs, so small differences are noise. List prices ignore batch
discounts, caching and negotiated rates.
