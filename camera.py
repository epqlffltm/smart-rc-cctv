import cv2

# 0, 1, 2번을 순서대로 테스트
for i in range(3):
    camera = cv2.VideoCapture(i)
    if camera.isOpened():
        ret, frame = camera.read()
        if ret:
            print(f"✅ {i}번 카메라에서 영상 읽기 성공!")
            cv2.imwrite(f'test_{i}.jpg', frame)
            camera.release()
            break
        else:
            print(f"❓ {i}번 장치 열기 성공했으나 프레임 읽기 실패")
    else:
        print(f"❌ {i}번 장치 열기 실패")
    camera.release()