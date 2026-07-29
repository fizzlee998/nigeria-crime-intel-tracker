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
        CREATE TABLE IF NOT EXISTS geocode_cache (
            location TEXT PRIMARY KEY,
            lat REAL,
            lng REAL
        )
    """)
else:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS geocode_cache (
            location TEXT PRIMARY KEY,
            lat REAL,
            lng REAL
        )
    """)

connection.commit()
connection.close()
print("Geocode cache table ready.")