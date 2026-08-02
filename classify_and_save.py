import os
import json
import re
import sqlite3
import time
import psycopg2
from difflib import SequenceMatcher
from datetime import date
from dotenv import load_dotenv
from groq import Groq

from fetch_headlines import fetch_all_headlines, filter_crime_related

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
DATABASE_URL = os.environ.get("DATABASE_URL")

DUPLICATE_SIMILARITY_THRESHOLD = 0.80

STOPWORDS = {"a", "an", "the", "in", "on", "at", "to", "of", "for", "and",
             "or", "as", "by", "with", "after", "over", "amid", "amidst"}


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect("crime_intel.db")


def normalize_title(title):
    words = re.findall(r"[a-z0-9]+", title.lower())
    words = [w for w in words if w not in STOPWORDS]
    return " ".join(sorted(words))


def similar_headline_exists(cursor, title):
    normalized_new = normalize_title(title)
    cursor.execute("SELECT title FROM headlines")
    for (existing_title,) in cursor.fetchall():
        normalized_existing = normalize_title(existing_title)
        ratio = SequenceMatcher(None, normalized_new, normalized_existing).ratio()
        if ratio >= DUPLICATE_SIMILARITY_THRESHOLD:
            return True
    return False


def classify_headline(headline):
    prompt = f"""
You are a crime intelligence classifier for Nigerian news headlines.

Read this headline and return ONLY valid JSON, no extra text, no markdown formatting.

Headline: "{headline}"

Return JSON in exactly this format:
{{
  "crime_type": "one of: robbery, kidnapping, homicide, terrorism, armed_attack, other",
  "location": "city or state mentioned, or 'unknown' if none",
  "confidence": "high, medium, or low",
  "summary": "one sentence summary of the incident"
}}

Category guide:
- robbery: theft, burglary, armed robbery of property/money
- kidnapping: abduction, hostage-taking, ransom situations
- homicide: killings, murders not tied to kidnapping or robbery
- terrorism: attacks by named extremist/insurgent groups (e.g. Boko Haram, ISWAP)
- armed_attack: gunmen/bandit/herdsmen attacks on communities where the primary crime type isn't clear from the headline alone
- other: anything crime-related that doesn't fit the above
"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}]
    )

    raw_text = response.choices[0].message.content.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)


def save_to_database(cursor, headline, source, link, data):
    from geocode import geocode_location
    coords = geocode_location(data["location"])
    lat, lng = coords if coords else (None, None)

    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f"""
        INSERT INTO headlines (title, crime_type, location, confidence, summary, date_added, source, link, verified, lat, lng)
        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
    """, (
        headline, data["crime_type"], data["location"], data["confidence"],
        data["summary"], date.today().isoformat(), source, link, "unverified", lat, lng
    ))


def run_pipeline():
    all_headlines = fetch_all_headlines()
    crime_headlines = filter_crime_related(all_headlines)

    print(f"\n[{date.today().isoformat()}] Fetched {len(all_headlines)} total, {len(crime_headlines)} crime-related.")

    connection = get_connection()
    cursor = connection.cursor()

    saved_count = 0
    skipped_count = 0
    error_count = 0

    for h in crime_headlines:
        title = h["title"]

        if similar_headline_exists(cursor, title):
            skipped_count += 1
            continue

        print(f"Classifying: {title}")
        time.sleep(13)

        try:
            result = classify_headline(title)
        except json.JSONDecodeError:
            print(f"  ! Skipped — AI returned invalid JSON for this headline")
            error_count += 1
            continue
        except Exception as e:
            print(f"  ! Skipped — API error: {e}")
            error_count += 1
            continue

        required_fields = ["crime_type", "location", "confidence", "summary"]
        if not all(field in result for field in required_fields):
            print(f"  ! Skipped — response missing required fields: {result}")
            error_count += 1
            continue

        try:
            save_to_database(cursor, title, h["source"], h["link"], result)
            connection.commit()
        except Exception as e:
            print(f"  ! Skipped — database error: {e}")
            error_count += 1
            continue

        print(f"  -> {result['crime_type']} in {result['location']}")
        saved_count += 1

    connection.close()
    print(f"Done. Saved {saved_count} new, skipped {skipped_count} duplicates, {error_count} errors.")


if __name__ == "__main__":
    run_pipeline()