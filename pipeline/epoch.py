"""Epoch AI benchmark results.

Epoch publishes one CSV of every evaluation run it has done. It carries a few
benchmarks Artificial Analysis does not run at all (FrontierMath above all), it
records reasoning effort in the model identifier, and it lists parameter counts
for open-weight models.
"""
from __future__ import annotations

import csv
import io
import re

CSV_URL = "https://epoch.ai/data/benchmarks.csv"

# Task name in the CSV -> (metric key, label, help). Only tasks with enough
# models to plot are exposed; the rest of the file is ignored.
TASKS = {
    "FrontierMath-Tiers-1-3-v2-Private":
        ("epoch_frontiermath", "FrontierMath, tiers 1-3",
         "Research-level mathematics, held-out problem set. Run by Epoch AI."),
    "FrontierMath-Tier-4-v2-Private":
        ("epoch_frontiermath_t4", "FrontierMath, tier 4",
         "The hardest FrontierMath tier. Run by Epoch AI."),
    "OTIS Mock AIME 2024-2025":
        ("epoch_aime", "OTIS Mock AIME",
         "Olympiad-style competition mathematics. Run by Epoch AI."),
    "MATH level 5":
        ("epoch_math5", "MATH level 5",
         "The hardest tier of the MATH dataset. Run by Epoch AI."),
    "GPQA diamond":
        ("epoch_gpqa", "GPQA Diamond (Epoch)",
         "Graduate-level science questions, independently run by Epoch AI."),
    "SWE-Bench verified":
        ("epoch_swebench", "SWE-Bench Verified",
         "Real GitHub issues resolved end to end. Run by Epoch AI."),
    "SimpleQA Verified":
        ("epoch_simpleqa", "SimpleQA Verified",
         "Short factual questions with verified answers. Run by Epoch AI."),
    "Chess Puzzles":
        ("epoch_chess", "Chess Puzzles",
         "Tactical chess positions. Run by Epoch AI."),
    "Mystery Game Puzzles":
        ("epoch_mystery", "Mystery Game Puzzles",
         "Deductive reasoning puzzles. Run by Epoch AI."),
}

# Epoch writes effort as a suffix on the model id.
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}


def split_model(mid: str) -> tuple[str, str | None]:
    """'gpt-5-2025-08-07_high' -> ('gpt-5', 'high'); 'zai-org/GLM-4.6' -> ('glm-4-6', None)."""
    mid = mid.split("/", 1)[-1].strip().lower()
    effort = None
    if "_" in mid:
        head, tail = mid.rsplit("_", 1)
        if tail in EFFORTS:
            mid, effort = head, (None if tail == "none" else tail)
    mid = re.sub(r"-20\d{2}-\d{2}-\d{2}$", "", mid)       # -2025-08-07
    mid = re.sub(r"[.\s_]+", "-", mid)
    mid = re.sub(r"[^a-z0-9-]", "", mid)
    return re.sub(r"-+", "-", mid).strip("-"), effort


def _number(row: dict, *keys: str) -> float | None:
    for k in keys:
        v = (row.get(k) or "").strip()
        if v:
            try:
                return float(v)
            except ValueError:
                continue
    return None


def parse(csv_text: str) -> dict:
    """Return {(base, effort): {metric: score}}."""
    scores: dict[tuple[str, str | None], dict[str, float]] = {}

    for row in csv.DictReader(io.StringIO(csv_text)):
        base, effort = split_model(row.get("model") or "")
        if not base:
            continue

        spec = TASKS.get((row.get("task") or "").strip())
        if not spec:
            continue
        score = _number(row, "best_score", "Best score (across scorers)", "mean_score")
        if score is None:
            continue
        if score > 1.0:                       # a few tasks are scored out of 100
            score /= 100.0
        bucket = scores.setdefault((base, effort), {})
        # keep the best run when a model was evaluated more than once
        bucket[spec[0]] = max(bucket.get(spec[0], 0.0), score)

    return scores


def metrics() -> list[tuple[str, str, str, str]]:
    """The capability metrics this source contributes, in build.py's shape."""
    return [(key, label, "frac", help_) for key, label, help_ in TASKS.values()]
