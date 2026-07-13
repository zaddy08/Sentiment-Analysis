"""Public Sentiment Index (PSI) aggregation with time decay.

PSI = weighted mean of sentiment scores, where recent comments carry more
weight than older ones. A half-life of ~72 hours means a comment from 3 days
ago contributes half as much as a fresh one.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from models import all_comments, all_players, comments_for_player

HALF_LIFE_HOURS = 72.0
DECAY_LAMBDA = math.log(2) / HALF_LIFE_HOURS


def _parse_ts(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(str(value))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _weight_for(created_at: datetime, now: datetime) -> float:
    age_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)
    return math.exp(-DECAY_LAMBDA * age_hours)


def compute_psi(comments: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not comments:
        return {"psi": 0.0, "mentions": 0, "positive": 0, "neutral": 0, "negative": 0}
    weighted_sum = 0.0
    weight_total = 0.0
    dist = {"positive": 0, "neutral": 0, "negative": 0}
    for c in comments:
        w = _weight_for(_parse_ts(c["created_at"]), now)
        weighted_sum += c["score"] * w
        weight_total += w
        dist[c["label"]] = dist.get(c["label"], 0) + 1
    psi = weighted_sum / weight_total if weight_total > 0 else 0.0
    return {
        "psi": round(psi, 4),
        "mentions": len(comments),
        **dist,
    }


def rankings() -> list[dict]:
    """Ranked list of players by PSI descending."""
    results: list[dict] = []
    now = datetime.now(timezone.utc)
    for p in all_players():
        stats = compute_psi(comments_for_player(p["id"]), now=now)
        if stats["mentions"] == 0:
            continue
        results.append({
            "player_id": p["id"],
            "name": p["name"],
            "team": p["team"],
            "role": p["role"],
            **stats,
        })
    results.sort(key=lambda r: r["psi"], reverse=True)
    for i, r in enumerate(results, start=1):
        r["rank"] = i
    return results


def player_trend(player_id: int, bucket_minutes: int = 60) -> list[dict]:
    """Time-bucketed sentiment trend for one player (bucket = N minutes)."""
    comments = comments_for_player(player_id)
    if not comments:
        return []
    bucket = timedelta(minutes=bucket_minutes)
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for c in comments:
        ts = _parse_ts(c["created_at"])
        # Floor timestamp to the start of its bucket.
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        n_buckets = int((ts - epoch).total_seconds() // (bucket_minutes * 60))
        bucket_start = epoch + n_buckets * bucket
        buckets[bucket_start].append(c["score"])
    return [
        {"t": ts.isoformat(), "score": round(sum(scores) / len(scores), 4)}
        for ts, scores in sorted(buckets.items())
    ]


def distribution(player_id: int) -> dict:
    comments = comments_for_player(player_id)
    dist = {"positive": 0, "neutral": 0, "negative": 0}
    for c in comments:
        dist[c["label"]] = dist.get(c["label"], 0) + 1
    return dist


def overall_stats() -> dict:
    comments = all_comments()
    total = len(comments)
    dist = {"positive": 0, "neutral": 0, "negative": 0}
    for c in comments:
        dist[c["label"]] = dist.get(c["label"], 0) + 1
    return {
        "total_comments": total,
        "tracked_players": len([p for p in all_players()]),
        **dist,
    }
