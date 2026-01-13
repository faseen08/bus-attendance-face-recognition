import sqlite3

DB_PATH = "database/bus.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with open("database/schema.sql") as f:
        conn = get_connection()
        conn.executescript(f.read())
        conn.commit()
        conn.close()

if __name__ == "__main__":
    init_db()
