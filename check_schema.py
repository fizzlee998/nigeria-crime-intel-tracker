import sqlite3

connection = sqlite3.connect("crime_intel.db")
cursor = connection.cursor()

cursor.execute("PRAGMA table_info(headlines)")
columns = cursor.fetchall()

print("Columns in 'headlines' table:")
for col in columns:
    print(f" - {col[1]} ({col[2]})")

connection.close()