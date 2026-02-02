import sqlite3

DB_PATH = "database/bus.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    # Read the schema.sql file
    with open('database/schema.sql', 'r') as f:
        conn.executescript(f.read())
    
    # Check if we need to add columns to an existing database
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(students)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'bus_stop' not in columns:
        conn.execute("ALTER TABLE students ADD COLUMN bus_stop TEXT")
    if 'on_leave' not in columns:
        conn.execute("ALTER TABLE students ADD COLUMN on_leave INTEGER DEFAULT 0")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
