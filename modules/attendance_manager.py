import csv
import os
from datetime import datetime

ATTENDANCE_FILE = "data/attendance/attendance.csv"

def mark_attendance(student_id):
    os.makedirs(os.path.dirname(ATTENDANCE_FILE), exist_ok=True)

    # Prevent duplicate entry for same student on same date
    today = datetime.now().date()
    entries = []
    if os.path.exists(ATTENDANCE_FILE):
        with open(ATTENDANCE_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append(row)

    for row in entries:
        if row["student_id"] == student_id and row["date"] == str(today):
            return  # Already marked today

    now = datetime.now()
    with open(ATTENDANCE_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if os.path.getsize(ATTENDANCE_FILE) == 0:
            writer.writerow(["student_id", "date", "time", "status"])
        writer.writerow([student_id, str(now.date()), now.strftime("%H:%M:%S"), "Present"])
    print(f"Attendance marked for {student_id} at {now.strftime('%H:%M:%S')}")
