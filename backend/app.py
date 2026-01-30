from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging

from database.db import init_db
from database.db import get_connection
from database.attendance_db import mark_attendance_db


app = Flask(__name__)
CORS(app)


# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_students_from_disk():
    """Ensure students table contains entries for folders in data/students."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'students')
    if not os.path.isdir(data_dir):
        return

    conn = get_connection()
    cur = conn.cursor()

    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isdir(path):
            continue
        student_id = name
        exists = cur.execute("SELECT id FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if exists:
            continue

        # attempt to find a photo in the folder
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


if __name__ == "__main__":
    # Ensure DB schema exists and seed students from disk (helpful for development)
    try:
        init_db()
    except Exception:
        # init_db may be no-op if DB already initialized
        pass

    seed_students_from_disk()

    app.run(debug=True)
