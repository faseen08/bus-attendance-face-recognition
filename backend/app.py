from datetime import datetime
import os
import argparse
import json
import shutil
import logging

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_identity, get_jwt
from werkzeug.utils import secure_filename

from database.db import init_db, get_connection
from database.attendance_db import mark_attendance_db
from backend.auth import (
    authenticate_user,
    generate_token,
    create_user,
    require_auth,
    require_role,
    verify_password,
    hash_password,
)
from modules.driver_manager import (
    get_driver,
    log_student_boarding,
    log_student_alighting,
    is_student_on_bus,
    get_students_on_bus,
    get_driver_stats,
    get_daily_summary,
)
from modules.alerts import send_boarded_alert_for_student, evaluate_not_boarded_alerts

app = Flask(__name__)
CORS(app)
app.config["JWT_SECRET_KEY"] = "your-secret-key-change-in-production"
jwt = JWTManager(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@jwt.invalid_token_loader
def invalid_token_callback(error_string):
    return jsonify({"error": "Invalid token", "detail": error_string}), 401


@jwt.unauthorized_loader
def missing_token_callback(error_string):
    return jsonify({"error": "Authorization token required", "detail": error_string}), 401


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({"error": "Token expired"}), 401


def _utc_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def _driver_id_from_user(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT student_id FROM users WHERE id = ?", (str(user_id),)
        ).fetchone()
        if not row or not row["student_id"]:
            return None
        return row["student_id"]
    finally:
        conn.close()


@app.route("/")
def home():
    return "Bus Attendance Backend Running"

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

@app.route("/frontend/<path:filename>")
def serve_frontend(filename):
    return send_from_directory(FRONTEND_DIR, filename)

@app.route("/frontend")
def serve_frontend_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory(os.path.join(os.getcwd(), 'data'), filename)


# ============================================================================
# AUTHENTICATION
# ============================================================================

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json or {}
        username = data.get("id")
        password = data.get("password")
        role = data.get("role", "student")

        if not username or not password:
            return jsonify({"error": "Missing username or password"}), 400

        user = authenticate_user(username, password)
        if not user:
            return jsonify({"error": "Invalid username or password"}), 401

        if user["role"] != role:
            return jsonify({"error": f"This account is not a {role}"}), 403

        token = generate_token(user["id"], user["username"], user["role"])
        return jsonify({"token": token, "user": user}), 200
    except Exception:
        logger.exception("Login error")
        return jsonify({"error": "Login failed"}), 500


@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.json or {}
        username = data.get("username")
        password = data.get("password")
        role = data.get("role", "student")
        student_id = data.get("student_id")

        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400
        if role == "student" and not student_id:
            return jsonify({"error": "Student ID required for student role"}), 400

        result = create_user(username, password, role, student_id)
        if not result["success"]:
            return jsonify({"error": result["error"]}), 400

        user = authenticate_user(username, password)
        token = generate_token(user["id"], user["username"], user["role"])
        return jsonify({"message": "User registered successfully", "token": token, "user": user}), 201
    except Exception:
        logger.exception("Registration error")
        return jsonify({"error": "Registration failed"}), 500


@app.route("/verify-token", methods=["GET"])
@require_auth
def verify_token():
    user_id = get_jwt_identity()
    claims = get_jwt()
    return jsonify({"valid": True, "user_id": user_id, "role": claims.get("role")}), 200


@app.route("/users/change-password", methods=["POST"])
@require_auth
def change_password():
    data = request.json or {}
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return jsonify({"error": "current_password and new_password are required"}), 400
    if len(str(new_password)) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    user_id = str(get_jwt_identity())
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        if not verify_password(current_password, user["password_hash"]):
            return jsonify({"error": "Current password is incorrect"}), 400

        new_hash = hash_password(new_password)
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id),
        )
        conn.commit()
        return jsonify({"status": "Password updated successfully"}), 200
    finally:
        conn.close()


@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.json or {}
    role = (data.get("role") or "").strip()
    username = (data.get("username") or data.get("id") or "").strip()
    new_password = data.get("new_password")

    if role not in ("student", "driver", "admin"):
        return jsonify({"error": "Invalid role"}), 400
    if not username or not new_password:
        return jsonify({"error": "username and new_password are required"}), 400
    if len(str(new_password)) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT id, username, role, student_id FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not user or user["role"] != role:
            return jsonify({"error": "Account not found for that role"}), 404

        if role == "student":
            parent_phone = (data.get("parent_phone") or "").strip()
            if not parent_phone:
                return jsonify({"error": "Parent phone is required"}), 400
            row = conn.execute(
                "SELECT parent_phone FROM students WHERE student_id = ?",
                (user["student_id"],),
            ).fetchone()
            if not row or not row["parent_phone"]:
                return jsonify({"error": "Parent phone not set. Contact admin."}), 400
            if row["parent_phone"] != parent_phone:
                return jsonify({"error": "Parent phone does not match"}), 400

        if role == "driver":
            phone = (data.get("phone") or "").strip()
            if not phone:
                return jsonify({"error": "Phone is required"}), 400
            row = conn.execute(
                "SELECT phone FROM drivers WHERE driver_id = ?",
                (username,),
            ).fetchone()
            if not row or not row["phone"]:
                return jsonify({"error": "Driver phone not set. Contact admin."}), 400
            if row["phone"] != phone:
                return jsonify({"error": "Phone does not match"}), 400

        if role == "admin":
            reset_code = (data.get("reset_code") or "").strip()
            expected = os.environ.get("ADMIN_RESET_CODE", "")
            if not expected:
                return jsonify({"error": "Admin reset code not configured"}), 400
            if reset_code != expected:
                return jsonify({"error": "Invalid admin reset code"}), 400

        new_hash = hash_password(new_password)
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user["id"]),
        )
        conn.commit()
        return jsonify({"status": "Password reset successful"}), 200
    finally:
        conn.close()


