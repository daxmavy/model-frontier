#!/usr/bin/env python3
"""Build the model dataset that the site renders.

Sources
  Artificial Analysis  leaderboard page payload -> capability scores, prices,
                       cost to run the whole Intelligence Index, reasoning effort
  OpenRouter           public /api/v1/models    -> live provider pricing, links
  OpenRouter           /rankings page payload   -> recent token usage (top slice)

Output: site/data/models.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.request

import epoch
import weights
from aa_parse import extract, _arrays

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data" / "models.json"
CACHE = ROOT / "data"

AA_LEADERBOARD = "https://artificialanalysis.ai/leaderboards/models"
OR_MODELS = "https://openrouter.ai/api/v1/models"
OR_RANKINGS = "https://openrouter.ai/rankings"
HF_CACHE = ROOT / "data" / "hf_params.json"

# The labs whose releases the chart shows by default: the Western frontier labs
# and the Chinese labs that ship competitive frontier models. Everything else
# stays one click away behind the developer filter.
MAJOR_LABS = {
    "OpenAI", "Anthropic", "Google", "Google DeepMind", "xAI", "SpaceXAI",
    "Meta", "Mistral",
    "DeepSeek", "Alibaba", "Moonshot AI", "Kimi", "Z AI", "Zhipu AI",
    "MiniMax", "Tencent", "ByteDance", "Baidu", "Xiaomi",
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

# --- metric catalogue -------------------------------------------------------
# Each entry: key in the AA record, label, and how to read it.
CAPABILITY_METRICS = [
    ("intelligenceIndex", "Intelligence Index", "index",
     "Artificial Analysis Intelligence Index: a composite of ten evaluations."),
    ("codingIndex", "Coding Index", "index",
     "Composite of the coding evaluations."),
    ("agenticIndex", "Agentic Index", "index",
     "Composite of the agentic / tool-use evaluations."),
    ("gpqa", "GPQA Diamond", "frac", "Graduate-level science questions."),
    ("hle", "Humanity's Last Exam", "frac", "Very hard expert-written questions."),
    ("omniscienceAccuracy", "Omniscience (accuracy)", "frac",
     "Factual recall accuracy."),
    ("omniscience", "Omniscience Index", "index",
     "Recall accuracy penalised for hallucination."),
    ("terminalbenchHard", "Terminal-Bench Hard", "frac",
     "Agentic terminal tasks."),
    ("tau2", "Tau^2 Bench", "frac", "Tool use in customer-service scenarios."),
    ("scicode", "SciCode", "frac", "Scientific coding."),
    ("lcr", "LiveCodeBench", "frac", "Competitive programming."),
    ("ifbench", "IFBench", "frac", "Instruction following."),
    ("critpt", "CritPt", "frac", "Research-level physics."),
    ("mmmuPro", "MMMU-Pro", "frac", "Multimodal reasoning."),
    ("gdpvalNormalized", "GDPval", "frac",
     "Performance on economically valuable knowledge work."),
    ("analystAgent", "Analyst Agent", "frac", "Long-horizon analyst tasks."),
    ("apexAgents", "APEX Agents", "frac", "Agentic professional tasks."),
    ("itbenchSre", "IT-Bench SRE", "frac", "Site-reliability engineering tasks."),
] + epoch.metrics()

COST_METRICS = [
    ("aaii_cost_total", "Cost to run the Intelligence Index (USD)",
     "Total dollars Artificial Analysis spent running the whole index on this "
     "model. Captures verbosity and reasoning tokens, not just the token price."),
    ("blended_price", "Blended price, 3:1 (USD / 1M tokens)",
     "Three parts input to one part output, at list price."),
    ("output_price", "Output price (USD / 1M tokens)", "List price per million output tokens."),
    ("input_price", "Input price (USD / 1M tokens)", "List price per million input tokens."),
    ("or_blended_price", "OpenRouter blended price, 3:1 (USD / 1M tokens)",
     "Same 3:1 blend using OpenRouter's listed price for the default provider."),
    ("cost_per_index_point", "Index cost per intelligence point (USD)",
     "Cost to run the Intelligence Index divided by the score it achieved."),
]


def fetch(url: str, binary: bool = False) -> str | bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    return raw if binary else raw.decode("utf-8", errors="replace")


def norm(s: str | None) -> str:
    """Loose key for matching model identifiers across sources."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[.\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-(preview|latest|beta|thinking|instruct)$", "", s)
    return re.sub(r"-+", "-", s).strip("-")


