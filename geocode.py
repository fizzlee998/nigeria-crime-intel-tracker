import os
import sqlite3
import psycopg2
import time
from geopy.geocoders import Nominatim

DATABASE_URL = os.environ.get("DATABASE_URL")

geolocator = Nominatim(user_agent="nigeria-crime-intel-tracker (fizzlee998)")


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect("crime_intel.db")


def get_cached_coords(location):
    connection = get_connection()
    cursor = connection.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f"SELECT lat, lng FROM geocode_cache WHERE location = {placeholder}", (location,))
    row = cursor.fetchone()
    connection.close()
    return (row[0], row[1]) if row else None


def cache_coords(location, lat, lng):
    connection = get_connection()
    cursor = connection.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    if DATABASE_URL:
        cursor.execute(f"""
            INSERT INTO geocode_cache (location, lat, lng) VALUES ({placeholder}, {placeholder}, {placeholder})
            ON CONFLICT (location) DO NOTHING
        """, (location, lat, lng))
    else:
        cursor.execute(f"""
            INSERT OR IGNORE INTO geocode_cache (location, lat, lng) VALUES ({placeholder}, {placeholder}, {placeholder})
        """, (location, lat, lng))
    connection.commit()
    connection.close()


def geocode_location(location):
    if not location or location.strip().lower() == "unknown":
        return None

    cached = get_cached_coords(location)
    if cached:
        return cached

    try:
        result = geolocator.geocode(f"{location}, Nigeria", timeout=5)
        time.sleep(1)  # respect Nominatim's 1 request/second limit

        if result:
            cache_coords(location, result.latitude, result.longitude)
            return (result.latitude, result.longitude)
    except Exception as e:
        print(f"  ! Geocoding failed for '{location}': {e}")

    return None