# ============================================================================
# ADMIN REQUESTS (student/driver add, leave requests)
# ============================================================================

@app.route("/requests/student", methods=["POST"])
def request_student_add():
    data = request.json or {}
    student_id = (data.get("student_id") or "").strip()
    name = (data.get("name") or "").strip() or student_id
    bus_number = (data.get("bus_number") or "").strip()
    bus_stop = (data.get("bus_stop") or "").strip()
    parent_name = (data.get("parent_name") or "").strip() or None
    parent_phone = (data.get("parent_phone") or "").strip()
    password = data.get("password")
    education_type = (data.get("education_type") or "").strip() or None
    college_type = (data.get("college_type") or "").strip() or None
    college_year = (data.get("college_year") or "").strip() or None
    college_department = (data.get("college_department") or "").strip() or None
    school_class = (data.get("school_class") or "").strip() or None
    school_division = (data.get("school_division") or "").strip() or None

    if not student_id or not bus_number or not bus_stop or not parent_phone or not password:
        return jsonify({"error": "student_id, bus_number, bus_stop, parent_phone, password required"}), 400
    if len(str(password)) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (student_id,)
        ).fetchone()
        if exists or user_exists:
            return jsonify({"error": "Student already exists"}), 400

        payload = {
            "student_id": student_id,
            "name": name,
            "bus_number": bus_number,
            "bus_stop": bus_stop,
            "parent_name": parent_name,
            "parent_phone": parent_phone,
            "password": password,
            "education_type": education_type,
            "college_type": college_type,
            "college_year": college_year,
            "college_department": college_department,
            "school_class": school_class,
            "school_division": school_division,
        }
        conn.execute(
            """
            INSERT INTO admin_requests (request_type, requester_role, requester_id, payload)
            VALUES (?, ?, ?, ?)
            """,
            ("STUDENT_ADD", "student", student_id, json.dumps(payload)),
        )
        conn.commit()
        return jsonify({"status": "request submitted"}), 201
    finally:
        conn.close()


@app.route("/requests/driver", methods=["POST"])
def request_driver_add():
    data = request.json or {}
    driver_id = (data.get("driver_id") or "").strip()
    name = (data.get("name") or "").strip() or driver_id
    bus_number = (data.get("bus_number") or "").strip()
    phone = (data.get("phone") or "").strip()
    license_number = (data.get("license_number") or "").strip() or None
    password = data.get("password")

    if not driver_id or not name or not bus_number or not phone or not password:
        return jsonify({"error": "driver_id, name, bus_number, phone, password required"}), 400
    if len(str(password)) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM drivers WHERE driver_id = ?", (driver_id,)
        ).fetchone()
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (driver_id,)
        ).fetchone()
        if exists or user_exists:
            return jsonify({"error": "Driver already exists"}), 400

        payload = {
            "driver_id": driver_id,
            "name": name,
            "bus_number": bus_number,
            "phone": phone,
            "license_number": license_number,
            "password": password,
        }
        conn.execute(
            """
            INSERT INTO admin_requests (request_type, requester_role, requester_id, payload)
            VALUES (?, ?, ?, ?)
            """,
            ("DRIVER_ADD", "driver", driver_id, json.dumps(payload)),
        )
        conn.commit()
        return jsonify({"status": "request submitted"}), 201
    finally:
        conn.close()


@app.route("/requests/leave", methods=["POST"])
@require_auth
def request_leave():
    data = request.json or {}
    desired_status = 1 if str(data.get("desired_status", "1")) not in ("0", "false", "False") else 0
    reason = (data.get("reason") or "").strip() or None
    user_id = str(get_jwt_identity())
    claims = get_jwt()

    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT student_id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user or not user["student_id"]:
            return jsonify({"error": "Only students can request leave"}), 403

        student_id = user["student_id"]
        pending = conn.execute(
            """
            SELECT 1 FROM admin_requests
            WHERE request_type = 'LEAVE' AND status = 'PENDING' AND requester_id = ?
            """,
            (student_id,),
        ).fetchone()
        if pending:
            return jsonify({"error": "Leave request already pending"}), 400

        payload = {
            "student_id": student_id,
            "desired_status": desired_status,
            "reason": reason,
            "requested_by": claims.get("username"),
        }
        conn.execute(
            """
            INSERT INTO admin_requests (request_type, requester_role, requester_id, payload)
            VALUES (?, ?, ?, ?)
            """,
            ("LEAVE", "student", student_id, json.dumps(payload)),
        )
        conn.commit()
        return jsonify({"status": "request submitted"}), 201
    finally:
        conn.close()


@app.route("/admin/requests", methods=["GET"])
@require_auth
@require_role("admin")
def admin_requests():
    req_type = request.args.get("type")
    status = request.args.get("status", "PENDING")
    conn = get_connection()
    try:
        query = "SELECT * FROM admin_requests WHERE 1=1"
        params = []
        if req_type:
            query += " AND request_type = ?"
            params.append(req_type)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows]), 200
    finally:
        conn.close()


