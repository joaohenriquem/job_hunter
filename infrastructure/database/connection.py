import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'jobs_v2.db')

def get_connection():
    return sqlite3.connect(DB_PATH)
