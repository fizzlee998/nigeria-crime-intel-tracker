import os
import threading
import time
import schedule
import sqlite3
from flask import Flask, render_template, jsonify

from classify_and_save import run_pipeline

app = Flask(__name__)

# Approximate coordinates for Nigerian states/cities commonly seen in headlines
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


def get_coords(location):
    if not location:
        return None
    key = location.strip().lower()
    if key in LOCATION_COORDS:
        return LOCATION_COORDS[key]
    for name, coords in LOCATION_COORDS.items():
        if name in key or key in name:
            return coords
    return None


def ensure_database_exists():
    connection = sqlite3.connect("crime_intel.db")
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS headlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            crime_type TEXT,
            location TEXT,
            confidence TEXT,
            summary TEXT,
            date_added TEXT
        )
    """)
    connection.commit()
    connection.close()


def get_all_incidents():
    connection = sqlite3.connect("crime_intel.db")
    cursor = connection.cursor()
    cursor.execute("""
        SELECT id, title, crime_type, location, confidence, summary, date_added
        FROM headlines
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    connection.close()
    return rows


def get_chart_data():
    connection = sqlite3.connect("crime_intel.db")
    cursor = connection.cursor()

    cursor.execute("SELECT crime_type, COUNT(*) FROM headlines GROUP BY crime_type")
    by_type = cursor.fetchall()

    cursor.execute("SELECT location, COUNT(*) FROM headlines GROUP BY location ORDER BY COUNT(*) DESC LIMIT 8")
    by_location = cursor.fetchall()

    cursor.execute("SELECT date_added, COUNT(*) FROM headlines GROUP BY date_added ORDER BY date_added")
    by_date = cursor.fetchall()

    connection.close()

    return {
        "by_type": {"labels": [r[0] for r in by_type], "values": [r[1] for r in by_type]},
        "by_location": {"labels": [r[0] for r in by_location], "values": [r[1] for r in by_location]},
        "by_date": {"labels": [r[0] for r in by_date], "values": [r[1] for r in by_date]},
    }


@app.route("/")
def dashboard():
    incidents = get_all_incidents()
    return render_template("index.html", count=len(incidents))


@app.route("/api/chart-data")
def chart_data():
    return jsonify(get_chart_data())


@app.route("/api/incidents")
def incidents_api():
    rows = get_all_incidents()
    result = []
    for row in rows:
        coords = get_coords(row[3])
        result.append({
            "id": row[0], "title": row[1], "crime_type": row[2], "location": row[3],
            "confidence": row[4], "summary": row[5], "date_added": row[6],
            "lat": coords[0] if coords else None, "lng": coords[1] if coords else None,
        })
    return jsonify(result)


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