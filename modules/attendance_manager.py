from backend.client import mark_attendance as mark_attendance_backend

def mark_attendance(student_id):
    try:
        result = mark_attendance_backend(student_id)
        print(f"[ATTENDANCE] {result.get('status')}")
    except Exception as e:
        print("[ATTENDANCE] Backend unavailable")

    return result.get("status") == "Attendance marked"
    

