from backend.client import mark_attendance as mark_attendance_backend

def mark_attendance(student_id):
    try:
        result = mark_attendance_backend(student_id)
        trip_type = result.get("trip_type") or "UNKNOWN"
        print(f"[ATTENDANCE] {result.get('status')} for {trip_type}")
    except Exception as e:
        print("[ATTENDANCE] Backend unavailable")

    
