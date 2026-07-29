import sqlite3

connection = sqlite3.connect("crime_intel.db")
cursor = connection.cursor()

cursor.execute("SELECT * FROM headlines")
rows = cursor.fetchall()

for row in rows:
    print(row)

connection.close()