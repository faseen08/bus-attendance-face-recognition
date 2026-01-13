from flask import Flask, request, jsonify
from database.db import get_connection
from database.attendance_db import mark_attendance_db


app = Flask(__name__)

@app.route("/")
def home():
    return "Bus Attendance Backend Running"

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    data = request.json
    student_id = data.get("student_id")

    if not student_id:
        return jsonify({"error": "student_id missing"}), 400

    marked = mark_attendance_db(student_id)

    if marked:
        return jsonify({"status": "Attendance marked"})
    else:
        return jsonify({"status": "Already marked today"})

@app.route("/attendance", methods=["GET"])
def get_attendance():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM attendance ORDER BY date DESC, time DESC").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    app.run(debug=True)