def openrouter_index(models: list[dict]) -> dict[str, dict]:
    """Map several normalised aliases onto each OpenRouter model."""
    idx: dict[str, dict] = {}
    for m in models:
        mid = m.get("id") or ""
        if ":" in mid:                      # skip :batch / :free variants
            continue
        bare = mid.split("/", 1)[-1]
        name = (m.get("name") or "").split(":", 1)[-1]
        aliases = {norm(bare), norm(name), norm(mid.replace("/", "-"))}
        aliases |= {undate(a) for a in aliases}
        for alias in aliases:
            if alias:
                idx.setdefault(alias, m)
    return idx


def undate(s: str) -> str:
    """Drop trailing date stamps: -0813, -2512, -20260902."""
    return re.sub(r"-(20)?\d{4,8}$", "", s)


def or_price(m: dict, field: str) -> float | None:
    try:
        v = float(m["pricing"][field])
    except (KeyError, TypeError, ValueError):
        return None
    return v * 1_000_000 if v > 0 else None


def usage_by_model(html: str) -> dict[str, float]:
    """Recent total tokens per model from the rankings page payload."""
    best: list[dict] = []
    for arr in _arrays(html.replace('\\"', '"'), '"data":['):
        if arr and isinstance(arr[0], dict) and "model_permaslug" in arr[0]:
            if len(arr) > len(best):
                best = arr
    out: dict[str, float] = {}
    for r in best:
        slug = re.sub(r"-20\d{6}$", "", r.get("model_permaslug", ""))
        tokens = (r.get("total_completion_tokens") or 0) + (r.get("total_prompt_tokens") or 0)
        out[norm(slug.split("/", 1)[-1])] = out.get(norm(slug.split("/", 1)[-1]), 0) + tokens
    return out


def cost_total(rec: dict) -> float | None:
    c = rec.get("intelligenceIndexCostPerTask")
    if isinstance(c, dict):
        v = c.get("cost", {}).get("total")
        return float(v) if isinstance(v, (int, float)) else None
    return None


