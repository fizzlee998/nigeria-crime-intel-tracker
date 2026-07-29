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

cursor.execute("SELECT id, title FROM headlines ORDER BY id DESC LIMIT 2")
rows_to_delete = cursor.fetchall()

for row_id, title in rows_to_delete:
    print(f"Deleting: [{row_id}] {title}")
    cursor.execute("DELETE FROM headlines WHERE id = %s" if DATABASE_URL else "DELETE FROM headlines WHERE id = ?", (row_id,))

connection.commit()
connection.close()
print("Done.")