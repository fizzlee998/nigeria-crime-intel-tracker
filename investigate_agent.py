import os
import json
import sqlite3
import psycopg2
from dotenv import load_dotenv
from groq import Groq, BadRequestError
from geocode import geocode_location

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MAX_ITERATIONS = 8

SYSTEM_PROMPT = """You are a criminal intelligence analysis agent investigating patterns in
Nigerian crime incident data. You have tools to query a database of
verified incidents, search headlines by keyword, geocode locations, and
retrieve full incident details.

Your job is to investigate a specific question by gathering evidence
step by step — not to answer from assumption or general knowledge of
Nigerian crime patterns. Every claim you make must be traceable to a
specific incident_id you retrieved through your tools.

The database uses specific crime_type values (robbery, kidnapping, homicide,
terrorism, armed_attack, other) and location names as they appear in news
text (often a state name, sometimes a city). If a user's question uses a
different word (e.g. "abduction" instead of "kidnapping", or a city instead
of a state), try the closest matching value first, and if that returns
nothing, use search_headlines_by_keyword with the user's own wording before
concluding there's no data.

Rules you must follow:
1. Never claim a pattern exists based on a single incident. You need at
   least 2-3 independent incidents (different sources, not the same
   story republished) before proposing a pattern.
2. Never use confirmatory language ("confirmed", "proven", "established").
   Use only "low confidence" or "moderate confidence — recommend review."
   This is analytical support, not a verdict.
3. If evidence is thin or contradictory, say so explicitly rather than
   forcing a conclusion. An honest "insufficient evidence" is a valid
   and useful outcome.
4. If two incidents share a named actor/group, check whether it's
   plausibly the same entity (matching location, timeframe, method)
   before treating them as connected — names can coincidentally match.
5. Before calling finish_investigation, review your own gathered
   evidence and ask: would an analyst reviewing this brief be able to
   verify each claim by checking the cited incident_ids? If not,
   gather more evidence or lower your confidence rating.

You have up to {max_iterations} tool calls. Use them deliberately —
plan what you need to know before you search, rather than searching
broadly and hoping something turns up. Do not repeat a search you've
already effectively run with slightly different wording. Once you
have gathered evidence sufficient to answer the question — even if
that answer is "insufficient evidence" — call finish_investigation
promptly rather than continuing to search for more. Also watch for
near-duplicate headlines describing the same real-world event
reported by different outlets — treat these as ONE corroborating
data point, not several independent ones, when assessing confidence.""".format(max_iterations=MAX_ITERATIONS)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_incidents",
            "description": "Search the incident database with optional filters. Leave a field null/omitted to not filter on it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "crime_type": {"type": "string", "description": "e.g. robbery, kidnapping, homicide, terrorism, armed_attack, other"},
                    "location": {"type": "string", "description": "State or city name"},
                    "method": {"type": "string", "description": "Partial match on method text, e.g. 'roadside'"},
                    "named_group": {"type": "string", "description": "Named group/organization, e.g. 'Boko Haram'"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_incident_detail",
            "description": "Get full details for one incident by its ID.",
            "parameters": {
                "type": "object",
                "properties": {"incident_id": {"type": "integer"}},
                "required": ["incident_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_headlines_by_keyword",
            "description": "Search incident titles and summaries for a keyword not covered by structured filters.",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string"}},
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "geocode_location",
            "description": "Get approximate latitude/longitude for a place name in Nigeria.",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_investigation",
            "description": "Call this when you have gathered enough evidence to conclude the investigation, or determined there is insufficient evidence for a pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern_found": {"type": "boolean", "description": "Whether a credible pattern was identified"},
                    "confidence": {"type": "string", "enum": ["insufficient_evidence", "low", "moderate"], "description": "moderate requires 3+ independent corroborating incidents"},
                    "pattern_summary": {"type": "string", "description": "1-2 sentence plain-language description of the pattern, if any"},
                    "supporting_incident_ids": {"type": "array", "items": {"type": "integer"}, "description": "Every incident_id cited as evidence"},
                    "reasoning": {"type": "string", "description": "Step-by-step explanation referencing specific incident_ids"},
                    "contradicting_or_weak_points": {"type": "string", "description": "Anything that complicates or weakens the pattern"},
                    "recommended_next_steps": {"type": "string", "description": "What a human analyst should check next"},
                },
                "required": ["pattern_found", "confidence", "supporting_incident_ids", "reasoning", "contradicting_or_weak_points", "recommended_next_steps"],
            },
        },
    },
]


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect("crime_intel.db")


def _row_to_dict(row, columns):
    return dict(zip(columns, row))


