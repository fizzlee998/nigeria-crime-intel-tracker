import sqlite3

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

print("Database is ready!")