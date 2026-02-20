-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student',  -- 'admin', 'student', 'driver'
    student_id TEXT,  -- Links to students table if user is a student
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Updated students table
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE,
    name TEXT,
    bus_stop TEXT,      -- Added for Module 1
    photo_path TEXT,
    on_leave INTEGER DEFAULT 0  -- Added for Module 4 (0=Present, 1=On Leave)
);

-- Updated attendance table
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    date TEXT,
    time TEXT,
    direction TEXT DEFAULT 'IN' -- Added for Module 3 (IN/OUT)
);

CREATE INDEX IF NOT EXISTS idx_attendance_student_date ON attendance(student_id, date);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
