"""Ingest sample cricket commentary into the SQLite store.

Real deployments would replace the SAMPLE_COMMENTS block with a Celery
worker pulling from Reddit / Twitter / news comment sections. The rest of
this pipeline (entity extraction, scoring, storage) stays identical.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from models import (
    init_db,
    upsert_player,
    insert_comment,
    insert_match_event,
    all_players,
)
from sentiment_engine import CricketSentimentEngine


PLAYERS = [
    {"name": "Virat Kohli",       "team": "India",    "role": "Batter"},
    {"name": "Rohit Sharma",      "team": "India",    "role": "Batter"},
    {"name": "Jasprit Bumrah",    "team": "India",    "role": "Bowler"},
    {"name": "Hardik Pandya",     "team": "India",    "role": "All-rounder"},
    {"name": "Rishabh Pant",      "team": "India",    "role": "Wicket-keeper"},
    {"name": "Harshal Patel",     "team": "India",    "role": "Bowler"},
    {"name": "Bhuvneshwar Kumar", "team": "India",    "role": "Bowler"},
    {"name": "Shubman Gill",      "team": "India",    "role": "Batter"},
    {"name": "Babar Azam",        "team": "Pakistan", "role": "Batter"},
    {"name": "Steve Smith",       "team": "Australia","role": "Batter"},
    {"name": "Pat Cummins",       "team": "Australia","role": "Bowler"},
    {"name": "Joe Root",          "team": "England",  "role": "Batter"},
]


# Sample commentary — mix of positive, negative, and neutral cricket takes.
# Each tuple: (text, source, hours_ago).
SAMPLE_COMMENTS: list[tuple[str, str, float]] = [
    ("Virat Kohli's cover drive was absolutely sublime, world class batting on display!", "reddit", 1),
    ("Kohli anchoring the chase like only he can, this is clutch.", "twitter", 2),
    ("Virat Kohli threw it away with a poor shot, huge disappointment.", "reddit", 20),
    ("Kohli scored a brilliant century, absolute masterclass.", "news", 5),
    ("Kohli looked out of touch today, off day for the great one.", "twitter", 48),

    ("Rohit Sharma smashed three sixes in one over, unreal power hitting!", "twitter", 3),
    ("Rohit dismissed early for a golden duck, terrible start for India.", "reddit", 30),
    ("Rohit Sharma's captaincy is world class, brilliant field placements.", "news", 12),
    ("Rohit collapsed under pressure, dropped catch too. Off day.", "reddit", 72),
    ("Hit man Rohit Sharma with another hundred!", "twitter", 6),

    ("Jasprit Bumrah bowled an unplayable yorker, took a wicket first ball!", "reddit", 2),
    ("Bumrah with a fifer! Absolute demolition job.", "twitter", 4),
    ("Bumrah conceded 20 in an over, expensive spell today.", "reddit", 25),
    ("Bumrah's yorker in the death overs, sublime bowling.", "news", 8),
    ("Bumrah bowled a no ball at a crucial moment, poor discipline.", "twitter", 40),

    ("Hardik Pandya hit the winning six! Match winner as always.", "twitter", 1),
    ("Pandya dropped a sitter, that could cost India the match.", "reddit", 15),
    ("Hardik with a brilliant catch at long on, incredible athleticism.", "news", 3),
    ("Hardik Pandya underperformed today, needs to work on his batting.", "reddit", 55),

    ("Rishabh Pant played the helicopter shot, what a talent!", "twitter", 2),
    ("Pant with a stunning catch behind the stumps.", "reddit", 5),
    ("Rishabh Pant got clean bowled by a peach of a delivery.", "news", 30),

    ("Harshal Patel took a hat trick! Absolute magic.", "reddit", 6),
    ("Harshal was hammered for 50 in 3 overs, poor bowling.", "twitter", 45),

    ("Bhuvneshwar Kumar swinging it both ways, unplayable spell!", "reddit", 4),
    ("Bhuvi with a maiden over in the powerplay, brilliant discipline.", "news", 12),

    ("Shubman Gill's cover drive is a thing of beauty, sublime touch.", "twitter", 2),
    ("Gill dismissed early again, form is a concern.", "reddit", 25),
    ("Shubman Gill scored a brilliant hundred, future superstar!", "news", 10),

    ("Babar Azam masterclass, elegant batting at its finest.", "twitter", 3),
    ("Babar with a poor shot selection, gave his wicket away.", "reddit", 28),

    ("Steve Smith's technique is world class, sublime batting.", "news", 6),
    ("Smith looked off today, dismissed cheaply.", "twitter", 30),

    ("Pat Cummins bowled a fifer, absolute demolition!", "reddit", 8),
    ("Cummins conceded runs freely today, expensive spell.", "twitter", 36),

    ("Joe Root's technique is sublime, world class player.", "news", 5),
    ("Root got clean bowled by a beauty, tough luck.", "reddit", 22),
]


# Match events tied to specific players — will be plotted as overlays.
SAMPLE_EVENTS: list[tuple[str, str, str, float]] = [
    ("Virat Kohli", "Hit a Six", "Massive six over long-on off Cummins", 1.5),
    ("Virat Kohli", "Dropped Catch", "Dropped a regulation catch at slip", 20.5),
    ("Rohit Sharma", "Hit a Six", "Six over deep midwicket", 3.2),
    ("Rohit Sharma", "Dismissed", "Golden duck to first ball", 30.1),
    ("Jasprit Bumrah", "Wicket", "Bowled with a searing yorker", 2.1),
    ("Jasprit Bumrah", "No Ball", "No ball at crucial moment", 40.2),
    ("Hardik Pandya", "Winning Six", "Hit the winning runs", 1.1),
    ("Hardik Pandya", "Dropped Catch", "Dropped a sitter at deep", 15.3),
]


def seed_players() -> dict[str, int]:
    ids: dict[str, int] = {}
    for p in PLAYERS:
        pid = upsert_player(p["name"], team=p["team"], role=p["role"])
        ids[p["name"]] = pid
    return ids


def _wobble(hours_ago: float) -> datetime:
    # Add small jitter to look more natural in trend charts
    jitter_minutes = random.uniform(-15, 15)
    return datetime.now(timezone.utc) - timedelta(hours=hours_ago, minutes=jitter_minutes)


def run() -> None:
    init_db()
    player_ids = seed_players()
    engine = CricketSentimentEngine(players=list(player_ids.keys()))

    random.seed(42)
    for text, source, hours_ago in SAMPLE_COMMENTS:
        ts = _wobble(hours_ago)
        results = engine.analyze(text)
        for res in results:
            pid = player_ids.get(res.player) if res.player else None
            insert_comment(
                player_id=pid,
                text=text,
                source=source,
                score=res.score,
                label=res.label,
                created_at=ts,
            )

    for player_name, event_type, description, hours_ago in SAMPLE_EVENTS:
        pid = player_ids.get(player_name)
        if pid is None:
            continue
        insert_match_event(
            player_id=pid,
            event_type=event_type,
            description=description,
            occurred_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        )

    n_players = len(all_players())
    print(f"Seeded {n_players} players and {len(SAMPLE_COMMENTS)} comments.")


if __name__ == "__main__":
    run()
