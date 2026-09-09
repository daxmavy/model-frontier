# The Model Frontier

A daily-updating chart of what language-model capability actually costs.

The question it answers: **for a given level of capability, what is the cheapest
model that reaches it?** Models on the Pareto frontier are the answer at each
level. Everything below the frontier is dominated, meaning some other model is
both cheaper and better.

## Why another one of these

Existing views each pick one axis and one cost measure. This one lets you choose
both, and it is careful about what "cost" means.

- **Cost is holistic by default.** The headline measure is the total dollars
  Artificial Analysis spent running its whole Intelligence Index on a model. A
  verbose model that emits five times the reasoning tokens costs five times as
  much to run, and that shows up here where a per-token price hides it.
- **Reasoning levels are separate marks.** Running a model at `high` versus
  `minimal` changes both its score and its bill, so they are not the same
  product and are not merged into one point.
- **Every mark links out**, to that model's Artificial Analysis page for the
  exact reasoning level, and to its OpenRouter page where one exists.

## How it works

`pipeline/build.py` reads three sources and writes one file, `site/data/models.json`:

| Source | What it contributes |
| --- | --- |
| Artificial Analysis leaderboard | capability scores, list prices, cost to run the index, reasoning effort |
| OpenRouter model list | live provider pricing, model links |
| OpenRouter rankings | recent token usage, used for the popularity ranking |

`site/index.html` is a single page with no build step and no runtime
dependencies. It fetches that JSON and draws the chart itself.

A GitHub Action rebuilds the dataset every morning, commits it, and redeploys the
page. If a source changes shape the build aborts and the job fails, so the
previously deployed site stays up rather than being replaced by a broken one.

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

## Caveats

Benchmark scores are a proxy for usefulness, not a measurement of it. The cost of
running the index is one measurement per model rather than an average over
repeated runs, so small differences are noise. List prices ignore batch
discounts, caching and negotiated rates.
