import os
import pickle
from typing import List, Tuple

import numpy as np

from face_engine.face_model import FaceModel

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def _list_images(folder: str) -> List[str]:
    if not os.path.isdir(folder):
        return []
    files = [f for f in os.listdir(folder) if f.lower().endswith(IMAGE_EXTENSIONS)]
    files.sort()
    return [os.path.join(folder, f) for f in files]


def load_known_faces(
    students_dir: str,
    face_model: FaceModel | None = None,
) -> Tuple[List[np.ndarray], List[str]]:
    """
    Loads all students' folders and returns averaged embeddings.
    Only images with exactly one face are used.
    """
    known_encodings: List[np.ndarray] = []
    known_ids: List[str] = []
    face_model = face_model or FaceModel()

    print("Looking for students in:", os.path.abspath(students_dir))
    if not os.path.exists(students_dir):
        print("❌ students directory does NOT exist")
        return known_encodings, known_ids

    cache_path = os.path.join(students_dir, "encodings.pkl")
    use_cache = False

    if os.path.exists(cache_path):
        cache_mtime = os.path.getmtime(cache_path)
        # Check if any student folder is newer than the cache file
        is_stale = False
        for entry in os.scandir(students_dir):
            if entry.is_dir() and entry.stat().st_mtime > cache_mtime:
                is_stale = True
                print(f"♻️  New data detected in '{entry.name}'. Rebuilding cache...")
                break
        
        if not is_stale:
            print(f"⚡ Loading cached encodings from {cache_path}")
            with open(cache_path, "rb") as f:
                return pickle.load(f)

    for student_id in sorted(os.listdir(students_dir)):
        student_path = os.path.join(students_dir, student_id)
        student_encodings = []
        print("Checking folder:", student_path)

        if not os.path.isdir(student_path):
            print("  ⛔ Not a directory")
            continue

        for image_path in _list_images(student_path):
            print("  Loading image:", image_path)
            encodings = face_model.image_embeddings(image_path)
            print("  Faces found in image:", len(encodings))

            # Only use clean enrollment images with exactly one face.
            if len(encodings) == 1:
                student_encodings.append(encodings[0])
            elif len(encodings) > 1:
                print("  ⛔ Skipping image with multiple faces")

        if student_encodings:
            avg_embedding = np.mean(np.asarray(student_encodings, dtype=np.float32), axis=0)
            avg_embedding = avg_embedding / (np.linalg.norm(avg_embedding) + 1e-8)
            known_encodings.append(avg_embedding)
            known_ids.append(student_id)
            print("  ✅ Enrolled with", len(student_encodings), "image(s)")
        else:
            print("  ⚠️ No valid single-face images for", student_id)

    # Save to cache for next time
    with open(cache_path, "wb") as f:
        pickle.dump((known_encodings, known_ids), f)

    print("FINAL → Known faces loaded:", len(known_encodings))
    return known_encodings, known_ids
