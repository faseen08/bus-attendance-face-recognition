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

    # Migration 004: student alert profile columns
    migration = "004_student_alert_columns"
    if not _is_migration_applied(conn, migration):
        _ensure_column(conn, "students", "parent_name", "parent_name TEXT", report)
        _ensure_column(conn, "students", "parent_phone", "parent_phone TEXT", report)
        _ensure_column(conn, "students", "alerts_enabled", "alerts_enabled INTEGER DEFAULT 1", report)
        _ensure_column(conn, "students", "bus_stop_lat", "bus_stop_lat REAL", report)
        _ensure_column(conn, "students", "bus_stop_lng", "bus_stop_lng REAL", report)
        _ensure_column(conn, "students", "bus_stop_label", "bus_stop_label TEXT", report)
        _mark_migration_applied(conn, migration)
        report["migrations_applied"].append(migration)

    # Migration 005: trips + locations + notifications tables
    migration = "005_trip_and_alert_tables"
    if not _is_migration_applied(conn, migration):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bus_trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_id TEXT NOT NULL,
                bus_number TEXT NOT NULL,
                trip_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                service_date TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bus_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                speed REAL,
                heading REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES bus_trips(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                trip_id INTEGER NOT NULL,
                trip_type TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                provider_sid TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, trip_id, event_type)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                stop_radius_meters INTEGER DEFAULT 150,
                timezone TEXT DEFAULT 'Asia/Kolkata',
                boarded_template TEXT DEFAULT 'Bus update: {student_name} boarded bus {bus_number}.',
                missed_template TEXT DEFAULT 'Alert: {student_name} has not boarded bus {bus_number} after the stop was passed.',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO notification_settings (id) VALUES (1)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trip_student_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                last_distance_m REAL,
                min_distance_m REAL,
                reached_stop INTEGER DEFAULT 0,
                passed_stop INTEGER DEFAULT 0,
                last_evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trip_id, student_id)
            )
            """
        )
        _mark_migration_applied(conn, migration)
        report["migrations_applied"].append(migration)

    # Migration 006: indexes for trip/location/notification performance
    migration = "006_trip_alert_indexes"
    if not _is_migration_applied(conn, migration):
        _ensure_index(
            conn,
            "idx_bus_trips_driver_status",
            "CREATE INDEX IF NOT EXISTS idx_bus_trips_driver_status ON bus_trips(driver_id, status)",
            report,
        )
        _ensure_index(
            conn,
            "idx_bus_trips_bus_status",
            "CREATE INDEX IF NOT EXISTS idx_bus_trips_bus_status ON bus_trips(bus_number, status)",
            report,
        )
        _ensure_index(
            conn,
            "idx_bus_locations_trip_time",
            "CREATE INDEX IF NOT EXISTS idx_bus_locations_trip_time ON bus_locations(trip_id, timestamp)",
            report,
        )
        _ensure_index(
            conn,
            "idx_notifications_student_time",
            "CREATE INDEX IF NOT EXISTS idx_notifications_student_time ON notifications(student_id, created_at)",
            report,
        )
        _ensure_index(
            conn,
            "idx_notifications_trip_type",
            "CREATE INDEX IF NOT EXISTS idx_notifications_trip_type ON notifications(trip_id, event_type)",
            report,
        )
        _mark_migration_applied(conn, migration)
        report["migrations_applied"].append(migration)

    # Migration 007: ensure bus_locations.timestamp exists (older DBs)
    migration = "007_bus_locations_timestamp"
    if not _is_migration_applied(conn, migration):
        # SQLite cannot add a column with non-constant default via ALTER TABLE.
        _ensure_column(conn, "bus_locations", "timestamp", "timestamp TEXT", report)
        _mark_migration_applied(conn, migration)
        report["migrations_applied"].append(migration)

    # Migration 008: ensure bus_locations driver metadata columns exist
    migration = "008_bus_locations_metadata"
    if not _is_migration_applied(conn, migration):
        _ensure_column(conn, "bus_locations", "driver_id", "driver_id TEXT", report)
        _ensure_column(conn, "bus_locations", "bus_number", "bus_number TEXT", report)
        _ensure_column(conn, "bus_locations", "recorded_at", "recorded_at TEXT", report)
        _mark_migration_applied(conn, migration)
        report["migrations_applied"].append(migration)

    # Migration 009: ensure notification_settings columns exist on older DBs
    migration = "009_notification_settings_columns"
    if not _is_migration_applied(conn, migration):
        _ensure_column(conn, "notification_settings", "stop_radius_meters", "stop_radius_meters INTEGER DEFAULT 150", report)
        _ensure_column(conn, "notification_settings", "timezone", "timezone TEXT DEFAULT 'Asia/Kolkata'", report)
        _ensure_column(conn, "notification_settings", "boarded_template", "boarded_template TEXT", report)
        _ensure_column(conn, "notification_settings", "missed_template", "missed_template TEXT", report)
        _ensure_column(conn, "notification_settings", "updated_at", "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP", report)
        conn.execute("INSERT OR IGNORE INTO notification_settings (id) VALUES (1)")
        _mark_migration_applied(conn, migration)
        report["migrations_applied"].append(migration)

    conn.commit()
    conn.close()
    return report

if __name__ == "__main__":
    print(init_db())
