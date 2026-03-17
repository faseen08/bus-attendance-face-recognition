import os
import time
from typing import List, Optional, Tuple

# Force Qt to use X11 when running on Xorg. This avoids the Wayland plugin error.
if "QT_QPA_PLATFORM" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "xcb"

import cv2
import numpy as np

from face_engine.face_model import FaceModel
from face_engine.face_recognize import load_known_faces
from modules.attendance_manager import mark_attendance


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDENTS_DIR = os.path.join(BASE_DIR, "data", "students")

# Matching thresholds (tune for your camera/environment)
SIMILARITY_THRESHOLD = 0.45
AMBIGUITY_MARGIN = 0.05

# Runtime behavior
FRAME_SCALE = 0.5
ATTENDANCE_COOLDOWN_SEC = 10
DETECT_EVERY_N_FRAMES = 2

last_seen = {}


def _match_embedding(
    embedding: np.ndarray,
    known_matrix: Optional[np.ndarray],
    known_ids: List[str],
) -> Tuple[str, Optional[float]]:
    """
    Returns (best_name, best_score) or ("Unknown", best_score/None).
    Uses cosine similarity with a "clear winner" margin to reduce false matches.
    """
    if known_matrix is None or known_matrix.size == 0:
        return "Unknown", None

    emb = np.asarray(embedding, dtype=np.float32)
    emb = emb / (np.linalg.norm(emb) + 1e-8)
    similarities = known_matrix @ emb
    best_idx = int(np.argmax(similarities))
    best_score = float(similarities[best_idx])
    second_score = (
        float(np.partition(similarities, -2)[-2])
        if len(similarities) > 1
        else -1.0
    )

    strong_match = best_score >= SIMILARITY_THRESHOLD
    clear_winner = (best_score - second_score) >= AMBIGUITY_MARGIN

    if strong_match and clear_winner:
        return known_ids[best_idx], best_score
    return "Unknown", best_score


def capture_face_image(save_path: str) -> bool:
    """
    Live preview with bounding boxes; press S to save the frame, Q to quit.
    """
    face_model = FaceModel()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Camera not accessible")
        return False

    print("Press S to save, Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        detections = face_model.detect_and_embed(frame)
        for item in detections:
            left, top, right, bottom = item["bbox"]
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

        cv2.imshow("Capture Face", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("s"):
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            cv2.imwrite(save_path, frame)
            print("Image saved:", save_path)
            break

        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    return True


def real_time_face_recognition() -> None:
    face_model = FaceModel()
    known_encodings, known_ids = load_known_faces(STUDENTS_DIR, face_model=face_model)
    known_matrix = (
        np.asarray(known_encodings, dtype=np.float32) if known_encodings else None
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Camera not accessible")
        return

    print("Press Q to quit")

    frame_count = 0
    last_detections = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Resize frame for performance
        small_frame = cv2.resize(frame, (0, 0), fx=FRAME_SCALE, fy=FRAME_SCALE)
        if frame_count % DETECT_EVERY_N_FRAMES == 0:
            last_detections = face_model.detect_and_embed(small_frame)
        detections = last_detections

        for item in detections:
            left, top, right, bottom = item["bbox"]
            face_embedding = item["embedding"]

            # Scale back coordinates to original frame
            scale = 1 / FRAME_SCALE
            left = int(left * scale)
            top = int(top * scale)
            right = int(right * scale)
            bottom = int(bottom * scale)
            name, score = _match_embedding(face_embedding, known_matrix, known_ids)

            if name != "Unknown":
                now = time.monotonic()
                if name not in last_seen or now - last_seen[name] > ATTENDANCE_COOLDOWN_SEC:
                    mark_attendance(name)
                    last_seen[name] = now

            label = f"{name} ({score:.2f})" if score is not None else name

            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(
                frame,
                label,
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )

        cv2.imshow("Real-Time Face Recognition", frame)

        frame_count += 1
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    real_time_face_recognition()
