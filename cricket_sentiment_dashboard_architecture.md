# System Design & Architecture: Cricket Player Sentiment Analysis Dashboard

## 1. Overview
This document outlines the architecture of the Cricket Player Sentiment Analysis Dashboard. The system ingests public cricket commentary, processes the text to gauge sentiment specific to the cricket context, and ranks players dynamically based on public perception.

> **Implementation status:** Sections below distinguish what is **implemented today** from what is **planned** for a production deployment. The current codebase is a self-contained Flask app that runs on a pre-seeded SQLite database with a rule-based (VADER + cricket lexicon) sentiment engine.

## 2. Technology Stack

The stack favours a lightweight, dependency-light design with an optional path to a local LLM:

* **Backend Framework:** **Flask** (Python) — a lightweight backend that handles API routing, data aggregation, and serving the UI template.
* **NLP & Sentiment Engine:** A **rule-based cricket-aware scorer** built on **[vaderSentiment](https://github.com/cjhutto/vaderSentiment)** augmented with a custom **cricket lexicon**. This overrides/augments generic scores for domain-specific jargon (e.g., "golden duck" is strongly negative, while "fifer", "maiden over", or "cover drive" is strongly positive). Player **entity extraction** is done with **regex** name matching, not an LLM.
  * *Optional LLM path:* setting the `OLLAMA_MODEL` environment variable routes scoring through a local [Ollama](https://ollama.com) server. If Ollama is unreachable, the engine automatically falls back to the rule-based scorer.
* **Data Visualization:** **Chart.js** — renders the ranking table, sentiment trend lines, and distribution charts in a vanilla-JS frontend served by Flask.
* **Data Processing:** Plain Python standard library (`math`, `collections`, `datetime`) for aggregating sentiment scores and computing rankings — no heavyweight data-frame dependencies.
* **Storage:** **SQLite** (`cricket_sentiment.db`) caches players, scored comments, and match events so sentiment does not need to be recomputed on every request.

## 3. System Architecture Pipeline

### Phase 1: Data Ingestion
* **Implemented:** `ingest.py` seeds the database with a curated **sample dataset** of players, commentary, and match events. Each comment is scored at ingest time and cached in SQLite.
* **Planned:** Replace the sample block with a background worker (e.g., Celery) that pulls live text from match-day threads (Reddit), social feeds (Twitter/X), and cricket news comment sections. The downstream pipeline (extraction, scoring, storage) stays identical.

### Phase 2: Entity Extraction & Sentiment Scoring
* **Entity Resolution:** Player names are extracted with case-insensitive **regex matching** against the roster, sorted longest-first so multi-word names (e.g., "Rohit Sharma") take precedence over partial matches ("Rohit").
* **Sentiment Inference:** Text is scored to a polarity in the range **-1.0 (Highly Negative) to +1.0 (Highly Positive)**:
  * *Default:* VADER's compound score, with single-token cricket terms folded into VADER's lexicon and multi-word cricket phrases applied as an additional boost.
  * *Optional:* a local Ollama LLM, when `OLLAMA_MODEL` is set.
* A comment is labelled `positive` (> 0.15), `negative` (< -0.15), or `neutral` otherwise.

### Phase 3: Aggregation & Ranking Algorithm
* Scores are grouped by player and **time-decayed** using an exponential weight with a **72-hour half-life** — a comment from 3 days ago contributes half as much as a fresh one.
* A weighted mean produces the final **Public Sentiment Index (PSI)** per player, which drives the ranking (`aggregator.py`).

### Phase 4: Flask Backend & Chart.js UI
* Flask routes serve JSON consumed by the frontend:
  * `GET /api/rankings` — players ranked by PSI plus overall stats.
  * `GET /api/players` — all tracked players.
  * `GET /api/player/<id>/trends` — time-bucketed trend, match events, and distribution.
  * `GET /api/player/<id>/comments` — raw comments for a player.
  * `POST /api/analyze` — score arbitrary commentary text on demand.
* The frontend consumes this data with JavaScript and renders the dashboard using **Chart.js**.

## 4. Dashboard UI Components

1. **Live Player Ranking Table:** a dynamic leaderboard sorting players by their current PSI.
2. **Sentiment Trend Line (Chart.js):** a time-series line chart tracking a player's sentiment across time buckets.
3. **Sentiment Distribution (Chart.js):** a chart showing the split of Positive, Neutral, and Negative mentions for a player.
4. **Match Context Overlays:** markers on the charts indicating specific match events (e.g., "Dropped Catch" or "Hit a Six") to explain sudden spikes or dips in sentiment.

## 5. Deployment Considerations
* The default rule-based engine is CPU-only and has no special hardware requirements — it runs anywhere Python does.
* SQLite caches scored comments and events, avoiding recomputation on historical data. For higher write concurrency (e.g., live ingestion), migrating to PostgreSQL is a natural next step.
* **Only if** the optional Ollama LLM path is enabled does the host need sufficient GPU/CPU resources to run the chosen model for inference.
