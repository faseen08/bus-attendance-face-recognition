import cv2
import face_recognition
import os

# Load known face
known_image = face_recognition.load_image_file("known-faces/faseen.jpg")
known_encoding = face_recognition.face_encodings(known_image)[0]

known_encodings = [known_encoding]
known_names = ["Student 1"]

video = cv2.VideoCapture(0)

while True:
    ret, frame = video.read()
    rgb = frame[:, :, ::-1]

    face_locations = face_recognition.face_locations(rgb)
    face_encodings = face_recognition.face_encodings(rgb, face_locations)

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
        matches = face_recognition.compare_faces(known_encodings, face_encoding)
        name = "Unknown"

        if True in matches:
            name = known_names[matches.index(True)]

        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.putText(
            frame,
            name,
            (left, top - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 255, 0),
            2
        )

    cv2.imshow("Bus Face Recognition", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()

