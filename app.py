from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from picarx import Picarx
import cv2
import threading
import time
import os
from datetime import datetime

# --- 설정 ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_picarx_key' # 보안 키 (임의 설정)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- 하드웨어 초기화 ---
px = Picarx()
# 카메라 서보 초기 각도 설정 (중앙)
pan_angle = 0  # 좌우
tilt_angle = 0 # 상하
px.set_cam_pan_angle(pan_angle)
px.set_cam_tilt_angle(tilt_angle)

# --- 전역 변수 (영상 처리용) ---
camera = None
is_recording = False
video_writer = None
output_dir = os.path.join(os.getcwd(), 'recordings')
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# --- 백그라운드 스레드: 영상 캡처 및 스트리밍 ---
def frame_stream():
    global camera, is_recording, video_writer
    camera = cv2.VideoCapture(0) # 0번 카메라 장치 열기
    # 해상도 설정 (너무 높으면 렉 유발, 적절히 타협)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    while True:
        success, frame = camera.read()
        if not success:
            time.sleep(0.1)
            continue

        # 1. 녹화 중이면 파일에 쓰기
        if is_recording and video_writer is not None:
            video_writer.write(frame)
            # 녹화 중임을 화면에 표시 (빨간 원)
            cv2.circle(frame, (30, 30), 10, (0, 0, 255), -1)

        # 2. 웹 전송을 위해 JPEG로 인코딩
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        # 3. 웹소켓으로 데이터 전송 (바이너리 데이터)
        socketio.emit('video_frame', {'image': frame_bytes}, namespace='/')
        
        # 과부하 방지 딜레이 (약 20~30 FPS 목표)
        time.sleep(0.04)

# --- 웹소켓 이벤트 핸들러 ---

@socketio.on('connect')
def connect():
    print("클라이언트 접속 연결됨")
    # 첫 접속 시 영상 스트리밍 스레드 시작 (하나만 실행되도록 체크)
    if threading.active_count() < 3: # 메인 스레드 + 소켓 스레드 외에 없으면
        t = threading.Thread(target=frame_stream, daemon=True)
        t.start()

# 1. 조이스틱 제어 처리 (웹소켓 버전)
@socketio.on('move_control')
def handle_move(data):
    angle = data.get('angle')
    distance = data.get('distance')
    command = data.get('command')

    if command == 'stop':
        px.stop()
        px.set_dir_servo_angle(0)
        return

    if angle is not None and distance is not None:
        speed = int(distance * 1.5) # 속도 보정
        if speed > 100: speed = 100
        
        steering = 0
        if 0 <= angle <= 180: # 전진
            steering = (90 - angle) * 0.6
            px.set_dir_servo_angle(steering)
            px.forward(speed)
        elif 181 <= angle <= 360: # 후진
            steering = (angle - 270) * 0.6
            px.set_dir_servo_angle(steering)
            px.backward(speed)

# 2. 카메라 서보 제어 처리
@socketio.on('camera_control')
def handle_camera(data):
    global pan_angle, tilt_angle
    direction = data.get('direction')
    step = 5 # 한 번 누를 때 움직일 각도

    if direction == 'up':
        tilt_angle = max(-45, tilt_angle - step) # 각도 제한 필요
    elif direction == 'down':
        tilt_angle = min(45, tilt_angle + step)
    elif direction == 'left':
        pan_angle = min(90, pan_angle + step)
    elif direction == 'right':
        pan_angle = max(-90, pan_angle - step)
    elif direction == 'center':
        pan_angle = 0
        tilt_angle = 0
    
    px.set_cam_pan_angle(pan_angle)
    px.set_cam_tilt_angle(tilt_angle)

# 3. 녹화 제어 처리
@socketio.on('record_control')
def handle_record(data):
    global is_recording, video_writer
    action = data.get('action')

    if action == 'start' and not is_recording:
        filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".avi"
        filepath = os.path.join(output_dir, filename)
        # VideoWriter 설정 (코덱, FPS, 해상도)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        video_writer = cv2.VideoWriter(filepath, fourcc, 20.0, (640, 480))
        is_recording = True
        print(f"녹화 시작: {filepath}")
        emit('record_status', {'status': 'recording'})
        
    elif action == 'stop' and is_recording:
        is_recording = False
        if video_writer:
            video_writer.release()
            video_writer = None
        print("녹화 종료")
        emit('record_status', {'status': 'stopped'})


# --- Flask 라우트 ---
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    try:
        # app.run 대신 socketio.run 사용
        socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    finally:
        px.stop()
        if camera: camera.release()
        if video_writer: video_writer.release()