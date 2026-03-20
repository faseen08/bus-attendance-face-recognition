-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student',  -- 'admin', 'student', 'driver'
    student_id TEXT,  -- Links to students table if user is a student
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Students table
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE,
    name TEXT,
    bus_stop TEXT,
    bus_number TEXT,
    parent_name TEXT,
    parent_phone TEXT,
    alerts_enabled INTEGER DEFAULT 1,
    education_type TEXT, -- college | school
    college_type TEXT, -- engineering | architecture | arts_science
    college_year TEXT,
    college_department TEXT,
    school_class TEXT,
    school_division TEXT,
    bus_stop_lat REAL,
    bus_stop_lng REAL,
    bus_stop_label TEXT,
    photo_path TEXT,
    on_leave INTEGER DEFAULT 0
);

-- Attendance table
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    date TEXT,
    time TEXT,
    direction TEXT DEFAULT 'IN'
);

-- Drivers table
CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    bus_number TEXT NOT NULL,
    phone TEXT,
    license_number TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Driver logs table (boarding/alighting events)
CREATE TABLE IF NOT EXISTS driver_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL DEFAULT 'IN',
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_attendance_student_date ON attendance(student_id, date);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_students_bus_number ON students(bus_number);
CREATE INDEX IF NOT EXISTS idx_drivers_driver_id ON drivers(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_logs_driver_time ON driver_logs(driver_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_driver_logs_student_time ON driver_logs(student_id, timestamp);

-- Driver-managed trip lifecycle
CREATE TABLE IF NOT EXISTS bus_trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_id TEXT NOT NULL,
    bus_number TEXT NOT NULL,
    trip_type TEXT NOT NULL, -- TO_SCHOOL | TO_HOME
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE | COMPLETED
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    service_date TEXT NOT NULL
);

-- Live bus positions
CREATE TABLE IF NOT EXISTS bus_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    driver_id TEXT,
    bus_number TEXT,
    source TEXT NOT NULL, -- DRIVER_PHONE | GPS_DEVICE
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    speed REAL,
    heading REAL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timestamp TEXT,
    FOREIGN KEY (trip_id) REFERENCES bus_trips(id)
);

-- Alert and delivery audit log
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    trip_id INTEGER NOT NULL,
    trip_type TEXT NOT NULL,
    event_type TEXT NOT NULL, -- BOARDED | NOT_BOARDED
    status TEXT NOT NULL, -- SENT | FAILED | SKIPPED
    provider_sid TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, trip_id, event_type)
);

-- Settings (single-row)
CREATE TABLE IF NOT EXISTS notification_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    stop_radius_meters INTEGER DEFAULT 150,
    timezone TEXT DEFAULT 'Asia/Kolkata',
    boarded_template TEXT DEFAULT 'Bus update: {student_name} boarded bus {bus_number}.',
    missed_template TEXT DEFAULT 'Alert: {student_name} has not boarded bus {bus_number} after the stop was passed.',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-trip progress state for stop-pass detection
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
);

-- Admin request queue (student/driver add requests, leave requests)
CREATE TABLE IF NOT EXISTS admin_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_type TEXT NOT NULL, -- STUDENT_ADD | DRIVER_ADD | LEAVE
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING | APPROVED | REJECTED
    requester_role TEXT,
    requester_id TEXT,
    payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    reviewed_by TEXT,
    reviewed_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_bus_trips_driver_status ON bus_trips(driver_id, status);
CREATE INDEX IF NOT EXISTS idx_bus_trips_bus_status ON bus_trips(bus_number, status);
CREATE INDEX IF NOT EXISTS idx_bus_locations_trip_time ON bus_locations(trip_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_notifications_student_time ON notifications(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_trip_type ON notifications(trip_id, event_type);
