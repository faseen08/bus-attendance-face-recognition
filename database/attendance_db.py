from database.db import get_connection
from datetime import datetime

def mark_attendance_db(student_id):
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M:%S")

    conn = get_connection()

    # prevent duplicate attendance for same day
    existing = conn.execute(
        "SELECT * FROM attendance WHERE student_id=? AND date=?",
        (student_id, today)
    ).fetchone()

    if existing:
        conn.close()
        return False  # already marked

    conn.execute(
        "INSERT INTO attendance (student_id, date, time) VALUES (?, ?, ?)",
        (student_id, today, now)
    )
    conn.commit()
    conn.close()
    return True
