import os
import threading
import time
import schedule
import sqlite3
import psycopg2
from flask import Flask, render_template, jsonify, send_file, request
from io import BytesIO
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import date

from classify_and_save import run_pipeline, get_connection, DATABASE_URL
from investigate_agent import run_investigation

app = Flask(__name__)

LOCATION_COORDS = {
    "lagos": (6.5244, 3.3792), "abuja": (9.0765, 7.3986), "kano": (12.0022, 8.5920),
    "kaduna": (10.5105, 7.4165), "katsina": (12.9908, 7.6018), "zamfara": (12.1704, 6.2649),
    "borno": (11.8333, 13.1500), "adamawa": (9.3265, 12.3984), "benue": (7.3369, 8.7404),
    "ogun": (7.1608, 3.3480), "oyo": (8.1574, 3.6147), "rivers": (4.8156, 6.9778),
    "delta": (5.5320, 5.8987), "edo": (6.6342, 5.9304), "enugu": (6.4413, 7.4990),
    "anambra": (6.2209, 6.9370), "imo": (5.4836, 7.0333), "abia": (5.4527, 7.5248),
    "ebonyi": (6.2649, 8.0137), "cross river": (5.9631, 8.3251), "akwa ibom": (5.0077, 7.8536),
    "bayelsa": (4.7719, 6.0699), "sokoto": (13.0059, 5.2476), "kebbi": (12.4539, 4.1975),
    "niger": (9.9309, 5.5983), "kwara": (8.5000, 4.5500), "kogi": (7.7337, 6.6906),
    "nasarawa": (8.4933, 8.5210), "plateau": (9.2182, 9.5179), "taraba": (7.9994, 10.7740),
    "gombe": (10.2897, 11.1673), "bauchi": (10.3158, 9.8442), "yobe": (12.2939, 11.4390),
    "jigawa": (12.2280, 9.5616), "ekiti": (7.7190, 5.3110), "ondo": (7.2500, 5.2000),
    "osun": (7.5629, 4.5200), "south-east": (5.9631, 7.4990), "south east": (5.9631, 7.4990),
    "abuja fct": (9.0765, 7.3986), "fct": (9.0765, 7.3986), "lafia": (8.4939, 8.5170),
}


def ensure_database_exists():
    connection = get_connection()
    cursor = connection.cursor()
    if DATABASE_URL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS headlines (
                id SERIAL PRIMARY KEY,
                title TEXT,
                crime_type TEXT,
                location TEXT,
                confidence TEXT,
                summary TEXT,
                date_added TEXT,
                source TEXT,
                link TEXT,
                verified TEXT DEFAULT 'unverified',
                lat REAL,
                lng REAL,
                method TEXT,
                named_group TEXT
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS headlines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                crime_type TEXT,
                location TEXT,
                confidence TEXT,
                summary TEXT,
                date_added TEXT,
                source TEXT,
                link TEXT,
                verified TEXT DEFAULT 'unverified',
                lat REAL,
                lng REAL,
                method TEXT,
                named_group TEXT
            )
        """)
    connection.commit()
    connection.close()


def get_all_incidents():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT id, title, crime_type, location, confidence, summary, date_added, source, link, verified, lat, lng
        FROM headlines
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    connection.close()
    return rows


@app.route("/")
def dashboard():
    incidents = get_all_incidents()
    return render_template("index.html", count=len(incidents))


@app.route("/api/chart-data")
def chart_data():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT crime_type, COUNT(*) FROM headlines GROUP BY crime_type")
    by_type = cursor.fetchall()

    cursor.execute("SELECT location, COUNT(*) FROM headlines GROUP BY location ORDER BY COUNT(*) DESC LIMIT 8")
    by_location = cursor.fetchall()

    cursor.execute("SELECT date_added, COUNT(*) FROM headlines GROUP BY date_added ORDER BY date_added")
    by_date = cursor.fetchall()

    connection.close()

    return jsonify({
        "by_type": {"labels": [r[0] for r in by_type], "values": [r[1] for r in by_type]},
        "by_location": {"labels": [r[0] for r in by_location], "values": [r[1] for r in by_location]},
        "by_date": {"labels": [r[0] for r in by_date], "values": [r[1] for r in by_date]},
    })


@app.route("/api/incidents")
def incidents_api():
    rows = get_all_incidents()
    result = []
    for row in rows:
        result.append({
            "id": row[0], "title": row[1], "crime_type": row[2], "location": row[3],
            "confidence": row[4], "summary": row[5], "date_added": row[6],
            "source": row[7], "link": row[8],
            "lat": row[10], "lng": row[11],
        })
    return jsonify(result)


@app.route("/api/insights")
def insights():
    connection = get_connection()
    cursor = connection.cursor()
    placeholder = "%s" if DATABASE_URL else "?"

    cursor.execute(f"""
        SELECT location, COUNT(*) as cnt FROM headlines
        WHERE location != {placeholder}
        GROUP BY location ORDER BY cnt DESC LIMIT 5
    """, ("unknown",))
    hotspots = cursor.fetchall()

    cursor.execute("SELECT crime_type, COUNT(*) as cnt FROM headlines GROUP BY crime_type ORDER BY cnt DESC LIMIT 1")
    top_crime = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM headlines")
    total = cursor.fetchone()[0]

    connection.close()

    return jsonify({
        "hotspots": [{"location": h[0], "count": h[1]} for h in hotspots],
        "top_crime_type": {"type": top_crime[0], "count": top_crime[1]} if top_crime else None,
        "total_incidents": total,
    })


@app.route("/api/correlations")
def correlations():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, title, crime_type, location, method, named_group, date_added
        FROM headlines
        WHERE location != 'unknown'
    """)
    rows = cursor.fetchall()
    connection.close()

    groups = {}
    for row in rows:
        row_id, title, crime_type, location, method, named_group, date_added = row

        key = (location, crime_type)
        groups.setdefault(key, []).append({
            "id": row_id, "title": title, "method": method, "date_added": date_added
        })

        if named_group and named_group.lower() != "none":
            gkey = ("named_group", named_group)
            groups.setdefault(gkey, []).append({
                "id": row_id, "title": title, "method": method, "date_added": date_added
            })

    correlations_found = []
    for key, incidents in groups.items():
        if len(incidents) < 2:
            continue

        if key[0] == "named_group":
            label = f"Multiple reports name '{key[1]}'"
            confidence = "moderate"
        else:
            location, crime_type = key
            methods = set(i["method"] for i in incidents if i["method"] and i["method"] != "unspecified")
            shared_method = len(methods) == 1
            label = f"{len(incidents)} {crime_type} reports in {location}"
            confidence = "moderate" if shared_method else "low"

        correlations_found.append({
            "label": label,
            "confidence": confidence,
            "count": len(incidents),
            "incidents": incidents,
        })

    correlations_found.sort(key=lambda c: c["count"], reverse=True)

    return jsonify(correlations_found)


