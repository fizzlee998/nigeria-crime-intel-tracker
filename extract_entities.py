import os
import json
import sqlite3
import psycopg2
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect("crime_intel.db")


def extract_entities(title, summary):
    prompt = f"""
You are extracting factual entities from a Nigerian crime news report. Do not infer or guess beyond what is stated.

Title: "{title}"
Summary: "{summary}"

Return ONLY valid JSON, no extra text:
{{
  "method": "the method/means used, in a few words (e.g. 'roadside abduction', 'armed break-in', 'IED attack'), or 'unspecified' if not stated",
  "named_group": "a specific named group/organization if explicitly mentioned (e.g. 'Boko Haram'), or 'none' if no group is named"
}}
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    raw_text = response.choices[0].message.content.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()
    return json.loads(raw_text)


def run_extraction():
    connection = get_connection()
    cursor = connection.cursor()
    placeholder = "%s" if DATABASE_URL else "?"

    cursor.execute(f"""
        SELECT id, title, summary FROM headlines
        WHERE method IS NULL OR method = {placeholder}
    """, ("",))
    rows = cursor.fetchall()

    print(f"Found {len(rows)} incidents needing entity extraction.")

    updated = 0
    errors = 0

    for row_id, title, summary in rows:
        print(f"Extracting: [{row_id}] {title}")
        time.sleep(13)

        try:
            entities = extract_entities(title, summary)
        except Exception as e:
            print(f"  ! Skipped — error: {e}")
            errors += 1
            continue

        cursor.execute(
            f"UPDATE headlines SET method = {placeholder}, named_group = {placeholder} WHERE id = {placeholder}",
            (entities.get("method", "unspecified"), entities.get("named_group", "none"), row_id)
        )
        connection.commit()
        print(f"  -> method: {entities.get('method')}, group: {entities.get('named_group')}")
        updated += 1

    connection.close()
    print(f"Done. Updated {updated}, errors {errors}.")


if __name__ == "__main__":
    run_extraction()