@app.route("/admin/requests/<int:request_id>/approve", methods=["POST"])
@require_auth
@require_role("admin")
def approve_request(request_id):
    claims = get_jwt()
    reviewer = claims.get("username")
    notes = (request.json or {}).get("notes")
    conn = get_connection()
    try:
        req = conn.execute(
            "SELECT * FROM admin_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if not req:
            return jsonify({"error": "Request not found"}), 404
        if req["status"] != "PENDING":
            return jsonify({"error": "Request already processed"}), 400

        payload = json.loads(req["payload"] or "{}")
        if req["request_type"] == "STUDENT_ADD":
            student_id = payload.get("student_id")
            exists = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()
            user_exists = conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (student_id,)
            ).fetchone()
            if exists or user_exists:
                return jsonify({"error": "Student already exists"}), 400

            conn.execute(
                """
                INSERT INTO students (
                    student_id, name, bus_number, bus_stop, photo_path,
                    parent_name, parent_phone, alerts_enabled, on_leave,
                    education_type, college_type, college_year, college_department,
                    school_class, school_division
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    payload.get("name") or student_id,
                    payload.get("bus_number"),
                    payload.get("bus_stop"),
                    None,
                    payload.get("parent_name"),
                    payload.get("parent_phone"),
                    1,
                    0,
                    payload.get("education_type"),
                    payload.get("college_type"),
                    payload.get("college_year"),
                    payload.get("college_department"),
                    payload.get("school_class"),
                    payload.get("school_division"),
                ),
            )

            user_result = create_user(
                username=student_id,
                password=payload.get("password"),
                role="student",
                student_id=student_id,
            )
            if not user_result.get("success"):
                return jsonify({"error": user_result.get("error")}), 400

        elif req["request_type"] == "DRIVER_ADD":
            driver_id = payload.get("driver_id")
            exists = conn.execute(
                "SELECT 1 FROM drivers WHERE driver_id = ?", (driver_id,)
            ).fetchone()
            user_exists = conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (driver_id,)
            ).fetchone()
            if exists or user_exists:
                return jsonify({"error": "Driver already exists"}), 400

            conn.execute(
                """
                INSERT INTO drivers (driver_id, name, bus_number, phone, license_number)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    driver_id,
                    payload.get("name") or driver_id,
                    payload.get("bus_number"),
                    payload.get("phone"),
                    payload.get("license_number"),
                ),
            )

            user_result = create_user(
                username=driver_id,
                password=payload.get("password"),
                role="driver",
                student_id=None,
            )
            if not user_result.get("success"):
                return jsonify({"error": user_result.get("error")}), 400

        elif req["request_type"] == "LEAVE":
            student_id = payload.get("student_id")
            desired_status = 1 if str(payload.get("desired_status", "1")) not in ("0", "false", "False") else 0
            conn.execute(
                "UPDATE students SET on_leave = ? WHERE student_id = ?",
                (desired_status, student_id),
            )
        else:
            return jsonify({"error": "Unknown request type"}), 400

        conn.execute(
            """
            UPDATE admin_requests
            SET status = 'APPROVED',
                reviewed_at = CURRENT_TIMESTAMP,
                reviewed_by = ?,
                reviewed_notes = ?
            WHERE id = ?
            """,
            (reviewer, notes, request_id),
        )
        conn.commit()
        return jsonify({"status": "approved"}), 200
    finally:
        conn.close()


@app.route("/admin/requests/<int:request_id>/reject", methods=["POST"])
@require_auth
@require_role("admin")
def reject_request(request_id):
    claims = get_jwt()
    reviewer = claims.get("username")
    notes = (request.json or {}).get("notes")
    conn = get_connection()
    try:
        req = conn.execute(
            "SELECT * FROM admin_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if not req:
            return jsonify({"error": "Request not found"}), 404
        if req["status"] != "PENDING":
            return jsonify({"error": "Request already processed"}), 400

        conn.execute(
            """
            UPDATE admin_requests
            SET status = 'REJECTED',
                reviewed_at = CURRENT_TIMESTAMP,
                reviewed_by = ?,
                reviewed_notes = ?
            WHERE id = ?
            """,
            (reviewer, notes, request_id),
        )
        conn.commit()
        return jsonify({"status": "rejected"}), 200
    finally:
        conn.close()


# ============================================================================
# CORE STUDENT/ATTENDANCE ROUTES
# ============================================================================

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    data = request.json or {}
    student_id = data.get("student_id")
    if not student_id:
        return jsonify({"error": "student_id missing"}), 400

    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT id FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
    finally:
        conn.close()

    if not exists:
        return jsonify({"error": "unknown student_id"}), 404

    marked = mark_attendance_db(student_id)
    if marked:
        return jsonify({"status": "Attendance marked"}), 200
    return jsonify({"status": "Already marked today"}), 200


@app.route("/attendance", methods=["GET"])
def get_attendance():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT student_id, date, time, direction FROM attendance ORDER BY date DESC, time DESC"
        ).fetchall()
    finally:
        conn.close()

    return jsonify([
        {
            "student_id": row["student_id"],
            "date": row["date"],
            "time": row["time"],
            "direction": row["direction"] if row["direction"] else "IN",
        }
        for row in rows
    ])


@app.route("/students", methods=["GET"])
def get_students():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM students ORDER BY student_id").fetchall()
        return jsonify([dict(row) for row in rows])
    finally:
        conn.close()


@app.route("/students/count", methods=["GET"])
def get_students_count():
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM students").fetchone()["c"]
        return jsonify({"count": count})
    finally:
        conn.close()


UPLOAD_DIR = os.path.join("data", "students")


