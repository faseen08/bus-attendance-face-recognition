"""
Parent alert service.
Sends SMS via Twilio when available and always writes audit rows.
"""

import os
from datetime import datetime

from database.db import get_connection
from modules.bus_location import haversine_meters, evaluate_stop_pass


def _get_setting(conn, key, default):
    row = conn.execute(
        f"SELECT {key} FROM notification_settings WHERE id = 1"
    ).fetchone()
    if not row or row[key] is None:
        return default
    return row[key]


def _get_twilio_client():
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        return None
    try:
        from twilio.rest import Client
        return Client(sid, token)
    except Exception:
        return None


def _send_sms(phone, body):
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not from_number:
        return {"status": "SKIPPED", "sid": None, "error": "TWILIO_FROM_NUMBER is not set"}

    client = _get_twilio_client()
    if not client:
        return {"status": "SKIPPED", "sid": None, "error": "Twilio is not configured"}

    try:
        msg = client.messages.create(
            to=phone,
            from_=from_number,
            body=body,
        )
        return {"status": "SENT", "sid": msg.sid, "error": None}
    except Exception as exc:
        return {"status": "FAILED", "sid": None, "error": str(exc)}


def _already_notified(conn, student_id, trip_id, event_type):
    row = conn.execute(
        """
        SELECT id FROM notifications
        WHERE student_id = ? AND trip_id = ? AND event_type = ?
        """,
        (student_id, trip_id, event_type),
    ).fetchone()
    return bool(row)


def _save_notification(conn, student_id, trip_id, trip_type, event_type, send_result):
    conn.execute(
        """
        INSERT OR IGNORE INTO notifications (
            student_id, trip_id, trip_type, event_type, status, provider_sid, error_message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            trip_id,
            trip_type,
            event_type,
            send_result["status"],
            send_result.get("sid"),
            send_result.get("error"),
            datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )


def _has_boarded_in_trip(conn, student_id, trip):
    row = conn.execute(
        """
        SELECT 1
        FROM driver_logs
        WHERE student_id = ?
          AND driver_id = ?
          AND action = 'IN'
          AND timestamp >= ?
          AND (? IS NULL OR timestamp <= ?)
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (
            student_id,
            trip["driver_id"],
            trip["started_at"],
            trip["ended_at"],
            trip["ended_at"],
        ),
    ).fetchone()
    return bool(row)


def send_boarded_alert_for_student(student_id, driver_id):
    """Send BOARDED alert for active trip if not sent before."""
    conn = get_connection()
    try:
        trip = conn.execute(
            """
            SELECT id, trip_type, driver_id, bus_number, started_at, ended_at
            FROM bus_trips
            WHERE driver_id = ? AND status = 'ACTIVE'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (driver_id,),
        ).fetchone()
        if not trip:
            return {"status": "SKIPPED", "reason": "No active trip"}

        student = conn.execute(
            """
            SELECT student_id, name, parent_phone, alerts_enabled
            FROM students
            WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
        if not student:
            return {"status": "SKIPPED", "reason": "Student not found"}
        if not student["alerts_enabled"] or not student["parent_phone"]:
            return {"status": "SKIPPED", "reason": "Alerts disabled or parent phone missing"}
        if _already_notified(conn, student_id, trip["id"], "BOARDED"):
            return {"status": "SKIPPED", "reason": "Already sent"}

        template = _get_setting(
            conn,
            "boarded_template",
            "Bus update: {student_name} boarded bus {bus_number}.",
        )
        text = template.format(
            student_name=student["name"] or student["student_id"],
            bus_number=trip["bus_number"],
        )
        send_result = _send_sms(student["parent_phone"], text)
        _save_notification(conn, student_id, trip["id"], trip["trip_type"], "BOARDED", send_result)
        conn.commit()
        return {"status": send_result["status"], "trip_id": trip["id"]}
    finally:
        conn.close()


def evaluate_not_boarded_alerts(trip_id, lat, lng):
    """
    Evaluate stop-pass logic for all students on this trip and send NOT_BOARDED once.
    """
    conn = get_connection()
    sent = []
    try:
        trip = conn.execute(
            """
            SELECT id, driver_id, bus_number, trip_type, started_at, ended_at
            FROM bus_trips
            WHERE id = ?
            """,
            (trip_id,),
        ).fetchone()
        if not trip:
            return sent

        radius = int(_get_setting(conn, "stop_radius_meters", 150))
        students = conn.execute(
            """
            SELECT student_id, name, parent_phone, alerts_enabled, on_leave,
                   bus_stop_lat, bus_stop_lng
            FROM students
            WHERE bus_number = ?
              AND bus_stop_lat IS NOT NULL
              AND bus_stop_lng IS NOT NULL
            """,
            (trip["bus_number"],),
        ).fetchall()

        missed_template = _get_setting(
            conn,
            "missed_template",
            "Alert: {student_name} has not boarded bus {bus_number} after the stop was passed.",
        )

        for student in students:
            student_id = student["student_id"]
            if student["on_leave"] == 1:
                continue
            if not student["alerts_enabled"] or not student["parent_phone"]:
                continue
            if _already_notified(conn, student_id, trip["id"], "NOT_BOARDED"):
                continue
            if _has_boarded_in_trip(conn, student_id, trip):
                continue

            distance_m = haversine_meters(
                lat,
                lng,
                float(student["bus_stop_lat"]),
                float(student["bus_stop_lng"]),
            )
            progress = evaluate_stop_pass(conn, trip["id"], student_id, distance_m, radius)
            if not progress["passed_stop"]:
                continue

            text = missed_template.format(
                student_name=student["name"] or student_id,
                bus_number=trip["bus_number"],
            )
            send_result = _send_sms(student["parent_phone"], text)
            _save_notification(
                conn,
                student_id,
                trip["id"],
                trip["trip_type"],
                "NOT_BOARDED",
                send_result,
            )
            sent.append(
                {
                    "student_id": student_id,
                    "status": send_result["status"],
                    "distance_m": progress["distance_m"],
                }
            )

        conn.commit()
        return sent
    finally:
        conn.close()
