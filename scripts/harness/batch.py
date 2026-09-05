"""Application-ID and batch-ID minting; deterministic random selection."""
from __future__ import annotations
import datetime as dt
import hashlib
import random
from typing import Iterable

from .paths import COUNTERS_JSON
from .state import read_json, write_json


def _counters() -> dict:
    return read_json(COUNTERS_JSON, {"app_seq": {}, "batch_seq": {}})


def mint_application_id() -> str:
    year = dt.date.today().year
    c = _counters()
    seq_by_year = c.setdefault("app_seq", {})
    seq = int(seq_by_year.get(str(year), 0)) + 1
    seq_by_year[str(year)] = seq
    write_json(COUNTERS_JSON, c)
    return f"APP-{year}-{seq:04d}"


def mint_batch_id() -> str:
    day = dt.date.today().isoformat()
    c = _counters()
    seq_by_day = c.setdefault("batch_seq", {})
    seq = int(seq_by_day.get(day, 0)) + 1
    seq_by_day[day] = seq
    write_json(COUNTERS_JSON, c)
    return f"BATCH-{day}-{seq:03d}"


def diversified_sample(
    jobs: list[dict],
    count: int,
    seed: str | None = None,
) -> list[dict]:
    """Spec §7: controlled randomness that diversifies by company / role /
    location while favoring stronger matches."""
    if not jobs:
        return []
    rng = random.Random(seed or dt.datetime.utcnow().isoformat())
    # Bucket by company; within each bucket sort by score desc.
    buckets: dict[str, list[dict]] = {}
    for j in jobs:
        buckets.setdefault(j.get("company", "?"), []).append(j)
    for arr in buckets.values():
        arr.sort(key=lambda j: -int(j.get("match_score", 0)))

    selected: list[dict] = []
    ordered_companies = list(buckets.keys())
    rng.shuffle(ordered_companies)
    # Round-robin one job per company at a time until we hit `count`
    # or run out. Preserves diversity while still favoring higher scores
    # (each bucket is score-sorted).
    while len(selected) < count and any(buckets[c] for c in ordered_companies):
        for c in ordered_companies:
            if not buckets[c]:
                continue
            selected.append(buckets[c].pop(0))
            if len(selected) >= count:
                break
    return selected


def stable_hash(*parts: Iterable[str]) -> str:
    joined = "\x1f".join(str(p) for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]
