# System Design & Architecture: Cricket Player Sentiment Analysis Dashboard

## 1. Overview
This document outlines the architecture and implementation steps for building a sentimental analysis dashboard focused on cricket player performances. The system ingests public commentary, processes the text to gauge sentiment specific to cricket context, and ranks players dynamically based on these public perceptions.

## 2. Technology Stack

To ensure modularity, high performance, and precise domain adaptation, the following stack is utilized:

* **Backend Framework:** **Flask** (Python) - Serves as the lightweight backend to handle API routing, data aggregation, and serving the UI templates.
* **NLP & Sentiment Engine:** **Local LLM (Ollama / Hugging Face)** - Instead of relying on generic cloud APIs, a local LLM architecture is deployed. This allows for training and fine-tuning by feeding the model cricket-specific terminologies. It ensures the model accurately interprets domain-specific jargon (e.g., recognizing that "getting a golden duck" is negative, while "bowling a maiden" or taking a "fifer" is highly positive). 
* **Data Visualization:** **Chart.js** - The recommended charting library for the UI development. It integrates seamlessly with the Flask backend to render responsive, visually appealing data representations like sentiment trend lines and ranking bar charts.
* **Data Processing:** Pandas & NumPy for aggregating sentiment scores and managing ranking matrices.

## 3. System Architecture Pipeline

### Phase 1: Data Ingestion
* **Sources:** Match day threads (Reddit), public social media feeds (Twitter/X APIs), and cricket news comment sections.
* **Process:** A background worker (e.g., Celery) scrapes or ingests live text data during and after a match.

### Phase 2: Entity Extraction & Sentiment Scoring
* **Entity Resolution:** The local LLM acts as the base model for entity extraction, pulling out specific player names (e.g., distinguishing "Harshal Patel" or "Bhuvneshwar Kumar" from the general text).
* **Sentiment Inference:** The text is passed through the cricket-trained local LLM inference model to output a sentiment polarity score ranging from -1.0 (Highly Negative) to +1.0 (Highly Positive).

### Phase 3: Aggregation & Ranking Algorithm
* Scores are grouped by player and time-decayed (recent sentiments carry more weight than sentiments from weeks ago).
* A weighted average calculates the final "Public Sentiment Index" (PSI) for each player.

### Phase 4: Flask Backend & Chart.js UI
* Flask routes (e.g., `/api/rankings`, `/api/player/<id>/trends`) serve the JSON data.
* The frontend consumes this data using JavaScript and renders the dashboard using **Chart.js**.

## 4. Dashboard UI Components

1.  **Live Player Ranking Table:** A dynamic leaderboard sorting players by their current PSI. 
2.  **Sentiment Trend Line (Chart.js):** A time-series line chart tracking a specific player's sentiment over the course of an innings or a tournament.
3.  **Sentiment Distribution (Chart.js):** A doughnut chart for individual players showing the split of Positive, Neutral, and Negative mentions.
4.  **Match Context Overlays:** Markers on the charts indicating specific match events (e.g., "Dropped Catch" or "Hit a Six") to explain sudden spikes or dips in sentiment.

## 5. Deployment Considerations
* Ensure the host machine or instance has sufficient GPU VRAM to run the local Ollama/Hugging Face models efficiently for real-time inference.
* Use SQLite or PostgreSQL to cache the sentiment scores, preventing the need to re-run expensive LLM inferences on historical data.

