import cv2

camera = cv2.VideoCapture(0)
if camera.isOpened():
    ret, frame = camera.read()
    if ret:
        print("✅ 카메라 정상 작동!")
        cv2.imwrite('test.jpg', frame)
    else:
        print("❌ 프레임 읽기 실패")
else:
    print("❌ 카메라 열기 실패")
camera.release()