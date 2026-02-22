import sqlite3

DB_PATH = "database/bus.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _table_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [r[1] for r in rows]

def _ensure_column(conn, table_name, column_name, column_sql, report):
    columns = _table_columns(conn, table_name)
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
        report["columns_added"].append(f"{table_name}.{column_name}")

def _ensure_index(conn, index_name, index_sql, report):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name = ?",
        (index_name,),
    ).fetchone()
    if not exists:
        conn.execute(index_sql)
        report["indexes_added"].append(index_name)

def _ensure_migrations_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

def _is_migration_applied(conn, name):
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE name = ?",
        (name,),
    ).fetchone()
    return bool(row)

def _mark_migration_applied(conn, name):
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (name) VALUES (?)",
        (name,),
    )

def init_db():
    report = {
        "migrations_applied": [],
        "columns_added": [],
        "indexes_added": [],
    }
    conn = get_connection()

    _ensure_migrations_table(conn)

    # Base schema (idempotent)
    with open('database/schema.sql', 'r') as f:
        conn.executescript(f.read())
    
    # Migration 001: students columns required by current app and driver module
    migration = "001_students_columns"
    if not _is_migration_applied(conn, migration):
        _ensure_column(conn, "students", "bus_stop", "bus_stop TEXT", report)
        _ensure_column(conn, "students", "bus_number", "bus_number TEXT", report)
        _ensure_column(conn, "students", "on_leave", "on_leave INTEGER DEFAULT 0", report)
        _mark_migration_applied(conn, migration)
        report["migrations_applied"].append(migration)

    # Migration 002: attendance direction
    migration = "002_attendance_direction"
    if not _is_migration_applied(conn, migration):
        _ensure_column(conn, "attendance", "direction", "direction TEXT DEFAULT 'IN'", report)
        _mark_migration_applied(conn, migration)
        report["migrations_applied"].append(migration)

    # Migration 003: indexes for driver + attendance flows
    migration = "003_indexes"
    if not _is_migration_applied(conn, migration):
        _ensure_index(
            conn,
            "idx_students_bus_number",
            "CREATE INDEX IF NOT EXISTS idx_students_bus_number ON students(bus_number)",
            report,
        )
        _ensure_index(
            conn,
            "idx_drivers_driver_id",
            "CREATE INDEX IF NOT EXISTS idx_drivers_driver_id ON drivers(driver_id)",
            report,
        )
        _ensure_index(
            conn,
            "idx_driver_logs_driver_time",
            "CREATE INDEX IF NOT EXISTS idx_driver_logs_driver_time ON driver_logs(driver_id, timestamp)",
            report,
        )
        _ensure_index(
            conn,
            "idx_driver_logs_student_time",
            "CREATE INDEX IF NOT EXISTS idx_driver_logs_student_time ON driver_logs(student_id, timestamp)",
            report,
        )
        _ensure_index(
            conn,
            "idx_attendance_student_date",
            "CREATE INDEX IF NOT EXISTS idx_attendance_student_date ON attendance(student_id, date)",
            report,
        )
        _mark_migration_applied(conn, migration)
        report["migrations_applied"].append(migration)

    conn.commit()
    conn.close()
    return report

if __name__ == "__main__":
    print(init_db())
