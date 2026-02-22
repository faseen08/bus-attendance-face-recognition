from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import os
import logging

from database.db import init_db
from database.db import get_connection
from database.attendance_db import mark_attendance_db
from werkzeug.utils import secure_filename
from flask import send_from_directory
from backend.auth import (
    authenticate_user, 
    generate_token, 
    create_user,
    require_auth
)
from modules.driver_manager import (
    create_driver,
    get_driver,
    get_all_drivers,
    log_student_boarding,
    log_student_alighting,
    is_student_on_bus,
    get_students_on_bus,
    get_recent_logs,
    get_driver_stats,
    get_daily_summary
)

app = Flask(__name__)
CORS(app)

# ============================================================================
# JWT CONFIGURATION
# ============================================================================
# This sets up JWT authentication for our app
app.config['JWT_SECRET_KEY'] = 'your-secret-key-change-in-production'
jwt = JWTManager(app)

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

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.route("/login", methods=["POST"])
def login():
    """
    Login endpoint - authenticates user with username and password.
    
    Request body:
    {
        "id": "username_or_student_id",
        "password": "password",
        "role": "admin" or "student"
    }
    
    Returns:
    {
        "token": "JWT_TOKEN",
        "user": {
            "id": user_id,
            "username": username,
            "role": role,
            "student_id": student_id (if student)
        }
    }
    """
    try:
        data = request.json
        username = data.get("id")  # Frontend sends "id" as username
        password = data.get("password")
        role = data.get("role", "student")
        
        # Validate input
        if not username or not password:
            return jsonify({"error": "Missing username or password"}), 400
        
        # Try to authenticate user
        user = authenticate_user(username, password)
        
        if not user:
            return jsonify({"error": "Invalid username or password"}), 401
        
        # Check if role matches
        if user['role'] != role:
            return jsonify({"error": f"This account is not a {role}"}), 403
        
        # Generate JWT token
        token = generate_token(user['id'], user['username'], user['role'])
        
        return jsonify({
            "token": token,
            "user": user
        }), 200
    
    except Exception as e:
        logger.exception("Login error")
        return jsonify({"error": "Login failed"}), 500


@app.route("/register", methods=["POST"])
def register():
    """
    Register endpoint - creates a new user account.
    
    Request body:
    {
        "username": "username",
        "password": "password",
        "role": "student" or "admin",
        "student_id": "student_id" (required if role is student)
    }
    
    Returns:
    {
        "message": "User registered successfully",
        "token": "JWT_TOKEN"
    }
    """
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")
        role = data.get("role", "student")
        student_id = data.get("student_id")
        
        # Validate input
        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400
        
        if role == "student" and not student_id:
            return jsonify({"error": "Student ID required for student role"}), 400
        
        # Create user
        result = create_user(username, password, role, student_id)
        
        if not result['success']:
            return jsonify({"error": result['error']}), 400
        
        # Generate token for auto-login after registration
        user = authenticate_user(username, password)
        token = generate_token(user['id'], user['username'], user['role'])
        
        return jsonify({
            "message": "User registered successfully",
            "token": token,
            "user": user
        }), 201
    
    except Exception as e:
        logger.exception("Registration error")
        return jsonify({"error": "Registration failed"}), 500


@app.route("/verify-token", methods=["GET"])
@require_auth
def verify_token():
    """
    Verify that a token is valid.
    Protected endpoint - requires valid JWT token.
    """
    from flask_jwt_extended import get_jwt_identity, get_jwt
    user_id = get_jwt_identity()
    claims = get_jwt()
    
    return jsonify({
        "valid": True,
        "user_id": user_id,
        "role": claims.get("role")
    }), 200


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
@require_auth
def add_student():
    student_id = request.form.get("student_id")
    name = request.form.get("name") # Added name
    bus_number = request.form.get("bus_number")  # Added bus_number
    bus_stop = request.form.get("bus_stop") # Added bus_stop
    photo = request.files.get("photo")

    if not student_id or not photo or not bus_number:
        return jsonify({"error": "missing data"}), 400

    folder = os.path.join(UPLOAD_DIR, student_id)
    os.makedirs(folder, exist_ok=True)

    filename = secure_filename(photo.filename)
    photo_path = os.path.join(folder, filename)
    photo.save(photo_path)

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO students (student_id, name, bus_number, bus_stop, photo_path) VALUES (?, ?, ?, ?, ?)",
            (student_id, name if name else student_id, bus_number, bus_stop, photo_path)
        )
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"status": "student added"})

@app.route("/students/toggle_leave", methods=["POST"])
def toggle_leave():
    """
    Toggle leave status for a student.
    Note: This endpoint is accessible without authentication to allow quick leave requests
    from leave.html, but in production you may want to add @require_auth
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
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

        return jsonify({"status": "Success", "on_leave": new_status}), 200
    
    except Exception as e:
        logger.exception("Error in toggle_leave")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# DRIVER ENDPOINTS
# ============================================================================

@app.route('/driver/dashboard', methods=['GET'])
@require_auth
def driver_dashboard():
    """
    Get driver dashboard data (driver info, stats, students on bus)
    Requires: JWT token with role='driver'
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        
        user_id = int(get_jwt_identity())
        conn = get_connection()
        user = conn.execute(
            "SELECT username, student_id FROM users WHERE id = ?", 
            (user_id,)
        ).fetchone()
        conn.close()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        driver_id = user[1]  # student_id linked to driver
        driver_info = get_driver(driver_id)
        
        if not driver_info:
            return jsonify({"error": "Driver not found"}), 404
        
        stats = get_driver_stats(driver_id)
        
        return jsonify({
            "driver": driver_info,
            "statistics": stats
        }), 200
    
    except Exception as e:
        logger.exception("Error in driver_dashboard")
        return jsonify({"error": str(e)}), 500


