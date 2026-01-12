import face_recognition
import os


def load_known_faces(students_dir):
    known_encodings = []
    known_ids = []

    print("Looking for students in:", os.path.abspath(students_dir))

    if not os.path.exists(students_dir):
        print("❌ students directory does NOT exist")
        return known_encodings, known_ids

    for student_id in os.listdir(students_dir):
        student_path = os.path.join(students_dir, student_id)
        print("Checking folder:", student_path)

        if not os.path.isdir(student_path):
            print("  ⛔ Not a directory")
            continue

        for file in os.listdir(student_path):
            print("  Found file:", file)

            if file.lower().endswith((".jpg", ".png")):
                image_path = os.path.join(student_path, file)
                print("  Loading image:", image_path)

                image = face_recognition.load_image_file(image_path)
                encodings = face_recognition.face_encodings(image)

                print("  Faces found in image:", len(encodings))

                if encodings:
                    known_encodings.append(encodings[0])
                    known_ids.append(student_id)

    print("FINAL → Known faces loaded:", len(known_encodings))
    return known_encodings, known_ids