def tool_query_incidents(crime_type=None, location=None, method=None, named_group=None):
    connection = get_connection()
    cursor = connection.cursor()
    placeholder = "%s" if DATABASE_URL else "?"

    conditions = []
    params = []
    like_op = "ILIKE" if DATABASE_URL else "LIKE"
    if crime_type:
        conditions.append(f"crime_type {like_op} {placeholder}")
        params.append(f"%{crime_type}%")
    if location:
        conditions.append(f"location {like_op} {placeholder}")
        params.append(f"%{location}%")
    if method:
        conditions.append(f"method {like_op} {placeholder}")
        params.append(f"%{method}%")
    if named_group:
        conditions.append(f"named_group {like_op} {placeholder}")
        params.append(f"%{named_group}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cursor.execute(f"""
        SELECT id, title, crime_type, location, source, date_added, method, named_group
        FROM headlines {where_clause} LIMIT 20
    """, params)
    rows = cursor.fetchall()
    connection.close()

    columns = ["id", "title", "crime_type", "location", "source", "date_added", "method", "named_group"]
    return [_row_to_dict(r, columns) for r in rows]


def tool_get_incident_detail(incident_id):
    connection = get_connection()
    cursor = connection.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f"""
        SELECT id, title, crime_type, location, confidence, summary, date_added, source, link, method, named_group
        FROM headlines WHERE id = {placeholder}
    """, (incident_id,))
    row = cursor.fetchone()
    connection.close()

    if not row:
        return {"error": f"No incident with id {incident_id}"}

    columns = ["id", "title", "crime_type", "location", "confidence", "summary", "date_added", "source", "link", "method", "named_group"]
    return _row_to_dict(row, columns)


def tool_search_headlines_by_keyword(keyword):
    connection = get_connection()
    cursor = connection.cursor()
    like_op = "ILIKE" if DATABASE_URL else "LIKE"
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f"""
        SELECT id, title, crime_type, location, source, date_added
        FROM headlines
        WHERE title {like_op} {placeholder} OR summary {like_op} {placeholder}
        LIMIT 20
    """, (f"%{keyword}%", f"%{keyword}%"))
    rows = cursor.fetchall()
    connection.close()

    columns = ["id", "title", "crime_type", "location", "source", "date_added"]
    return [_row_to_dict(r, columns) for r in rows]


def tool_geocode_location(location):
    coords = geocode_location(location)
    if coords:
        return {"lat": coords[0], "lng": coords[1]}
    return {"error": "Could not geocode this location"}


TOOL_FUNCTIONS = {
    "query_incidents": tool_query_incidents,
    "get_incident_detail": tool_get_incident_detail,
    "search_headlines_by_keyword": tool_search_headlines_by_keyword,
    "geocode_location": tool_geocode_location,
}


def run_investigation(question):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for iteration in range(MAX_ITERATIONS):
        is_last_iteration = (iteration == MAX_ITERATIONS - 1)

        kwargs = {
            "model": "openai/gpt-oss-120b",
            "messages": messages,
            "tools": TOOLS,
        }

        if is_last_iteration:
            kwargs["tool_choice"] = {"type": "function", "function": {"name": "finish_investigation"}}
        else:
            kwargs["tool_choice"] = "auto"

        try:
            response = client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            print(f"  [forced tool_choice failed: {e}] Falling back to plain-text conclusion.")
            return _force_plain_text_conclusion(messages)

        message = response.choices[0].message
        messages.append(message)

        if not message.tool_calls:
            return {
                "pattern_found": False,
                "confidence": "insufficient_evidence",
                "pattern_summary": "",
                "supporting_incident_ids": [],
                "reasoning": "Agent did not call finish_investigation and stopped early.",
                "contradicting_or_weak_points": message.content or "",
                "recommended_next_steps": "Try rephrasing the question.",
            }

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            print(f"  [tool call] {fn_name}({fn_args})")

            if fn_name == "finish_investigation":
                return fn_args

            fn = TOOL_FUNCTIONS.get(fn_name)
            if fn:
                try:
                    result = fn(**fn_args)
                except Exception as e:
                    result = {"error": str(e)}
            else:
                result = {"error": f"Unknown tool: {fn_name}"}

            print(f"    -> {result}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    return _force_plain_text_conclusion(messages)


def _force_plain_text_conclusion(messages):
    schema_hint = """Based on everything you've gathered so far in this conversation, respond
with ONLY a JSON object (no other text, no markdown code fences) matching this exact schema:

{
  "pattern_found": true or false,
  "confidence": "insufficient_evidence" or "low" or "moderate",
  "pattern_summary": "1-2 sentence plain-language description, or empty string",
  "supporting_incident_ids": [list of integer incident_ids actually retrieved above],
  "reasoning": "step-by-step explanation referencing specific incident_ids",
  "contradicting_or_weak_points": "anything that weakens the pattern, required even if none",
  "recommended_next_steps": "what a human analyst should check next"
}"""

    fallback_messages = messages + [{"role": "user", "content": schema_hint}]

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=fallback_messages,
        )
        raw_text = response.choices[0].message.content.strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        return json.loads(raw_text)
    except Exception as e:
        return {
            "pattern_found": False,
            "confidence": "insufficient_evidence",
            "pattern_summary": "",
            "supporting_incident_ids": [],
            "reasoning": f"Reached the tool-call limit and the fallback conclusion also failed: {e}",
            "contradicting_or_weak_points": "Investigation could not be cleanly concluded.",
            "recommended_next_steps": "Try a narrower or more specific question.",
        }