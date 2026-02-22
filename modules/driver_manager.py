"""
Driver Management Module
Handles driver operations: registration, student logging (boarding/alighting), bus tracking
"""

import sqlite3
from datetime import datetime, timedelta
from database.db import get_connection

# ============================================================================
# DRIVER MANAGEMENT
# ============================================================================

def create_driver(driver_id, name, bus_number, phone=None, license_number=None):
    """
    Create a new driver record
    
    Args:
        driver_id: Unique identifier (e.g., 'DRV001')
        name: Driver's full name
        bus_number: Bus registration number (e.g., 'KA-01-AB-1234')
        phone: Contact number
        license_number: DL number
    
    Returns:
        dict with success status or error message
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO drivers (driver_id, name, bus_number, phone, license_number)
            VALUES (?, ?, ?, ?, ?)
        """, (driver_id, name, bus_number, phone, license_number))
        
        conn.commit()
        return {"success": True, "message": "Driver created successfully"}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Driver ID already exists"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_driver(driver_id):
    """
    Get driver information
    
    Args:
        driver_id: Driver's unique ID
    
    Returns:
        dict with driver details or None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT driver_id, name, bus_number, phone, license_number, created_at
            FROM drivers WHERE driver_id = ?
        """, (driver_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                "driver_id": row[0],
                "name": row[1],
                "bus_number": row[2],
                "phone": row[3],
                "license_number": row[4],
                "created_at": row[5]
            }
        return None
    finally:
        conn.close()


def get_all_drivers():
    """Get a list of all drivers"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT driver_id, name, bus_number, phone, license_number
            FROM drivers ORDER BY name
        """)
        
        drivers = []
        for row in cursor.fetchall():
            drivers.append({
                "driver_id": row[0],
                "name": row[1],
                "bus_number": row[2],
                "phone": row[3],
                "license_number": row[4]
            })
        return drivers
    finally:
        conn.close()


# ============================================================================
# STUDENT LOGGING (BOARDING/ALIGHTING)
# ============================================================================

def log_student_boarding(driver_id, student_id):
    """
    Log a student boarding the bus
    Verifies student is assigned to driver's bus
    
    Args:
        driver_id: Driver's ID
        student_id: Student's ID
    
    Returns:
        dict with success status
    """
    # Check if student already on bus
    if is_student_on_bus(student_id):
        return {"success": False, "error": "Student already logged as on bus"}
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verify student is assigned to this driver's bus
        cursor.execute("""
            SELECT s.bus_number, d.bus_number FROM students s
            JOIN drivers d ON d.driver_id = ?
            WHERE s.student_id = ?
        """, (driver_id, student_id))
        
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": "Student not found"}
        
        if row[0] != row[1]:
            return {"success": False, "error": f"Student is not assigned to your bus"}
        
        cursor.execute("""
            INSERT INTO driver_logs (driver_id, student_id, action)
            VALUES (?, ?, 'IN')
        """, (driver_id, student_id))
        
        conn.commit()
        return {"success": True, "message": f"Student {student_id} boarded"}
    except sqlite3.IntegrityError as e:
        return {"success": False, "error": "Student or Driver not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def log_student_alighting(driver_id, student_id):
    """
    Log a student alighting from the bus
    Verifies student is assigned to driver's bus
    
    Args:
        driver_id: Driver's ID
        student_id: Student's ID
    
    Returns:
        dict with success status
    """
    # Check if student is on bus
    if not is_student_on_bus(student_id):
        return {"success": False, "error": "Student not logged as on bus"}
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verify student is assigned to this driver's bus
        cursor.execute("""
            SELECT s.bus_number, d.bus_number FROM students s
            JOIN drivers d ON d.driver_id = ?
            WHERE s.student_id = ?
        """, (driver_id, student_id))
        
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": "Student not found"}
        
        if row[0] != row[1]:
            return {"success": False, "error": f"Student is not assigned to your bus"}
        
        cursor.execute("""
            INSERT INTO driver_logs (driver_id, student_id, action)
            VALUES (?, ?, 'OUT')
        """, (driver_id, student_id))
        
        conn.commit()
        return {"success": True, "message": f"Student {student_id} alighted"}
    except sqlite3.IntegrityError as e:
        return {"success": False, "error": "Student or Driver not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def is_student_on_bus(student_id):
    """
    Check if a student is currently on the bus
    (Last log entry was 'IN', not 'OUT')
    
    Args:
        student_id: Student's ID
    
    Returns:
        bool: True if student is on bus, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT action FROM driver_logs
            WHERE student_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (student_id,))
        
        row = cursor.fetchone()
        if row and row[0] == 'IN':
            return True
        return False
    finally:
        conn.close()


def get_students_on_bus(driver_id):
    """
    Get list of students currently on the bus (assigned to driver's bus)
    
    Args:
        driver_id: Driver's ID
    
    Returns:
        list of dicts with student info
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all students assigned to this driver's bus whose last log is 'IN'
        cursor.execute("""
            SELECT DISTINCT dl.student_id, s.name, s.bus_stop
            FROM driver_logs dl
            JOIN students s ON dl.student_id = s.student_id
            JOIN drivers d ON d.driver_id = dl.driver_id
            WHERE dl.driver_id = ? AND s.bus_number = d.bus_number AND
                  dl.student_id IN (
                      SELECT student_id FROM driver_logs
                      WHERE action = 'IN'
                      GROUP BY student_id
                      HAVING MAX(timestamp) = (
                          SELECT MAX(timestamp) FROM driver_logs
                          WHERE student_id = driver_logs.student_id
                      )
                  )
            ORDER BY s.name
        """, (driver_id,))
        
        students = []
        for row in cursor.fetchall():
            students.append({
                "student_id": row[0],
                "name": row[1],
                "bus_stop": row[2]
            })
        return students
    finally:
        conn.close()


def get_recent_logs(driver_id, limit=20):
    """
    Get recent boarding/alighting logs for a driver (only for students on their bus)
    
    Args:
        driver_id: Driver's ID
        limit: Number of records to return
    
    Returns:
        list of dicts with log details
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT dl.student_id, s.name, dl.action, dl.timestamp
            FROM driver_logs dl
            JOIN students s ON dl.student_id = s.student_id
            JOIN drivers d ON d.driver_id = dl.driver_id
            WHERE dl.driver_id = ? AND s.bus_number = d.bus_number
            ORDER BY dl.timestamp DESC
            LIMIT ?
        """, (driver_id, limit))
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                "student_id": row[0],
                "name": row[1],
                "action": row[2],
                "timestamp": row[3]
            })
        return logs
    finally:
        conn.close()


