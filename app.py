"""Flask backend for the Cricket Player Sentiment Dashboard."""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request, abort

from aggregator import (
    rankings,
    player_trend,
    distribution,
    overall_stats,
)
from models import (
    init_db,
    player_by_id,
    events_for_player,
    comments_for_player,
    all_players,
)
from sentiment_engine import CricketSentimentEngine


app = Flask(__name__)


def get_engine() -> CricketSentimentEngine:
    if not hasattr(app, "_engine") or app._engine is None:
        names = [p["name"] for p in all_players()]
        app._engine = CricketSentimentEngine(players=names)
    return app._engine


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/rankings")
def api_rankings():
    return jsonify({"rankings": rankings(), "overall": overall_stats()})


@app.route("/api/players")
def api_players():
    return jsonify({"players": all_players()})


@app.route("/api/player/<int:pid>/trends")
def api_player_trends(pid: int):
    player = player_by_id(pid)
    if not player:
        abort(404)
    bucket = int(request.args.get("bucket", 60))
    trend = player_trend(pid, bucket_minutes=bucket)
    events = events_for_player(pid)
    return jsonify({
        "player": player,
        "trend": trend,
        "events": events,
        "distribution": distribution(pid),
    })


@app.route("/api/player/<int:pid>/comments")
def api_player_comments(pid: int):
    if not player_by_id(pid):
        abort(404)
    return jsonify({"comments": comments_for_player(pid)})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Score arbitrary commentary on demand — useful for ad-hoc testing."""
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400
    results = get_engine().analyze(text)
    return jsonify({
        "results": [
            {"player": r.player, "score": r.score, "label": r.label}
            for r in results
        ]
    })


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "not found"}), 404


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=1998, debug=True)
