"""Parameter counts, so the site can filter to models that fit a given GPU.

Counts come from Hugging Face, which reports exact totals for open-weight
repositories, with Epoch AI's figures as a fallback. Results are cached on disk
because the count for a released model never changes.
"""
from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request

API = "https://huggingface.co/api/models/"
UA = "model-frontier (https://github.com/daxmavy/model-frontier)"

# Bytes per parameter for the weights alone. Activations and the KV cache are
# extra, which the 1.2 headroom factor below is meant to cover.
BYTES = {"bf16": 2.0, "fp8": 1.0, "int4": 0.5}
HEADROOM = 1.2


def vram_gb(params: float, precision: str = "bf16") -> float:
    """Rough GPU memory needed to serve a model of this size."""
    return params * BYTES[precision] * HEADROOM / 1e9


def fetch_params(hf_id: str, timeout: int = 20) -> float | None:
    req = urllib.request.Request(API + hf_id, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.load(r)
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None
    total = (body.get("safetensors") or {}).get("total")
    return float(total) if isinstance(total, (int, float)) and total > 1e6 else None


def resolve(hf_ids: list[str], cache_path: pathlib.Path,
            fallback: dict[str, float] | None = None) -> dict[str, float]:
    """Parameter count per Hugging Face id, fetching only ids not already cached.

    A repository that reports no count is cached as a null so it is not retried
    every day.
    """
    cache: dict[str, float | None] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
        except ValueError:
            cache = {}

    for hf_id in hf_ids:
        if hf_id in cache:
            continue
        cache[hf_id] = fetch_params(hf_id)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=0, sort_keys=True))

    out = {k: v for k, v in cache.items() if v}
    for k, v in (fallback or {}).items():
        out.setdefault(k, v)
    return out
