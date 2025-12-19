import cv2
import face_recognition

video = cv2.VideoCapture(0)

while True:
    ret, frame = video.read()
    rgb = frame[:, :, ::-1]

    face_locations = face_recognition.face_locations(rgb)

    for top, right, bottom, left in face_locations:
        cv2.rectangle(
            frame,
            (left, top),
            (right, bottom),
            (0, 255, 0),
            2
        )

    cv2.imshow("Bus Face Monitor", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()

