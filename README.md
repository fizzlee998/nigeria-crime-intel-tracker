# Nigeria Crime Intelligence Tracker

An agentic AI pipeline that automatically monitors Nigerian news sources, identifies crime-related headlines, extracts structured incident data using AI, and displays it on a live dashboard — with zero manual input after startup.

## What it does

1. **Fetches** live headlines from Nigerian news RSS feeds (Punch, Vanguard, Premium Times)
2. **Filters** them for crime relevance using keyword matching, to avoid wasting AI calls on irrelevant news
3. **Classifies** matching headlines using Google's Gemini API, extracting:
   - Crime type (robbery, kidnapping)
   - Location
   - Confidence level
   - One-line summary
4. **Deduplicates** against existing records before saving
5. **Stores** structured results in a SQLite database
6. **Displays** everything on a live, auto-updating web dashboard
7. **Repeats automatically** every hour via a background scheduler — no manual re-running required

## Why this exists

Crime reporting in Nigerian news is scattered across dozens of outlets, in unstructured prose, with no central place to see patterns. This project is a prototype for turning that raw news flow into structured, searchable crime intelligence — a foundation for the kind of evidence-based crime analysis used by researchers, NGOs, journalists, and policy analysts.

## Tech stack

- **Python** — core pipeline
- **feedparser** — RSS ingestion
- **Google Gemini API** (gemini-2.5-flash) — headline classification
- **SQLite** — structured storage
- **Flask** — live dashboard
- **schedule** — automatic hourly re-runs

## Architecture


## Setup

1. Clone the repo
2. Install dependencies:

3. Create a `.env` file with a free Gemini API key from [aistudio.google.com](https://aistudio.google.com):
4. Initialize the database:
5. Run the app:
6. Open `http://127.0.0.1:5000` in your browser

## Current scope (MVP)

- Nigeria only
- Two crime categories: robbery, kidnapping
- Three news sources
- Keyword-based pre-filtering (not yet ML-based)

## Roadmap

- [ ] Expand RSS source coverage
- [ ] Expand crime category taxonomy
- [ ] Add maps/charts for geographic and trend visualization
- [ ] Add downloadable reports (PDF/Excel)
- [ ] Add source verification / cross-referencing before publication

## Author

Built by Abdulafeez as part of an ongoing effort to build practical tools for crime intelligence and evidence-based policing in Nigeria.