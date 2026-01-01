import cv2
import os
import face_recognition


def capture_face_image(save_path):
    """
    Opens webcam, shows real-time face detection with bounding boxes.
    Press 's' to save image.
    Press 'q' to quit.
    """
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("Error: Cannot access camera")
        return False

    print("Camera opened. Press 's' to save image, 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        # Convert BGR (OpenCV) to RGB (face_recognition)
        rgb_frame = frame[:, :, ::-1]

        # Detect faces
        face_locations = face_recognition.face_locations(rgb_frame)

        # Draw rectangles around faces
        for top, right, bottom, left in face_locations:
            cv2.rectangle(
                frame,
                (left, top),
                (right, bottom),
                (0, 255, 0),
                2
            )

        cv2.imshow("Real-Time Face Detection", frame)

        key = cv2.waitKey(1)

        if key == ord('s'):
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            cv2.imwrite(save_path, frame)
            print(f"Image saved at {save_path}")
            break

        elif key == ord('q'):
            print("Capture cancelled")
            break

    cap.release()
    cv2.destroyAllWindows()
    return True


if __name__ == "__main__":
    test_path = "data/students/test_student/photo1.jpg"
    capture_face_image(test_path)