@app.route("/students", methods=["POST"])
@require_auth
@require_role("admin")
def add_student():
    student_id = request.form.get("student_id")
    name = request.form.get("name")
    bus_number = request.form.get("bus_number")
    bus_stop = request.form.get("bus_stop")
    parent_name = request.form.get("parent_name")
    parent_phone = request.form.get("parent_phone")
    alerts_enabled = request.form.get("alerts_enabled", "1")
    education_type = (request.form.get("education_type") or "").strip() or None
    college_type = (request.form.get("college_type") or "").strip() or None
    college_year = (request.form.get("college_year") or "").strip() or None
    college_department = (request.form.get("college_department") or "").strip() or None
    school_class = (request.form.get("school_class") or "").strip() or None
    school_division = (request.form.get("school_division") or "").strip() or None
    initial_password = (request.form.get("initial_password") or "").strip()
    photo = request.files.get("photo")

    if not student_id or not photo or not bus_number:
        return jsonify({"error": "missing data"}), 400

    folder = os.path.join(UPLOAD_DIR, student_id)
    os.makedirs(folder, exist_ok=True)

    original_name = secure_filename(photo.filename or "")
    _, ext = os.path.splitext(original_name)
    if not ext:
        ext = ".jpg"
    safe_name = f"profile{ext}"
    # Ensure only one photo exists for the student by clearing the folder.
    for entry in os.listdir(folder):
        path = os.path.join(folder, entry)
        if os.path.isfile(path):
            os.remove(path)
    photo_path = os.path.join(folder, safe_name)
    photo.save(photo_path)

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO students (
                student_id, name, bus_number, bus_stop, photo_path,
                parent_name, parent_phone, alerts_enabled,
                education_type, college_type, college_year, college_department,
                school_class, school_division
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                name if name else student_id,
                bus_number,
                bus_stop,
                photo_path,
                parent_name,
                parent_phone,
                1 if str(alerts_enabled) != "0" else 0,
                education_type,
                college_type,
                college_year,
                college_department,
                school_class,
                school_division,
            ),
        )
        conn.commit()

        # Create login account with default password if missing.
        default_password = "pass123"
        password_to_set = initial_password if initial_password else default_password
        user_result = create_user(
            username=student_id,
            password=password_to_set,
            role="student",
            student_id=student_id,
        )
        account = {
            "created": False,
            "username": student_id,
            "password": None,
            "message": "Login account already exists",
        }
        if user_result.get("success"):
            account = {
                "created": True,
                "username": student_id,
                "password": password_to_set,
                "message": "Login created",
            }
        else:
            err = (user_result.get("error") or "").lower()
            if "unique constraint failed" not in err:
                account = {
                    "created": False,
                    "username": student_id,
                    "password": None,
                    "message": f"Login creation failed: {user_result.get('error')}",
                }

        return jsonify({"status": "student added", "account": account}), 201
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        conn.close()


@app.route("/students/<student_id>", methods=["DELETE"])
@require_auth
@require_role("admin")
def delete_student(student_id):
    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT student_id FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if not exists:
            return jsonify({"error": "Student not found"}), 404

        conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM driver_logs WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM notifications WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM trip_student_state WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM users WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        conn.commit()
    finally:
        conn.close()

    folder = os.path.join(UPLOAD_DIR, student_id)
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)

    return jsonify({"status": "deleted", "student_id": student_id}), 200


