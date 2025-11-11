
import cv2
import numpy as np
import os
from datetime import datetime

# Đường dẫn lưu ảnh khuôn mặt mẫu của nhân viên (dạng: static/captured/{employee_id}.jpg)
FACE_SAMPLES_DIR = 'static/captured/'

def detect_face(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    return faces

def recognize_face(frame):
    faces = detect_face(frame)
    if len(faces) == 0:
        return None, frame
    (x, y, w, h) = faces[0]
    face_img = frame[y:y+h, x:x+w]
    # Duyệt qua các ảnh mẫu để so sánh
    for filename in os.listdir(FACE_SAMPLES_DIR):
        if filename.endswith('.jpg'):
            sample = cv2.imread(os.path.join(FACE_SAMPLES_DIR, filename))
            sample = cv2.resize(sample, (w, h))
            diff = cv2.absdiff(face_img, sample)
            if np.mean(diff) < 50:  # Ngưỡng nhận diện, có thể điều chỉnh
                employee_id = filename.split('.')[0]
                return employee_id, frame
    return None, frame

def capture_and_recognize():
    cam = cv2.VideoCapture(0)
    ret, frame = cam.read()
    employee_id = None
    if ret:
        employee_id, frame = recognize_face(frame)
        filename = f"static/captured/{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(filename, frame)
    cam.release()
    return employee_id
