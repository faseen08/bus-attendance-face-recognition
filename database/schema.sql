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
