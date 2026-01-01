import face_recognition
import os


def load_known_faces(students_dir):
    """
    Load all student images and encode faces.
    Returns encodings and corresponding student IDs.
    """
    known_encodings = []
    known_ids = []

    for student_id in os.listdir(students_dir):
        student_path = os.path.join(students_dir, student_id)

        if not os.path.isdir(student_path):
            continue

        for file in os.listdir(student_path):
            if file.endswith(".jpg") or file.endswith(".png"):
                image_path = os.path.join(student_path, file)
                image = face_recognition.load_image_file(image_path)
                encodings = face_recognition.face_encodings(image)

                if encodings:
                    known_encodings.append(encodings[0])
                    known_ids.append(student_id)

    return known_encodings, known_ids


def recognize_face(unknown_image_path, known_encodings, known_ids):
    """
    Compare captured face with known faces.
    """
    unknown_image = face_recognition.load_image_file(unknown_image_path)
    unknown_encodings = face_recognition.face_encodings(unknown_image)

    if not unknown_encodings:
        return None

    unknown_encoding = unknown_encodings[0]

    results = face_recognition.compare_faces(
        known_encodings, unknown_encoding, tolerance=0.5
    )

    if True in results:
        match_index = results.index(True)
        return known_ids[match_index]

    return None
