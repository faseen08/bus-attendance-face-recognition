"""
Bus location helper logic.
"""

import math
from datetime import datetime


def haversine_meters(lat1, lng1, lat2, lng2):
    """Great-circle distance between 2 points in meters."""
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def evaluate_stop_pass(conn, trip_id, student_id, distance_m, stop_radius_m=150):
    """
    Update per-trip student location state and detect when bus has passed stop.

    Rule:
    1. Mark reached_stop when bus gets inside stop radius.
    2. Mark passed_stop when bus had reached stop earlier and now moves clearly away.
    """
    now = datetime.utcnow().isoformat(timespec="seconds")
    row = conn.execute(
        """
        SELECT last_distance_m, min_distance_m, reached_stop, passed_stop
        FROM trip_student_state
        WHERE trip_id = ? AND student_id = ?
        """,
        (trip_id, student_id),
    ).fetchone()

    if row:
        last_distance = row["last_distance_m"]
        min_distance = row["min_distance_m"] if row["min_distance_m"] is not None else distance_m
        reached_stop = bool(row["reached_stop"])
        passed_stop = bool(row["passed_stop"])
    else:
        last_distance = None
        min_distance = distance_m
        reached_stop = False
        passed_stop = False

    min_distance = min(min_distance, distance_m)
    if distance_m <= stop_radius_m:
        reached_stop = True

    moving_away = (
        last_distance is not None
        and distance_m > stop_radius_m
        and distance_m > (last_distance + 8.0)
    )
    if reached_stop and moving_away:
        passed_stop = True

    conn.execute(
        """
        INSERT INTO trip_student_state (
            trip_id, student_id, last_distance_m, min_distance_m,
            reached_stop, passed_stop, last_evaluated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(trip_id, student_id) DO UPDATE SET
            last_distance_m = excluded.last_distance_m,
            min_distance_m = excluded.min_distance_m,
            reached_stop = excluded.reached_stop,
            passed_stop = excluded.passed_stop,
            last_evaluated_at = excluded.last_evaluated_at
        """,
        (
            trip_id,
            student_id,
            float(distance_m),
            float(min_distance),
            1 if reached_stop else 0,
            1 if passed_stop else 0,
            now,
        ),
    )

    return {
        "distance_m": round(distance_m, 2),
        "reached_stop": reached_stop,
        "passed_stop": passed_stop,
    }
