"""Cricket-aware sentiment engine + player entity extraction.

Default path: VADER + a cricket lexicon that overrides/augments generic scores
for domain-specific jargon (e.g., "golden duck" = strongly negative,
"fifer"/"maiden over" = strongly positive).

Ollama path: set OLLAMA_MODEL env var (e.g. "llama3.1") and the engine will
POST to a local Ollama server for scoring. Falls back to the rule-based
scorer if Ollama is unreachable.
"""

from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from typing import Iterable

import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# Cricket-specific sentiment lexicon. Scores are in VADER-space
# (roughly -4 to +4 per token, aggregated by VADER into -1..+1 compound).
CRICKET_LEXICON: dict[str, float] = {
    # Batting positives
    "century": 3.5, "hundred": 3.2, "double century": 4.0, "fifty": 2.2,
    "half century": 2.2, "six": 2.5, "sixes": 2.8, "boundary": 1.8,
    "boundaries": 2.0, "cover drive": 2.5, "helicopter shot": 2.6,
    "masterclass": 3.8, "anchor": 1.5, "clutch": 2.4, "match winner": 3.5,
    # Batting negatives
    "duck": -3.0, "golden duck": -3.8, "diamond duck": -3.5,
    "collapse": -2.8, "collapsed": -2.8, "dismissed": -1.2,
    "clean bowled": -2.2, "lbw": -1.5, "run out": -1.8, "runout": -1.8,
    "chase choke": -3.0, "flop": -2.5, "poor shot": -2.0,
    # Bowling positives
    "fifer": 3.8, "five wicket haul": 3.8, "five wickets": 3.5,
    "hat trick": 3.9, "hat-trick": 3.9, "maiden": 2.0, "maiden over": 2.5,
    "yorker": 2.2, "dot ball": 1.2, "wicket": 2.0, "wickets": 2.2,
    "economical": 1.8, "unplayable": 3.0,
    # Bowling negatives
    "no ball": -1.8, "no-ball": -1.8, "wide": -1.0, "wides": -1.2,
    "expensive": -2.0, "leaked runs": -2.4, "gave away": -1.8,
    "conceded": -1.2, "smashed": -2.2, "hammered": -2.5,
    # Fielding
    "dropped catch": -3.0, "dropped": -1.8, "spilled": -1.5,
    "misfield": -1.6, "brilliant catch": 3.2, "stunning catch": 3.4,
    "diving catch": 2.8, "runout effort": 2.0,
    # Misc
    "player of the match": 3.8, "match winner": 3.5, "clutch performance": 3.2,
    "underperformed": -2.4, "off day": -1.8, "shambles": -3.0,
    "brilliant": 2.5, "sublime": 2.8, "world class": 3.0,
}


@dataclass
class SentimentResult:
    text: str
    player: str | None
    score: float  # -1.0 .. +1.0
    label: str    # positive | neutral | negative


class CricketSentimentEngine:
    def __init__(self, players: Iterable[str]):
        self.vader = SentimentIntensityAnalyzer()
        # Fold the cricket lexicon into VADER so multi-word phrases still bias
        # the compound score. VADER's lexicon supports single tokens, so we
        # additionally do a pre-pass boost for phrases in `_phrase_boost`.
        for token, score in CRICKET_LEXICON.items():
            if " " not in token and "-" not in token:
                self.vader.lexicon[token] = score
        self._phrase_lexicon = {
            k: v for k, v in CRICKET_LEXICON.items() if " " in k or "-" in k
        }
        # Sort players longest-first so "Rohit Sharma" wins over "Rohit"
        self.players = sorted(set(players), key=len, reverse=True)
        self._player_patterns = [
            (name, re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE))
            for name in self.players
        ]
        self.ollama_model = os.environ.get("OLLAMA_MODEL")
        self.ollama_url = os.environ.get(
            "OLLAMA_URL", "http://localhost:11434/api/generate"
        )

    # ---------- entity extraction ----------
    def extract_players(self, text: str) -> list[str]:
        hits: list[str] = []
        for name, pattern in self._player_patterns:
            if pattern.search(text):
                hits.append(name)
        return hits

    # ---------- sentiment ----------
    def score(self, text: str) -> float:
        if self.ollama_model:
            ollama_score = self._score_ollama(text)
            if ollama_score is not None:
                return ollama_score
        return self._score_rulebased(text)

    def _score_rulebased(self, text: str) -> float:
        boost = 0.0
        lower = text.lower()
        for phrase, weight in self._phrase_lexicon.items():
            if phrase in lower:
                # Normalize phrase weight into compound-space (-1..+1)
                boost += weight / 4.0
        vader_score = self.vader.polarity_scores(text)["compound"]
        combined = vader_score + boost
        return max(-1.0, min(1.0, combined))

    def _score_ollama(self, text: str) -> float | None:
        prompt = (
            "You are a cricket sentiment analyzer. Reply with ONLY a JSON "
            'object of the form {"score": <float between -1 and 1>}. '
            "Positive means the described player performance is praiseworthy. "
            f"Text: {text}"
        )
        try:
            resp = requests.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=8,
            )
            resp.raise_for_status()
            payload = resp.json()
            data = json.loads(payload.get("response", "{}"))
            score = float(data.get("score", 0.0))
            return max(-1.0, min(1.0, score))
        except Exception:
            return None

    # ---------- combined ----------
    def analyze(self, text: str) -> list[SentimentResult]:
        players = self.extract_players(text)
        score = self.score(text)
        label = (
            "positive" if score > 0.15
            else "negative" if score < -0.15
            else "neutral"
        )
        if not players:
            return [SentimentResult(text=text, player=None, score=score, label=label)]
        return [
            SentimentResult(text=text, player=p, score=score, label=label)
            for p in players
        ]