@app.route("/api/investigate", methods=["POST"])
def investigate():
    data = request.get_json()
    question = (data or {}).get("question", "").strip()

    if not question:
        return jsonify({"error": "No question provided"}), 400

    try:
        result = run_investigation(question)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/export/excel")
def export_excel():
    incidents = get_all_incidents()

    wb = Workbook()
    ws = wb.active
    ws.title = "Crime Incidents"

    headers = ["ID", "Title", "Crime Type", "Location", "Confidence", "Summary", "Date Added", "Source", "Link"]
    ws.append(headers)

    for row in incidents:
        ws.append(list(row)[:9])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"crime_incidents_{date.today().isoformat()}.xlsx"
    return send_file(buffer, as_attachment=True, download_name=filename,
                      mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/export/pdf")
def export_pdf():
    incidents = get_all_incidents()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()

    link_style = ParagraphStyle(
        "LinkCell", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#1a4fb3")
    )
    plain_cell_style = ParagraphStyle("PlainCell", parent=styles["Normal"], fontSize=8)

    elements = []

    elements.append(Paragraph("Nigeria Crime Intelligence Report", styles["Title"]))
    elements.append(Paragraph(f"Generated: {date.today().isoformat()} — {len(incidents)} incidents", styles["Normal"]))
    elements.append(Spacer(1, 12))

    table_data = [["ID", "Title", "Crime Type", "Location", "Confidence", "Date", "Source"]]
    for row in incidents:
        source_name = row[7] if row[7] else "—"
        link_url = row[8]

        if link_url:
            source_cell = Paragraph(f'<link href="{link_url}"><u>{source_name}</u></link>', link_style)
        else:
            source_cell = Paragraph(source_name, plain_cell_style)

        title_text = row[1][:55] + ("..." if len(row[1]) > 55 else "")

        table_data.append([
            str(row[0]),
            Paragraph(title_text, plain_cell_style),
            row[2], row[3], row[4], row[6], source_cell
        ])

    table = Table(table_data, repeatRows=1, colWidths=[25, 220, 70, 60, 60, 60, 60])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    filename = f"crime_report_{date.today().isoformat()}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


def run_scheduler():
    schedule.every(1).hours.do(run_pipeline)
    run_pipeline()

    while True:
        schedule.run_pending()
        time.sleep(60)


ensure_database_exists()

scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)