@app.route("/students/<student_id>/profile", methods=["GET"])
@require_auth
def get_student_profile(student_id):
    claims = get_jwt()
    role = claims.get("role")
    current_user_id = get_jwt_identity()

    conn = get_connection()
    try:
        if role == "student":
            user = conn.execute(
                "SELECT student_id FROM users WHERE id = ?", (str(current_user_id),)
            ).fetchone()
            if not user or user["student_id"] != student_id:
                return jsonify({"error": "You can only view your own profile"}), 403
        elif role != "admin":
            return jsonify({"error": "Only student/admin can access this endpoint"}), 403

        row = conn.execute(
            """
            SELECT student_id, name, bus_number, bus_stop,
                   parent_name, parent_phone, alerts_enabled, on_leave, photo_path,
                   education_type, college_type, college_year, college_department, school_class, school_division
            FROM students WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "Student not found"}), 404
        return jsonify(dict(row)), 200
    finally:
        conn.close()


@app.route("/students/<student_id>/profile", methods=["POST"])
@require_auth
def update_student_profile(student_id):
    claims = get_jwt()
    role = claims.get("role")
    current_user_id = get_jwt_identity()
    data = request.json or {}

    conn = get_connection()
    try:
        if role == "student":
            user = conn.execute(
                "SELECT student_id FROM users WHERE id = ?", (str(current_user_id),)
            ).fetchone()
            if not user or user["student_id"] != student_id:
                return jsonify({"error": "You can only update your own profile"}), 403
        elif role != "admin":
            return jsonify({"error": "Only student/admin can access this endpoint"}), 403

        exists = conn.execute(
            "SELECT student_id FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if not exists:
            return jsonify({"error": "Student not found"}), 404

        name = (data.get("name") or "").strip() or None
        bus_stop = (data.get("bus_stop") or "").strip() or None
        parent_name = (data.get("parent_name") or "").strip() or None
        parent_phone = (data.get("parent_phone") or "").strip() or None
        alerts_enabled = data.get("alerts_enabled")
        education_type = (data.get("education_type") or "").strip() or None
        college_type = (data.get("college_type") or "").strip() or None
        college_year = (data.get("college_year") or "").strip() or None
        college_department = (data.get("college_department") or "").strip() or None
        school_class = (data.get("school_class") or "").strip() or None
        school_division = (data.get("school_division") or "").strip() or None
        if alerts_enabled is None:
            alerts_enabled = 1
        alerts_enabled = 1 if str(alerts_enabled) not in ("0", "false", "False") else 0

        if parent_phone and not parent_phone.startswith("+"):
            return jsonify({"error": "Parent phone must include country code (e.g. +91...)"}), 400

        if role == "admin" and "bus_number" in data:
            bus_number = (data.get("bus_number") or "").strip() or None
            conn.execute(
                """
                UPDATE students
                SET name = COALESCE(?, name),
                    bus_stop = ?,
                    bus_number = COALESCE(?, bus_number),
                    parent_name = ?,
                    parent_phone = ?,
                    alerts_enabled = ?,
                    education_type = COALESCE(?, education_type),
                    college_type = ?,
                    college_year = ?,
                    college_department = ?,
                    school_class = ?,
                    school_division = ?
                WHERE student_id = ?
                """,
                (
                    name,
                    bus_stop,
                    bus_number,
                    parent_name,
                    parent_phone,
                    alerts_enabled,
                    education_type,
                    college_type,
                    college_year,
                    college_department,
                    school_class,
                    school_division,
                    student_id,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE students
                SET name = COALESCE(?, name),
                    bus_stop = ?,
                    parent_name = ?,
                    parent_phone = ?,
                    alerts_enabled = ?,
                    education_type = COALESCE(?, education_type),
                    college_type = ?,
                    college_year = ?,
                    college_department = ?,
                    school_class = ?,
                    school_division = ?
                WHERE student_id = ?
                """,
                (
                    name,
                    bus_stop,
                    parent_name,
                    parent_phone,
                    alerts_enabled,
                    education_type,
                    college_type,
                    college_year,
                    college_department,
                    school_class,
                    school_division,
                    student_id,
                ),
            )

        conn.commit()

        updated = conn.execute(
            """
            SELECT student_id, name, bus_number, bus_stop,
                   parent_name, parent_phone, alerts_enabled, on_leave, photo_path,
                   education_type, college_type, college_year, college_department, school_class, school_division
            FROM students WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
        return jsonify({"status": "updated", "student": dict(updated)}), 200
    finally:
        conn.close()


@app.route("/students/<student_id>/photo", methods=["POST"])
@require_auth
def update_student_photo(student_id):
    claims = get_jwt()
    role = claims.get("role")
    current_user_id = get_jwt_identity()

    conn = get_connection()
    try:
        if role == "student":
            user = conn.execute(
                "SELECT student_id FROM users WHERE id = ?", (str(current_user_id),)
            ).fetchone()
            if not user or user["student_id"] != student_id:
                return jsonify({"error": "You can only update your own photo"}), 403
        elif role != "admin":
            return jsonify({"error": "Only student/admin can access this endpoint"}), 403

        student = conn.execute(
            "SELECT student_id FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if not student:
            return jsonify({"error": "Student not found"}), 404

        photo = request.files.get("photo")
        if not photo:
            return jsonify({"error": "Photo is required"}), 400

        folder = os.path.join(UPLOAD_DIR, student_id)
        os.makedirs(folder, exist_ok=True)

        original_name = secure_filename(photo.filename or "")
        _, ext = os.path.splitext(original_name)
        if not ext:
            ext = ".jpg"
        safe_name = f"profile{ext}"
        # Ensure only one photo exists for the student by clearing the folder.
        for entry in os.listdir(folder):
            path = os.path.join(folder, entry)
            if os.path.isfile(path):
                os.remove(path)
        photo_path = os.path.join(folder, safe_name)
        photo.save(photo_path)

        conn.execute(
            "UPDATE students SET photo_path = ? WHERE student_id = ?",
            (photo_path, student_id),
        )
        conn.commit()

        return jsonify({"status": "updated", "photo_path": photo_path}), 200
    finally:
        conn.close()


@app.route("/students/toggle_leave", methods=["POST"])
def toggle_leave():
    try:
        data = request.json or {}
        student_id = data.get("student_id")
        if not student_id:
            return jsonify({"error": "ID missing"}), 400

        conn = get_connection()
        student = conn.execute(
            "SELECT on_leave FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if not student:
            conn.close()
            return jsonify({"error": "Student not found"}), 404

        new_status = 1 if student["on_leave"] == 0 else 0
        conn.execute(
            "UPDATE students SET on_leave = ? WHERE student_id = ?",
            (new_status, student_id),
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "Success", "on_leave": new_status}), 200
    except Exception as exc:
        logger.exception("Error in toggle_leave")
        return jsonify({"error": str(exc)}), 500


# ============================================================================
# STUDENT STOP LOCATION + LIVE BUS VIEW
# ============================================================================

@app.route("/students/<student_id>/stop-location", methods=["GET"])
def get_student_stop_location(student_id):
    conn = get_connection()
    try:
        student = conn.execute(
            """
            SELECT student_id, bus_stop_lat, bus_stop_lng, bus_stop_label
            FROM students WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
        if not student:
            return jsonify({"error": "Student not found"}), 404

        return jsonify(
            {
                "student_id": student["student_id"],
                "bus_stop_lat": student["bus_stop_lat"],
                "bus_stop_lng": student["bus_stop_lng"],
                "bus_stop_label": student["bus_stop_label"],
            }
        ), 200
    finally:
        conn.close()


@app.route("/students/<student_id>/stop-location", methods=["POST"])
@require_auth
def set_student_stop_location(student_id):
    claims = get_jwt()
    role = claims.get("role")
    current_user_id = get_jwt_identity()

    conn = get_connection()
    try:
        if role == "student":
            user = conn.execute(
                "SELECT student_id FROM users WHERE id = ?", (str(current_user_id),)
            ).fetchone()
            if not user or user["student_id"] != student_id:
                return jsonify({"error": "You can only update your own stop location"}), 403

        data = request.json or {}
        lat = data.get("lat")
        lng = data.get("lng")
        label = data.get("label")

        if lat is None or lng is None:
            return jsonify({"error": "lat and lng are required"}), 400

        conn.execute(
            """
            UPDATE students
            SET bus_stop_lat = ?, bus_stop_lng = ?, bus_stop_label = ?, bus_stop = COALESCE(?, bus_stop)
            WHERE student_id = ?
            """,
            (float(lat), float(lng), label, label, student_id),
        )
        conn.commit()
        return jsonify({"status": "saved"}), 200
    finally:
        conn.close()


@app.route("/bus/location/current", methods=["GET"])
def bus_location_current():
    student_id = request.args.get("student_id")
    if not student_id:
        return jsonify({"error": "student_id required"}), 400

    conn = get_connection()
    try:
        student = conn.execute(
            "SELECT bus_number FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if not student:
            return jsonify({"error": "Student not found"}), 404

        trip = conn.execute(
            """
            SELECT id, bus_number, trip_type, started_at
            FROM bus_trips
            WHERE bus_number = ? AND status = 'ACTIVE'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (student["bus_number"],),
        ).fetchone()
        if not trip:
            return jsonify({"error": "No active trip for this bus"}), 404

        loc = conn.execute(
            """
            SELECT lat, lng, speed, heading, COALESCE(timestamp, recorded_at) AS ts
            FROM bus_locations
            WHERE trip_id = ?
            ORDER BY COALESCE(timestamp, recorded_at) DESC
            LIMIT 1
            """,
            (trip["id"],),
        ).fetchone()
        if not loc:
            return jsonify({"error": "No location updates yet"}), 404

        return jsonify(
            {
                "trip_id": trip["id"],
                "bus_number": trip["bus_number"],
                "trip_type": trip["trip_type"],
                "lat": loc["lat"],
                "lng": loc["lng"],
                "speed": loc["speed"],
                "heading": loc["heading"],
                "timestamp": loc["ts"],
            }
        ), 200
    finally:
        conn.close()


# ============================================================================
# DRIVER ROUTES
# ============================================================================

@app.route('/driver/dashboard', methods=['GET'])
@require_auth
@require_role("driver")
def driver_dashboard():
    try:
        user_id = int(get_jwt_identity())
        conn = get_connection()
        user = conn.execute("SELECT student_id FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()

        if not user:
            return jsonify({"error": "User not found"}), 404

        driver_id = user["student_id"]
        driver_info = get_driver(driver_id)
        if not driver_info:
            return jsonify({"error": "Driver not found"}), 404

        stats = get_driver_stats(driver_id)
        return jsonify({"driver": driver_info, "statistics": stats}), 200
    except Exception as exc:
        logger.exception("Error in driver_dashboard")
        return jsonify({"error": str(exc)}), 500


@app.route('/driver/log-boarding', methods=['POST'])
@require_auth
@require_role("driver")
def driver_log_boarding():
    try:
        data = request.get_json() or {}
        student_id = data.get('student_id')
        if not student_id:
            return jsonify({"error": "Student ID required"}), 400

        driver_id = _driver_id_from_user(get_jwt_identity())
        if not driver_id:
            return jsonify({"error": "User not found"}), 404

        result = log_student_boarding(driver_id, student_id)
        if not result['success']:
            return jsonify({"error": result['error']}), 400

        alert_result = send_boarded_alert_for_student(student_id, driver_id)

        return jsonify({
            "message": result['message'],
            "student_id": student_id,
            "action": "IN",
            "alert": alert_result,
        }), 200
    except Exception as exc:
        logger.exception("Error in driver_log_boarding")
        return jsonify({"error": str(exc)}), 500


@app.route('/driver/log-alighting', methods=['POST'])
@require_auth
@require_role("driver")
def driver_log_alighting():
    try:
        data = request.get_json() or {}
        student_id = data.get('student_id')
        if not student_id:
            return jsonify({"error": "Student ID required"}), 400

        driver_id = _driver_id_from_user(get_jwt_identity())
        if not driver_id:
            return jsonify({"error": "User not found"}), 404

        result = log_student_alighting(driver_id, student_id)
        if not result['success']:
            return jsonify({"error": result['error']}), 400

        return jsonify({
            "message": result['message'],
            "student_id": student_id,
            "action": "OUT"
        }), 200
    except Exception as exc:
        logger.exception("Error in driver_log_alighting")
        return jsonify({"error": str(exc)}), 500


@app.route('/driver/students-on-bus', methods=['GET'])
@require_auth
@require_role("driver")
def driver_get_students_on_bus():
    try:
        driver_id = _driver_id_from_user(get_jwt_identity())
        if not driver_id:
            return jsonify({"error": "User not found"}), 404

        students = get_students_on_bus(driver_id)
        return jsonify({"driver_id": driver_id, "students_on_bus": students, "count": len(students)}), 200
    except Exception as exc:
        logger.exception("Error in driver_get_students_on_bus")
        return jsonify({"error": str(exc)}), 500


@app.route('/driver/check-student/<student_id>', methods=['GET'])
@require_auth
@require_role("driver")
def driver_check_student(student_id):
    try:
        driver_id = _driver_id_from_user(get_jwt_identity())
        if not driver_id:
            return jsonify({"error": "User not found"}), 404

        conn = get_connection()
        driver = conn.execute(
            "SELECT bus_number FROM drivers WHERE driver_id = ?",
            (driver_id,),
        ).fetchone()
        if not driver:
            conn.close()
            return jsonify({"error": "Driver not found"}), 404

        student = conn.execute(
            "SELECT name, bus_stop, bus_number FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        conn.close()
        if not student:
            return jsonify({"error": "Student not found"}), 404

        if student["bus_number"] != driver["bus_number"]:
            return jsonify({"error": f"Student {student_id} is not assigned to your bus ({driver['bus_number']})"}), 403

        on_bus = is_student_on_bus(student_id)
        return jsonify(
            {
                "student_id": student_id,
                "name": student["name"],
                "bus_stop": student["bus_stop"],
                "on_bus": on_bus,
            }
        ), 200
    except Exception as exc:
        logger.exception("Error in driver_check_student")
        return jsonify({"error": str(exc)}), 500


@app.route('/driver/daily-summary', methods=['GET'])
@require_auth
@require_role("driver")
def driver_get_daily_summary():
    try:
        driver_id = _driver_id_from_user(get_jwt_identity())
        if not driver_id:
            return jsonify({"error": "User not found"}), 404

        date = request.args.get('date')
        summary = get_daily_summary(driver_id, date)
        return jsonify(summary), 200
    except Exception as exc:
        logger.exception("Error in driver_get_daily_summary")
        return jsonify({"error": str(exc)}), 500


@app.route('/driver/route-students', methods=['GET'])
@require_auth
@require_role("driver")
def driver_route_students():
    driver_id = _driver_id_from_user(get_jwt_identity())
    if not driver_id:
        return jsonify({"error": "User not found"}), 404

    conn = get_connection()
    try:
        driver = conn.execute(
            "SELECT bus_number FROM drivers WHERE driver_id = ?",
            (driver_id,),
        ).fetchone()
        if not driver:
            return jsonify({"error": "Driver not found"}), 404

        rows = conn.execute(
            """
            SELECT student_id, name, bus_stop, bus_stop_lat, bus_stop_lng, bus_stop_label, on_leave
            FROM students
            WHERE bus_number = ?
            ORDER BY name
            """,
            (driver["bus_number"],),
        ).fetchall()
        return jsonify([dict(r) for r in rows]), 200
    finally:
        conn.close()


# ============================================================================
# TRIPS + LOCATION INGEST
# ============================================================================

@app.route('/driver/trips/start', methods=['POST'])
@require_auth
@require_role("driver")
def start_driver_trip():
    data = request.json or {}
    trip_type = data.get("trip_type")
    if trip_type not in ("TO_SCHOOL", "TO_HOME"):
        return jsonify({"error": "trip_type must be TO_SCHOOL or TO_HOME"}), 400

    driver_id = _driver_id_from_user(get_jwt_identity())
    if not driver_id:
        return jsonify({"error": "User not found"}), 404

    conn = get_connection()
    try:
        driver = conn.execute(
            "SELECT bus_number FROM drivers WHERE driver_id = ?",
            (driver_id,),
        ).fetchone()
        if not driver:
            return jsonify({"error": "Driver not found"}), 404

        active = conn.execute(
            "SELECT * FROM bus_trips WHERE driver_id = ? AND status = 'ACTIVE'",
            (driver_id,),
        ).fetchone()
        if active:
            return jsonify({"error": "Driver already has an active trip", "trip": dict(active)}), 400

        now = _utc_iso()
        service_date = datetime.now().strftime("%Y-%m-%d")
        cur = conn.execute(
            """
            INSERT INTO bus_trips (driver_id, bus_number, trip_type, status, started_at, service_date)
            VALUES (?, ?, ?, 'ACTIVE', ?, ?)
            """,
            (driver_id, driver["bus_number"], trip_type, now, service_date),
        )
        conn.commit()
        trip_id = cur.lastrowid

        row = conn.execute("SELECT * FROM bus_trips WHERE id = ?", (trip_id,)).fetchone()
        return jsonify({"message": "Trip started", "trip": dict(row)}), 201
    finally:
        conn.close()


@app.route('/driver/trips/end', methods=['POST'])
@require_auth
@require_role("driver")
def end_driver_trip():
    driver_id = _driver_id_from_user(get_jwt_identity())
    if not driver_id:
        return jsonify({"error": "User not found"}), 404

    conn = get_connection()
    try:
        trip = conn.execute(
            "SELECT * FROM bus_trips WHERE driver_id = ? AND status = 'ACTIVE' ORDER BY started_at DESC LIMIT 1",
            (driver_id,),
        ).fetchone()
        if not trip:
            return jsonify({"error": "No active trip"}), 404

        conn.execute(
            "UPDATE bus_trips SET status = 'COMPLETED', ended_at = ? WHERE id = ?",
            (_utc_iso(), trip["id"]),
        )
        conn.commit()

        updated = conn.execute("SELECT * FROM bus_trips WHERE id = ?", (trip["id"],)).fetchone()
        return jsonify({"message": "Trip ended", "trip": dict(updated)}), 200
    finally:
        conn.close()


@app.route('/driver/trips/current', methods=['GET'])
@require_auth
@require_role("driver")
def current_driver_trip():
    driver_id = _driver_id_from_user(get_jwt_identity())
    if not driver_id:
        return jsonify({"error": "User not found"}), 404

    conn = get_connection()
    try:
        trip = conn.execute(
            "SELECT * FROM bus_trips WHERE driver_id = ? AND status = 'ACTIVE' ORDER BY started_at DESC LIMIT 1",
            (driver_id,),
        ).fetchone()
        if not trip:
            return jsonify({"trip": None}), 200

        location = conn.execute(
            """
            SELECT lat, lng, speed, heading, COALESCE(timestamp, recorded_at) AS ts, source
            FROM bus_locations
            WHERE trip_id = ?
            ORDER BY COALESCE(timestamp, recorded_at) DESC
            LIMIT 1
            """,
            (trip["id"],),
        ).fetchone()

        return jsonify({
            "trip": dict(trip),
            "last_location": dict(location) if location else None,
        }), 200
    finally:
        conn.close()


@app.route('/driver/location', methods=['POST'])
@require_auth
@require_role("driver")
def ingest_driver_location():
    data = request.json or {}
    lat = data.get("lat")
    lng = data.get("lng")
    speed = data.get("speed")
    heading = data.get("heading")
    ts = data.get("timestamp") or _utc_iso()

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400

    driver_id = _driver_id_from_user(get_jwt_identity())
    if not driver_id:
        return jsonify({"error": "User not found"}), 404

    conn = get_connection()
    try:
        trip = conn.execute(
            "SELECT * FROM bus_trips WHERE driver_id = ? AND status = 'ACTIVE' ORDER BY started_at DESC LIMIT 1",
            (driver_id,),
        ).fetchone()
        if not trip:
            return jsonify({"error": "No active trip. Start a trip first."}), 400

        conn.execute(
            """
            INSERT INTO bus_locations (
                trip_id, driver_id, bus_number, source,
                lat, lng, speed, heading, recorded_at, timestamp
            )
            VALUES (?, ?, ?, 'DRIVER_PHONE', ?, ?, ?, ?, ?, ?)
            """,
            (
                trip["id"],
                trip["driver_id"],
                trip["bus_number"],
                float(lat),
                float(lng),
                speed,
                heading,
                ts,
                ts,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    alerts = evaluate_not_boarded_alerts(trip["id"], float(lat), float(lng))
    return jsonify({"status": "ok", "trip_id": trip["id"], "alerts_triggered": alerts}), 200


@app.route('/gps/devices/location', methods=['POST'])
def ingest_gps_device_location():
    secret = request.headers.get("X-GPS-DEVICE-SECRET", "")
    expected = os.getenv("GPS_DEVICE_SHARED_SECRET", "")
    if not expected:
        return jsonify({"error": "GPS device secret not configured"}), 500
    if secret != expected:
        return jsonify({"error": "Unauthorized device"}), 401

    data = request.json or {}
    bus_number = data.get("bus_number")
    lat = data.get("lat")
    lng = data.get("lng")
    speed = data.get("speed")
    heading = data.get("heading")
    ts = data.get("timestamp") or _utc_iso()

    if not bus_number or lat is None or lng is None:
        return jsonify({"error": "bus_number, lat, lng are required"}), 400

    conn = get_connection()
    try:
        trip = conn.execute(
            """
            SELECT * FROM bus_trips
            WHERE bus_number = ? AND status = 'ACTIVE'
            ORDER BY started_at DESC LIMIT 1
            """,
            (bus_number,),
        ).fetchone()
        if not trip:
            return jsonify({"error": "No active trip for this bus"}), 404

        conn.execute(
            """
            INSERT INTO bus_locations (
                trip_id, driver_id, bus_number, source,
                lat, lng, speed, heading, recorded_at, timestamp
            )
            VALUES (?, ?, ?, 'GPS_DEVICE', ?, ?, ?, ?, ?, ?)
            """,
            (
                trip["id"],
                trip["driver_id"],
                trip["bus_number"],
                float(lat),
                float(lng),
                speed,
                heading,
                ts,
                ts,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    alerts = evaluate_not_boarded_alerts(trip["id"], float(lat), float(lng))
    return jsonify({"status": "ok", "trip_id": trip["id"], "alerts_triggered": alerts}), 200


# ============================================================================
# NOTIFICATIONS
# ============================================================================

@app.route('/admin/notifications', methods=['GET'])
@require_auth
@require_role("admin")
def admin_notifications():
    status = request.args.get("status")
    event_type = request.args.get("event_type")
    limit = min(int(request.args.get("limit", 200)), 500)

    query = """
        SELECT n.*, s.name AS student_name
        FROM notifications n
        LEFT JOIN students s ON s.student_id = n.student_id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND n.status = ?"
        params.append(status)
    if event_type:
        query += " AND n.event_type = ?"
        params.append(event_type)
    query += " ORDER BY n.created_at DESC LIMIT ?"
    params.append(limit)

    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows]), 200
    finally:
        conn.close()


@app.route('/driver/notifications/recent', methods=['GET'])
@require_auth
@require_role("driver")
def driver_notifications_recent():
    driver_id = _driver_id_from_user(get_jwt_identity())
    if not driver_id:
        return jsonify({"error": "User not found"}), 404

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT n.*, s.name AS student_name
            FROM notifications n
            JOIN bus_trips t ON t.id = n.trip_id
            LEFT JOIN students s ON s.student_id = n.student_id
            WHERE t.driver_id = ?
            ORDER BY n.created_at DESC
            LIMIT 100
            """,
            (driver_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows]), 200
    finally:
        conn.close()


@app.route('/student/notifications', methods=['GET'])
@require_auth
def student_notifications():
    claims = get_jwt()
    user_id = get_jwt_identity()
    role = claims.get("role")

    requested_student_id = request.args.get("student_id")

    conn = get_connection()
    try:
        if role == "student":
            user = conn.execute(
                "SELECT student_id FROM users WHERE id = ?",
                (str(user_id),),
            ).fetchone()
            if not user:
                return jsonify({"error": "User not found"}), 404
            student_id = user["student_id"]
        elif role == "admin":
            student_id = requested_student_id
            if not student_id:
                return jsonify({"error": "student_id query param required for admin"}), 400
        else:
            return jsonify({"error": "Only student/admin can access this endpoint"}), 403

        rows = conn.execute(
            """
            SELECT * FROM notifications
            WHERE student_id = ?
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (student_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows]), 200
    finally:
        conn.close()


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    parser = argparse.ArgumentParser(description="Bus attendance backend")
    parser.add_argument("--host", default=os.environ.get("BACKEND_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("BACKEND_PORT", "5000")))
    parser.add_argument("--debug", action="store_true", default=os.environ.get("BACKEND_DEBUG", "1") == "1")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)
