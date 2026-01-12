import cv2
import os
import numpy as np
import face_recognition
from face_engine.face_recognize import load_known_faces
from modules.attendance_manager import mark_attendance

STUDENTS_DIR = "data/students"
TOLERANCE = 0.6  # Adjust as needed (0.55-0.65)


def capture_face_image(save_path):
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Camera not accessible")
        return False

    print("Press S to save, Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")

        for top, right, bottom, left in face_locations:
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


def real_time_face_recognition():
    known_encodings, known_ids = load_known_faces(STUDENTS_DIR)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Camera not accessible")
        return

    print("Press Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Resize frame to half for performance
        small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        # Scale back coordinates
        face_locations = [(top*2, right*2, bottom*2, left*2) for (top, right, bottom, left) in face_locations]

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            # Use face distance for best match
            if known_encodings:
                face_distances = face_recognition.face_distance(known_encodings, face_encoding)
                best_match_index = np.argmin(face_distances)
                if face_distances[best_match_index] <= TOLERANCE:
                    name = known_ids[best_match_index]
                    mark_attendance(name)
                else:
                    name = "Unknown"
            else:
                name = "Unknown"

            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(
                frame,
                name,
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )

        cv2.imshow("Real-Time Face Recognition", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    real_time_face_recognition()
