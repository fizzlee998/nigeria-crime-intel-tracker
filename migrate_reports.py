import os
import sqlite3
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect("crime_intel.db")


connection = get_connection()
cursor = connection.cursor()

if DATABASE_URL:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            generated_at TEXT,
            period_start TEXT,
            period_end TEXT,
            incident_count INTEGER,
            content TEXT
        )
    """)
else:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at TEXT,
            period_start TEXT,
            period_end TEXT,
            incident_count INTEGER,
            content TEXT
        )
    """)

connection.commit()
connection.close()
print("Reports table ready.")