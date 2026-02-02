from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging

from database.db import init_db
from database.db import get_connection
from database.attendance_db import mark_attendance_db
from werkzeug.utils import secure_filename
from flask import send_from_directory

app = Flask(__name__)
CORS(app)

@app.route('/data/<path:filename>')
def serve_data(filename):
    # This points to your actual data folder
    return send_from_directory(os.path.join(os.getcwd(), 'data'), filename)

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_students_from_disk():
    """Sync students table with data/students folder (Add new / Remove deleted)."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'students')
    if not os.path.isdir(data_dir):
        return

    conn = get_connection()
    cur = conn.cursor()

    # --- PART 1: ADD NEW STUDENTS ---
    existing_folders = sorted(os.listdir(data_dir))
    for name in existing_folders:
        path = os.path.join(data_dir, name)
        if not os.path.isdir(path):
            continue
        
        student_id = name
        exists = cur.execute("SELECT id FROM students WHERE student_id = ?", (student_id,)).fetchone()
        
        if not exists:
            photo = None
            try:
                for fname in os.listdir(path):
                    if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                        photo = os.path.join('data', 'students', name, fname)
                        break
            except Exception:
                photo = None

            cur.execute(
                "INSERT INTO students (student_id, name, photo_path) VALUES (?, ?, ?)",
                (student_id, student_id, photo)
            )

    # --- PART 2: REMOVE DELETED STUDENTS ---
    # Fetch all IDs currently in the DB
    db_students = cur.execute("SELECT student_id FROM students").fetchall()
    for row in db_students:
        s_id = row[0]
        # If the folder doesn't exist anymore, delete from DB
        if s_id not in existing_folders:
            logger.info(f"Removing {s_id} from database as folder was deleted.")
            cur.execute("DELETE FROM students WHERE student_id = ?", (s_id,))
            # Optional: Also delete their attendance history?
            # cur.execute("DELETE FROM attendance WHERE student_id = ?", (s_id,))

    conn.commit()
    conn.close()

@app.route("/")
def home():
    return "Bus Attendance Backend Running"

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    data = request.json
    student_id = data.get("student_id")

    if not student_id:
        return jsonify({"error": "student_id missing"}), 400

    # verify student exists
    try:
        conn = get_connection()
        exists = conn.execute(
            "SELECT id FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        conn.close()
    except Exception as e:
        logger.exception("DB error checking student")
        return jsonify({"error": "database error"}), 500

    if not exists:
        return jsonify({"error": "unknown student_id"}), 404

    marked = mark_attendance_db(student_id)

    if marked:
        return jsonify({"status": "Attendance marked"})
    else:
        return jsonify({"status": "Already marked today"})

@app.route("/attendance", methods=["GET"])
def get_attendance():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT student_id, date, time FROM attendance ORDER BY date DESC, time DESC"
    )
    rows = cursor.fetchall()
    conn.close()

    result = []
    for student_id, date, time in rows:
        result.append({
            "student_id": student_id,
            "date": date,
            "time": time
        })

    return jsonify(result)


@app.route("/students", methods=["GET"])
def get_students():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM students ORDER BY student_id").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/students/count", methods=["GET"])
def get_students_count():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM students")
    count = cursor.fetchone()[0]

    conn.close()

    return jsonify({"count": count})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


UPLOAD_DIR = os.path.join("data", "students")

@app.route("/students", methods=["POST"])
def add_student():
    student_id = request.form.get("student_id")
    name = request.form.get("name") # Added name
    bus_stop = request.form.get("bus_stop") # Added bus_stop
    photo = request.files.get("photo")

    if not student_id or not photo:
        return jsonify({"error": "missing data"}), 400

    folder = os.path.join(UPLOAD_DIR, student_id)
    os.makedirs(folder, exist_ok=True)

    filename = secure_filename(photo.filename)
    photo_path = os.path.join(folder, filename)
    photo.save(photo_path)

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO students (student_id, name, bus_stop, photo_path) VALUES (?, ?, ?, ?)",
            (student_id, name if name else student_id, bus_stop, photo_path)
        )
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"status": "student added"})

@app.route("/students/toggle_leave", methods=["POST"])
def toggle_leave():
    data = request.json
    student_id = data.get("student_id")
    
    if not student_id:
        return jsonify({"error": "ID missing"}), 400

    conn = get_connection()
    # Check current status
    student = conn.execute("SELECT on_leave FROM students WHERE student_id = ?", (student_id,)).fetchone()
    
    if not student:
        conn.close()
        return jsonify({"error": "Student not found"}), 404

    # Toggle: if 0 set to 1, if 1 set to 0
    new_status = 1 if student[0] == 0 else 0
    conn.execute("UPDATE students SET on_leave = ? WHERE student_id = ?", (new_status, student_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "Success", "on_leave": new_status})

if __name__ == "__main__":
    # Ensure DB schema exists and seed students from disk (helpful for development)
    try:
        init_db()
    except Exception:
        # init_db may be no-op if DB already initialized
        pass


    seed_students_from_disk()

    app.run(debug=True)
