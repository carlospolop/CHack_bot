import sqlite3
import json
from datetime import datetime

DATABASE = 'authorized_users.db'

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS authorized_users (user_id INTEGER PRIMARY KEY)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_runs (
                user_id INTEGER,
                run_id TEXT,
                name TEXT,
                date TEXT,
                status TEXT,
                parameters TEXT,
                PRIMARY KEY (user_id, run_id)
            )
        """)
        conn.commit()

def authorize_user(user_id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO authorized_users (user_id) VALUES (?)", (user_id,))
        conn.commit()

def is_authorized(user_id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM authorized_users WHERE user_id=?", (user_id,))
        return cursor.fetchone() is not None

def store_run_id(user_id, run_id, analysis_name, analysis_time, parameters):
    formatted_date = datetime.strptime(analysis_time, "%Y-%m-%dT%H:%M:%S.%f").strftime("%d/%m/%y")
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO user_runs (user_id, run_id, name, date, status, parameters) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, run_id, analysis_name, formatted_date, 'Pending', parameters))
        conn.commit()

def get_last_run_id(user_id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT run_id FROM user_runs WHERE user_id=? ORDER BY date DESC LIMIT 1", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None

def get_user_runs(user_id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT run_id, status, name, date, parameters FROM user_runs WHERE user_id=?", (user_id,))
        return cursor.fetchall()
