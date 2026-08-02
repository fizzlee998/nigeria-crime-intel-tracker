import os
import json
from datetime import date, timedelta
from dotenv import load_dotenv
from groq import Groq

from classify_and_save import get_connection, DATABASE_URL

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

REPORT_SYSTEM_PROMPT = """You are writing a periodic situation report for a Nigerian crime
intelligence dashboard, based on incidents drawn from public news reporting.

Rules:
1. Only state facts and counts explicitly given to you in the data below —
   never invent details or reference incidents not listed.
2. Never use confirmatory language ("confirmed", "proven"). Use hedged
   phrasing: "reported", "appears to", "may indicate", "worth monitoring".
3. Always mention that this reflects media-reported incidents only, not
   verified case records, and that duplicate/related coverage of the same
   event may inflate raw counts even after automated deduplication.
4. If the data is thin (e.g. very few incidents), say so plainly rather
   than padding the report with speculation.
5. Keep it concise: 150-250 words, written for a human analyst skimming it
   quickly, not a formal legal document.
"""


def _get_period_stats(period_start, period_end):
    connection = get_connection()
    cursor = connection.cursor()
    placeholder = "%s" if DATABASE_URL else "?"

    cursor.execute(f"""
        SELECT crime_type, location, date_added FROM headlines
        WHERE date_added >= {placeholder} AND date_added <= {placeholder}
    """, (period_start, period_end))
    rows = cursor.fetchall()
    connection.close()

    by_type = {}
    by_location = {}
    for crime_type, location, _ in rows:
        by_type[crime_type] = by_type.get(crime_type, 0) + 1
        if location and location.lower() != "unknown":
            by_location[location] = by_location.get(location, 0) + 1

    top_locations = sorted(by_location.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_incidents": len(rows),
        "by_crime_type": by_type,
        "top_locations": top_locations,
    }


def generate_situation_report(days=7):
    period_end = date.today()
    period_start = period_end - timedelta(days=days)

    stats = _get_period_stats(period_start.isoformat(), period_end.isoformat())

    data_summary = f"""
Period: {period_start.isoformat()} to {period_end.isoformat()}
Total incidents recorded: {stats['total_incidents']}
Breakdown by crime type: {json.dumps(stats['by_crime_type'])}
Top reported locations: {json.dumps(stats['top_locations'])}
"""

    if stats["total_incidents"] == 0:
        content = (
            f"No incidents were recorded between {period_start.isoformat()} and "
            f"{period_end.isoformat()}. This may reflect genuinely low reporting "
            f"activity, a gap in source coverage, or a technical issue with data "
            f"collection — worth checking the pipeline if this persists."
        )
    else:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Write the situation report based on this data:\n{data_summary}"},
            ],
        )
        content = response.choices[0].message.content.strip()

    connection = get_connection()
    cursor = connection.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f"""
        INSERT INTO reports (generated_at, period_start, period_end, incident_count, content)
        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
    """, (
        date.today().isoformat(), period_start.isoformat(), period_end.isoformat(),
        stats["total_incidents"], content
    ))
    connection.commit()
    connection.close()

    return content


if __name__ == "__main__":
    print(generate_situation_report())