import os
import sqlite3
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect("crime_intel.db")


def column_exists(cursor, column_name):
    if DATABASE_URL:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'headlines' AND column_name = %s
        """, (column_name,))
    else:
        cursor.execute("PRAGMA table_info(headlines)")
        columns = [row[1] for row in cursor.fetchall()]
        return column_name in columns
    return cursor.fetchone() is not None


connection = get_connection()
cursor = connection.cursor()

new_columns = {
    "source": "TEXT",
    "link": "TEXT",
    "verified": "TEXT DEFAULT 'unverified'"
}

for col_name, col_type in new_columns.items():
    if not column_exists(cursor, col_name):
        print(f"Adding column: {col_name}")
        cursor.execute(f"ALTER TABLE headlines ADD COLUMN {col_name} {col_type}")
    else:
        print(f"Column already exists, skipping: {col_name}")

connection.commit()
connection.close()
print("Migration complete.")