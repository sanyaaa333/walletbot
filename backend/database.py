import sqlite3
from contextlib import contextmanager

# Для SQLite
@contextmanager
def get_db():
    conn = sqlite3.connect('walletstars.db')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Для PostgreSQL (альтернатива)
"""
import psycopg2
from psycopg2.extras import RealDictCursor

@contextmanager
def get_db():
    conn = psycopg2.connect(
        dbname="walletstars",
        user="user",
        password="password",
        host="localhost",
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()
"""