# ============================================================================
# STATISTICS
# ============================================================================

def get_driver_stats(driver_id):
    """
    Get statistics for a driver's current shift (only for their bus students)
    
    Args:
        driver_id: Driver's ID
    
    Returns:
        dict with statistics
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get count of students boarded and alighted (only for this bus)
        cursor.execute("""
            SELECT action, COUNT(*) FROM driver_logs dl
            JOIN students s ON dl.student_id = s.student_id
            JOIN drivers d ON d.driver_id = dl.driver_id
            WHERE dl.driver_id = ? AND s.bus_number = d.bus_number
            AND DATE(dl.timestamp) = DATE('now')
            GROUP BY action
        """, (driver_id,))
        
        stats = {"boarded": 0, "alighted": 0, "on_bus": 0}
        for row in cursor.fetchall():
            if row[0] == 'IN':
                stats["boarded"] = row[1]
            elif row[0] == 'OUT':
                stats["alighted"] = row[1]
        
        stats["on_bus"] = len(get_students_on_bus(driver_id))
        
        return stats
    finally:
        conn.close()


def get_daily_summary(driver_id, date=None):
    """
    Get summary of the day's activity (only for their bus students)
    
    Args:
        driver_id: Driver's ID
        date: Date in format 'YYYY-MM-DD' (default: today)
    
    Returns:
        dict with daily summary
    """
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all logs for the day (only for this bus)
        cursor.execute("""
            SELECT dl.student_id, dl.action, dl.timestamp FROM driver_logs dl
            JOIN students s ON dl.student_id = s.student_id
            JOIN drivers d ON d.driver_id = dl.driver_id
            WHERE dl.driver_id = ? AND s.bus_number = d.bus_number AND DATE(dl.timestamp) = ?
            ORDER BY dl.timestamp
        """, (driver_id, date))
        
        logs = cursor.fetchall()
        boarded = sum(1 for log in logs if log[1] == 'IN')
        alighted = sum(1 for log in logs if log[1] == 'OUT')
        
        return {
            "date": date,
            "total_boarded": boarded,
            "total_alighted": alighted,
            "logs_count": len(logs)
        }
    finally:
        conn.close()