@app.route('/driver/log-boarding', methods=['POST'])
@require_auth
def driver_log_boarding():
    """
    Log a student boarding the bus
    Request body: { "student_id": "ekc23cs001" }
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = request.get_json()
        if not data or not data.get('student_id'):
            return jsonify({"error": "Student ID required"}), 400
        
        student_id = data['student_id']
        
        # Get driver_id from user's linked student_id (driver_id)
        user_id = int(get_jwt_identity())
        conn = get_connection()
        user = conn.execute(
            "SELECT student_id FROM users WHERE id = ?", 
            (user_id,)
        ).fetchone()
        conn.close()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        driver_id = user[0]
        result = log_student_boarding(driver_id, student_id)
        
        if not result['success']:
            return jsonify({"error": result['error']}), 400
        
        return jsonify({
            "message": result['message'],
            "student_id": student_id,
            "action": "IN"
        }), 200
    
    except Exception as e:
        logger.exception("Error in driver_log_boarding")
        return jsonify({"error": str(e)}), 500


@app.route('/driver/log-alighting', methods=['POST'])
@require_auth
def driver_log_alighting():
    """
    Log a student alighting from the bus
    Request body: { "student_id": "ekc23cs001" }
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = request.get_json()
        if not data or not data.get('student_id'):
            return jsonify({"error": "Student ID required"}), 400
        
        student_id = data['student_id']
        
        # Get driver_id from user's linked student_id (driver_id)
        user_id = int(get_jwt_identity())
        conn = get_connection()
        user = conn.execute(
            "SELECT student_id FROM users WHERE id = ?", 
            (user_id,)
        ).fetchone()
        conn.close()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        driver_id = user[0]
        result = log_student_alighting(driver_id, student_id)
        
        if not result['success']:
            return jsonify({"error": result['error']}), 400
        
        return jsonify({
            "message": result['message'],
            "student_id": student_id,
            "action": "OUT"
        }), 200
    
    except Exception as e:
        logger.exception("Error in driver_log_alighting")
        return jsonify({"error": str(e)}), 500


@app.route('/driver/students-on-bus', methods=['GET'])
@require_auth
def driver_get_students_on_bus():
    """
    Get list of students currently on the bus
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        
        user_id = get_jwt_identity()
        conn = get_connection()
        user = conn.execute(
            "SELECT student_id FROM users WHERE id = ?", 
            (user_id,)
        ).fetchone()
        conn.close()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        driver_id = user[0]
        students = get_students_on_bus(driver_id)
        
        return jsonify({
            "driver_id": driver_id,
            "students_on_bus": students,
            "count": len(students)
        }), 200
    
    except Exception as e:
        logger.exception("Error in driver_get_students_on_bus")
        return jsonify({"error": str(e)}), 500


@app.route('/driver/check-student/<student_id>', methods=['GET'])
@require_auth
def driver_check_student(student_id):
    """
    Check if a student is currently on the bus
    Also verifies the student is assigned to the driver's bus
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        
        # Get driver_id from JWT
        user_id = int(get_jwt_identity())
        conn = get_connection()
        user = conn.execute(
            "SELECT student_id FROM users WHERE id = ?", 
            (user_id,)
        ).fetchone()
        
        if not user:
            conn.close()
            return jsonify({"error": "User not found"}), 404
        
        driver_id = user[0]
        
        # Get driver's bus number
        driver = conn.execute(
            "SELECT bus_number FROM drivers WHERE driver_id = ?",
            (driver_id,)
        ).fetchone()
        
        if not driver:
            conn.close()
            return jsonify({"error": "Driver not found"}), 404
        
        driver_bus_number = driver[0]
        
        # Get student info
        student = conn.execute(
            "SELECT name, bus_stop, bus_number FROM students WHERE student_id = ?",
            (student_id,)
        ).fetchone()
        conn.close()
        
        if not student:
            return jsonify({"error": "Student not found"}), 404
        
        # Check if student belongs to this driver's bus
        if student[2] != driver_bus_number:
            return jsonify({"error": f"Student {student_id} is not assigned to your bus ({driver_bus_number})"}), 403
        
        on_bus = is_student_on_bus(student_id)
        
        return jsonify({
            "student_id": student_id,
            "name": student[0],
            "bus_stop": student[1],
            "on_bus": on_bus
        }), 200
    
    except Exception as e:
        logger.exception("Error in driver_check_student")
        return jsonify({"error": str(e)}), 500


@app.route('/driver/daily-summary', methods=['GET'])
@require_auth
def driver_get_daily_summary():
    """
    Get summary of the day's activity
    Optional query param: date (YYYY-MM-DD)
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        
        user_id = int(get_jwt_identity())
        conn = get_connection()
        user = conn.execute(
            "SELECT student_id FROM users WHERE id = ?", 
            (user_id,)
        ).fetchone()
        conn.close()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        driver_id = user[0]
        date = request.args.get('date')
        summary = get_daily_summary(driver_id, date)
        
        return jsonify(summary), 200
    
    except Exception as e:
        logger.exception("Error in driver_get_daily_summary")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Ensure DB schema exists and seed students from disk (helpful for development)
    try:
        init_db()
    except Exception:
        # init_db may be no-op if DB already initialized
        pass


    seed_students_from_disk()


    # Debug helper: list all registered routes (development only)
    @app.route('/debug/routes')
    def debug_routes():
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'rule': rule.rule,
                'methods': sorted(list(rule.methods - set(['HEAD', 'OPTIONS'])))
            })
        return jsonify({'routes': routes})

    app.run(debug=True)
