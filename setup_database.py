import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")

connection = psycopg2.connect(DATABASE_URL)
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS headlines (
    id SERIAL PRIMARY KEY,
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