def build_from_html(aa_html: str, or_models: list[dict] | None = None,
                    usage: dict[str, float] | None = None,
                    min_models: int = 50) -> dict:
    """Turn a leaderboard page into the dataset the site reads.

    Network access is optional: without OpenRouter the records simply carry no
    provider link, no OpenRouter price and no usage figure.
    """
    aa_rows, _ = extract(aa_html)
    if len(aa_rows) < min_models:
        raise SystemExit(f"Artificial Analysis parse returned only {len(aa_rows)} models; "
                         "the page layout has probably changed.")

    if or_models is None:
        try:
            or_models = json.loads(fetch(OR_MODELS))["data"]
        except Exception as e:                                # noqa: BLE001
            print(f"warning: OpenRouter model list unavailable ({e})", file=sys.stderr)
            or_models = []
    or_idx = openrouter_index(or_models)

    if usage is None:
        try:
            usage = usage_by_model(fetch(OR_RANKINGS))
        except Exception as e:                                # noqa: BLE001
            print(f"warning: OpenRouter rankings unavailable ({e})", file=sys.stderr)
            usage = {}

    try:
        ep_scores, ep_params = epoch.parse(fetch(epoch.CSV_URL))
    except Exception as e:                                    # noqa: BLE001
        print(f"warning: Epoch AI results unavailable ({e})", file=sys.stderr)
        ep_scores, ep_params = {}, {}

    hf_ids = sorted({m["hugging_face_id"] for m in or_models if m.get("hugging_face_id")})
    try:
        hf_params = weights.resolve(hf_ids, HF_CACHE)
    except Exception as e:                                    # noqa: BLE001
        print(f"warning: Hugging Face parameter counts unavailable ({e})", file=sys.stderr)
        hf_params = {}

    models = []
    for slug, r in aa_rows.items():
        if r.get("deprecated"):
            continue
        cap = {k: r.get(k) for k, *_ in CAPABILITY_METRICS if isinstance(r.get(k), (int, float))}
        if not cap:
            continue

        eff = r.get("effort") or {}
        rel = r.get("release") or {}
        base_slug = rel.get("slug") or slug

        pin, pout = r.get("price1mInputTokens"), r.get("price1mOutputTokens")

        orm = None
        for cand in (base_slug, slug, rel.get("name"), r.get("name")):
            key = norm(cand)
            orm = or_idx.get(key) or or_idx.get(undate(key))
            if orm:
                break
        or_in = or_price(orm, "prompt") if orm else None
        or_out = or_price(orm, "completion") if orm else None

        # Epoch reports per reasoning level too, so match on the level first.
        ep = (ep_scores.get((norm(base_slug), eff.get("label")))
              or ep_scores.get((norm(slug), eff.get("label")))
              or (ep_scores.get((norm(base_slug), None)) if not eff else None)
              or {})
        cap.update({k: v for k, v in ep.items() if k not in cap})

        params = None
        if orm and orm.get("hugging_face_id"):
            params = hf_params.get(orm["hugging_face_id"])
        if params is None:
            params = ep_params.get(norm(base_slug))

        total = cost_total(r)
        ii = r.get("intelligenceIndex")

        cost = {
            "aaii_cost_total": total,
            "blended_price": (0.75 * pin + 0.25 * pout) if pin is not None and pout is not None else None,
            "output_price": pout,
            "input_price": pin,
            "or_blended_price": (0.75 * or_in + 0.25 * or_out) if or_in is not None and or_out is not None else None,
            "cost_per_index_point": (total / ii) if total and ii else None,
        }

        if not any(v for v in cost.values()):
            continue           # a chart about cost has nothing to say about these

        models.append({
            "slug": slug,
            "name": r.get("shortName") or r.get("name") or slug,
            "release": rel.get("name") or r.get("shortName") or slug,
            "creator": r.get("modelCreatorName") or "Unknown",
            "effort": eff.get("label"),
            "effortLevel": eff.get("level"),
            "reasoning": bool(r.get("isReasoning")),
            "openWeights": bool(r.get("isOpenWeights")),
            "releaseDate": r.get("releaseDate"),
            "contextTokens": r.get("contextWindowTokens"),
            "speed": r.get("medianOutputTokensPerSecond"),
            "latency": r.get("medianTimeToFirstAnswerTokenSeconds"),
            "estimated": bool(r.get("intelligenceIndexIsEstimated")),
            "majorLab": (r.get("modelCreatorName") or "") in MAJOR_LABS,
            "params": params,
            "vramGB": round(weights.vram_gb(params), 1) if params else None,
            "capability": {k: round(v, 4) for k, v in cap.items()},
            "cost": {k: (round(v, 6) if v is not None else None) for k, v in cost.items()},
            "aaUrl": f"https://artificialanalysis.ai/models/{slug}",
            "aaReleaseUrl": f"https://artificialanalysis.ai/models/{base_slug}",
            "orUrl": f"https://openrouter.ai/{orm['id']}" if orm else None,
            "orId": orm["id"] if orm else None,
            "usageTokens": usage.get(norm(orm["id"].split("/", 1)[-1])) if orm else None,
        })

    models.sort(key=lambda m: -(m["capability"].get("intelligenceIndex") or 0))

    def reported(key, group, floor):
        return sum(1 for m in models if m[group].get(key) is not None) >= floor

    floor = min(10, max(1, len(models) // 10))
    caps = [c for c in CAPABILITY_METRICS if reported(c[0], "capability", floor)]
    costs = [c for c in COST_METRICS if reported(c[0], "cost", floor)]

    return {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "counts": {
            "models": len(models),
            "withIndexCost": sum(1 for m in models if m["cost"]["aaii_cost_total"]),
            "withOpenRouter": sum(1 for m in models if m["orUrl"]),
            "withEpoch": sum(1 for m in models
                             if any(k.startswith("epoch_") for k in m["capability"])),
            "withParams": sum(1 for m in models if m["params"]),
        },
        "capabilityMetrics": [
            {"key": k, "label": lab, "kind": kind, "help": h} for k, lab, kind, h in caps
        ],
        "costMetrics": [{"key": k, "label": lab, "help": h} for k, lab, h in costs],
        "models": models,
    }


def build(offline_html: str | None = None) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    if offline_html:
        aa_html = pathlib.Path(offline_html).read_text(encoding="utf-8", errors="replace")
    else:
        aa_html = fetch(AA_LEADERBOARD)
        (CACHE / "aa_leaderboard.html").write_text(aa_html, encoding="utf-8")
    return build_from_html(aa_html)


def bundle(dest: pathlib.Path, data_path: pathlib.Path, for_artifact: bool = False) -> pathlib.Path:
    """Inline the module and the dataset so the page is one standalone file."""
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    lib = (ROOT / "site" / "lib.js").read_text(encoding="utf-8").replace("export ", "")

    html = html.replace("import { money, fmtVal, fmtTokens, paretoFrontier, ticks } from './lib.js';", lib)
    html = html.replace("fetch('data/models.json?' + Date.now()).then(r => r.json()).then(d => {",
                        "Promise.resolve(EMBEDDED_DATA).then(d => {")
    html = html.replace("<script type=\"module\">",
                        "<script type=\"module\">\nconst EMBEDDED_DATA = "
                        + data_path.read_text(encoding="utf-8") + ";\n")

    if for_artifact:
        # The artifact host supplies its own document shell.
        for tag in ('<!doctype html>', '<html lang="en">', '<head>', '</head>',
                    '<body>', '</body>', '</html>',
                    '<meta charset="utf-8">',
                    '<meta name="viewport" content="width=device-width, initial-scale=1">'):
            html = html.replace(tag + "\n", "").replace(tag, "")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    return dest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline-html", help="use a saved leaderboard page instead of fetching")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--bundle", metavar="PATH",
                    help="also write a standalone single-file copy of the page")
    ap.add_argument("--for-artifact", action="store_true",
                    help="with --bundle, omit the document shell the artifact host provides")
    ap.add_argument("--no-fetch", action="store_true",
                    help="bundle the existing dataset without rebuilding it")
    a = ap.parse_args()

    if a.no_fetch:
        if not a.bundle:
            raise SystemExit("--no-fetch only makes sense with --bundle")
        b = bundle(pathlib.Path(a.bundle), pathlib.Path(a.out), a.for_artifact)
        print(f"bundled -> {b} ({b.stat().st_size/1024:.0f} KB)")
        raise SystemExit(0)

    data = build(a.offline_html)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    c = data["counts"]
    print(f"{c['models']} current models, "
          f"{c['withIndexCost']} with index cost, {c['withOpenRouter']} matched to OpenRouter "
          f"-> {out} ({out.stat().st_size/1024:.0f} KB)")

    if a.bundle:
        b = bundle(pathlib.Path(a.bundle), out, a.for_artifact)
        print(f"bundled -> {b} ({b.stat().st_size/1024:.0f} KB)")
