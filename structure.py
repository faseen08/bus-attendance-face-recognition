import os

structure = {
    "README.md": "",
    "requirements.txt": "",
    "main.py": "",
    "data": {
        "students": {},
        "attendance": {"attendance.csv": ""},
        "drivers": {"drivers.csv": ""},
        "leaves": {"leaves.csv": ""}
    },
    "face_engine": {
        "__init__.py": "",
        "face_detect.py": "",
        "face_recognize.py": ""
    },
    "modules": {
        "__init__.py": "",
        "student_registration.py": "",
        "attendance_manager.py": "",
        "leave_manager.py": "",
        "driver_attendance.py": "",
        "bus_location.py": "",
        "alerts.py": ""
    },
    "dashboard": {
        "admin_dashboard.py": ""
    }
}

def create(path, tree):
    for name, content in tree.items():
        full = os.path.join(path, name)
        if isinstance(content, dict):
            os.makedirs(full, exist_ok=True)
            create(full, content)
        else:
            open(full, "a").close()

create(".", structure)
print("Project structure created successfully")
