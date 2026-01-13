import requests

BACKEND_URL = "http://127.0.0.1:5000"

def mark_attendance(student_id):
    response = requests.post(
        f"{BACKEND_URL}/mark_attendance",
        json={"student_id": student_id}
    )
    return response.json()
