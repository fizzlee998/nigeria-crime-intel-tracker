import os
import sqlite3
import psycopg2
import time
from classify_and_save import classify_headline, DATABASE_URL


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect("crime_intel.db")


connection = get_connection()
cursor = connection.cursor()

cursor.execute("SELECT id, title FROM headlines WHERE crime_type = 'other'")
rows = cursor.fetchall()

print(f"Found {len(rows)} rows classified as 'other' — re-checking relevance for each.")

to_delete = []

for row_id, title in rows:
    print(f"Checking: [{row_id}] {title}")
    time.sleep(13)
    try:
        result = classify_headline(title)
    except Exception as e:
        print(f"  ! Error, leaving as-is: {e}")
        continue

    if not result.get("is_crime_incident", True):
        print(f"  -> Not a real crime incident, flagged for deletion")
        to_delete.append(row_id)
    else:
        print(f"  -> Confirmed relevant, keeping")

print(f"\n{len(to_delete)} rows flagged for deletion out of {len(rows)} checked.")

if to_delete:
    confirm = input("Type 'yes' to delete these rows: ")
    if confirm.strip().lower() == "yes":
        placeholder = "%s" if DATABASE_URL else "?"
        for row_id in to_delete:
            cursor.execute(f"DELETE FROM headlines WHERE id = {placeholder}", (row_id,))
        connection.commit()
        print("Deleted.")
    else:
        print("Cancelled — no changes made.")
else:
    print("Nothing to delete.")

connection.close()