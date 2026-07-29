import os
import json
import sqlite3
from datetime import date
from dotenv import load_dotenv
from google import genai

from fetch_headlines import fetch_all_headlines, filter_crime_related

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


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
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    raw_text = response.text.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)


def already_saved(cursor, title):
    cursor.execute("SELECT id FROM headlines WHERE title = ?", (title,))
    return cursor.fetchone() is not None


def save_to_database(cursor, headline, data):
    cursor.execute("""
        INSERT INTO headlines (title, crime_type, location, confidence, summary, date_added)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        headline,
        data["crime_type"],
        data["location"],
        data["confidence"],
        data["summary"],
        date.today().isoformat()
    ))


def run_pipeline():
    all_headlines = fetch_all_headlines()
    crime_headlines = filter_crime_related(all_headlines)

    print(f"\n[{date.today().isoformat()}] Fetched {len(all_headlines)} total, {len(crime_headlines)} crime-related.")

    connection = sqlite3.connect("crime_intel.db")
    cursor = connection.cursor()

    saved_count = 0
    skipped_count = 0
    error_count = 0

    for h in crime_headlines:
        title = h["title"]

        if already_saved(cursor, title):
            skipped_count += 1
            continue

        print(f"Classifying: {title}")

        try:
            result = classify_headline(title)
        except json.JSONDecodeError:
            print(f"  ! Skipped — Gemini returned invalid JSON for this headline")
            error_count += 1
            continue
        except Exception as e:
            print(f"  ! Skipped — API error: {e}")
            error_count += 1
            continue

        # Even if JSON parsed, make sure the fields we need actually exist
        required_fields = ["crime_type", "location", "confidence", "summary"]
        if not all(field in result for field in required_fields):
            print(f"  ! Skipped — response missing required fields: {result}")
            error_count += 1
            continue

        try:
            save_to_database(cursor, title, result)
            connection.commit()
        except sqlite3.Error as e:
            print(f"  ! Skipped — database error: {e}")
            error_count += 1
            continue

        print(f"  -> {result['crime_type']} in {result['location']}")
        saved_count += 1

    connection.close()
    print(f"Done. Saved {saved_count} new, skipped {skipped_count} duplicates, {error_count} errors.")


if __name__ == "__main__":
    run_pipeline()