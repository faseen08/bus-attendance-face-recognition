from backend.client import mark_attendance as mark_attendance_backend

def mark_attendance(student_id):
    """
    This function acts as a bridge.
    It sends the student_id to the backend API.
    """
    result = mark_attendance_backend(student_id)
    print(f"[ATTENDANCE] {result['status']}")

