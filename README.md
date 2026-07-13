# 🏏 Cricket Player Sentiment Analysis Dashboard

A Flask web application that ingests public cricket commentary, scores it with a
**cricket-aware sentiment engine**, and ranks players by a time-decayed
**Public Sentiment Index (PSI)**. The dashboard visualises live rankings,
per-player sentiment trends, and match-event overlays using Chart.js.

The engine understands cricket jargon that generic sentiment tools get wrong —
it knows a *"golden duck"* is strongly negative while a *"fifer"*, *"maiden over"*,
or *"cover drive"* is strongly positive.

---

## Features

- **Live player ranking table** — a leaderboard ordered by each player's current PSI.
- **Sentiment trend line** — a time-series chart of a player's sentiment over the innings/tournament.
- **Sentiment distribution** — the positive / neutral / negative split per player.
- **Match-event overlays** — markers (e.g. *"Hit a Six"*, *"Dropped Catch"*) that explain sudden spikes or dips.
- **Ad-hoc analysis endpoint** — score arbitrary commentary text on demand via `POST /api/analyze`.

## How it works

The pipeline runs in four stages:

1. **Ingestion** — commentary is loaded into SQLite (`ingest.py` ships with a
   sample dataset; a production deployment would swap in a worker pulling from
   Reddit / Twitter / news comment sections).
2. **Entity extraction & scoring** — `CricketSentimentEngine` extracts player
   names via regex and scores text with **VADER augmented by a cricket lexicon**
   of domain-specific phrases. Optionally, set `OLLAMA_MODEL` to route scoring
   through a local [Ollama](https://ollama.com) LLM (it falls back to the
   rule-based scorer if Ollama is unreachable).
3. **Aggregation** — scores are grouped per player and combined into a PSI using
   an exponential **time decay** (72-hour half-life), so recent sentiment counts
   more than old sentiment.
4. **Serving & visualisation** — Flask exposes JSON APIs that the Chart.js
   frontend consumes.

## Tech stack

| Layer            | Technology                                   |
| ---------------- | -------------------------------------------- |
| Backend          | Flask (Python)                               |
| Sentiment engine | vaderSentiment + custom cricket lexicon; optional Ollama LLM |
| Storage          | SQLite                                        |
| Visualisation    | Chart.js (vanilla JS frontend)               |

## Project structure

```
cricket_sentiment_analysis/
├── app.py                # Flask app & API routes
├── models.py             # SQLite schema and data-access helpers
├── ingest.py             # Seeds sample players, comments, and match events
├── sentiment_engine.py   # Cricket-aware sentiment + entity extraction
├── aggregator.py         # PSI, time decay, trends, distributions
├── cricket_sentiment.db  # Pre-seeded SQLite database
├── requirements.txt
├── templates/index.html  # Dashboard page
└── static/               # CSS and JS (Chart.js frontend)
```

## Getting started

### Prerequisites
- Python 3.10+

### Installation

```bash
# 1. Create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

### Run the app

The repository ships with a pre-seeded `cricket_sentiment.db`, so you can start
straight away:

```bash
python app.py
```

Then open <http://127.0.0.1:1998> in your browser.

To regenerate the database from the bundled sample data (or after changing the
sample set), run:

```bash
python ingest.py
```

### Optional: use a local LLM for scoring

```bash
# Point the engine at a running Ollama server
export OLLAMA_MODEL=llama3.1          # Windows: set OLLAMA_MODEL=llama3.1
# export OLLAMA_URL=http://localhost:11434/api/generate  # default
python app.py
```

## API reference

| Method | Endpoint                        | Description                                        |
| ------ | ------------------------------- | -------------------------------------------------- |
| `GET`  | `/`                             | Dashboard UI                                       |
| `GET`  | `/api/rankings`                 | Ranked players by PSI + overall stats              |
| `GET`  | `/api/players`                  | All tracked players                                |
| `GET`  | `/api/player/<id>/trends`       | Trend line, match events, and distribution         |
| `GET`  | `/api/player/<id>/comments`     | All comments for a player                          |
| `POST` | `/api/analyze`                  | Score arbitrary text — body: `{"text": "..."}`     |

## License

No license has been specified for this project yet.
