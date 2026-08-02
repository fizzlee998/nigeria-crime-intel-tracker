import os
import re
import sqlite3
import psycopg2
from difflib import SequenceMatcher

DATABASE_URL = os.environ.get("DATABASE_URL")
THRESHOLD = 0.80

STOPWORDS = {"a", "an", "the", "in", "on", "at", "to", "of", "for", "and",
             "or", "as", "by", "with", "after", "over", "amid", "amidst"}


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect("crime_intel.db")


def normalize_title(title):
    words = re.findall(r"[a-z0-9]+", title.lower())
    words = [w for w in words if w not in STOPWORDS]
    return " ".join(sorted(words))


connection = get_connection()
cursor = connection.cursor()
cursor.execute("SELECT id, title FROM headlines ORDER BY id ASC")
rows = cursor.fetchall()

kept = []
to_delete = []

for row_id, title in rows:
    norm = normalize_title(title)
    is_dup = False
    for kept_id, kept_norm in kept:
        ratio = SequenceMatcher(None, norm, kept_norm).ratio()
        if ratio >= THRESHOLD:
            is_dup = True
            print(f"Duplicate: [{row_id}] {title}\n   ~= kept [{kept_id}]")
            break
    if is_dup:
        to_delete.append(row_id)
    else:
        kept.append((row_id, norm))

print(f"\nFound {len(to_delete)} near-duplicate rows to remove out of {len(rows)} total.")

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
    print("No duplicates found.")

connection.close()