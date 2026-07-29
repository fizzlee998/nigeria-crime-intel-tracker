import threading
import time
import schedule
from flask import Flask, render_template
import sqlite3

from classify_and_save import run_pipeline

app = Flask(__name__)


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


@app.route("/")
def dashboard():
    incidents = get_all_incidents()
    return render_template("index.html", incidents=incidents, count=len(incidents))


def run_scheduler():
    schedule.every(1).hours.do(run_pipeline)
    run_pipeline()  # run once immediately on startup

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)