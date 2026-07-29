import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

headline = "Armed robbers attack bank in Lagos, cart away millions"

prompt = f"""
You are a crime intelligence classifier for Nigerian news headlines.

Read this headline and return ONLY valid JSON, no extra text, no markdown formatting.

Headline: "{headline}"

Return JSON in exactly this format:
{{
  "crime_type": "one of: robbery, kidnapping",
  "location": "city or state mentioned, or 'unknown' if none",
  "confidence": "high, medium, or low",
  "summary": "one sentence summary of the incident"
}}
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)

raw_text = response.text.strip()

# Gemini sometimes wraps JSON in ```json blocks — strip that if present
if raw_text.startswith("```"):
    raw_text = raw_text.split("```")[1]
    if raw_text.startswith("json"):
        raw_text = raw_text[4:]
    raw_text = raw_text.strip()

data = json.loads(raw_text)

print("Parsed result:")
print(data)