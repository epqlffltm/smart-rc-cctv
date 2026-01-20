from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from picarx import Picarx
import cv2
import threading
import time
import os
import sqlite3
from datetime import datetime

# --- [설정 및 DB 초기화] ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'picarx_secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_FILE = 'smart_rc.db'
# 카메라 스레드가 중복 실행되지 않도록 체크하는 플래그
camera_started = False 

def init_db():
    """로그를 저장할 테이블이 없으면 생성합니다."""
    with sqlite3.connect(DB_FILE) as conn:
        # 테이블 이름을 control_logs로 통일
        conn.execute('''CREATE TABLE IF NOT EXISTS control_logs 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    timestamp TEXT, 
                    category TEXT, 
                    action TEXT, 
                    details TEXT)''')
    print("✅ SQLite 데이터베이스 준비 완료")

def log_event(category, action, details=""):
    """이벤트를 DB에 기록합니다."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            # 테이블 이름을 control_logs로 수정
            conn.execute("INSERT INTO control_logs (timestamp, category, action, details) VALUES (?, ?, ?, ?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), category, action, str(details)))
    except Exception as e:
        print(f"❌ DB 기록 에러: {e}")

# --- [하드웨어 초기화] ---
px = Picarx()
pan_angle, tilt_angle = 0, 0
px.set_cam_pan_angle(pan_angle)
px.set_cam_tilt_angle(tilt_angle)

# --- [전역 변수] ---
is_recording = False
video_writer = None
output_dir = 'recordings'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# --- [카메라 스트리밍 스레드] ---
def frame_stream():
    global is_recording, video_writer, camera_started
    print("카메라 연결 시도 중...")
    
    # 0번이 안되면 1번, 그것도 안되면 CAP_V4L2 없이 시도
    camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not camera.isOpened():
        camera = cv2.VideoCapture(1, cv2.CAP_V4L2)
    
    if not camera.isOpened():
        print("카메라를 열 수 없습니다! 케이블이나 리눅스 설정을 확인하세요.")
        camera_started = False # 실패하면 다시 시도할 수 있게 플래그 리셋
        return

    # 전송 속도를 위해 해상도 최적화
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    print("카메라 스트리밍 시작")
    while True:
        success, frame = camera.read()
        if not success:
            continue

        if is_recording and video_writer:
            video_writer.write(frame)

        # JPEG 압축률을 조절하여 전송 부하 감소
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            socketio.emit('video_frame', {'image': buffer.tobytes()})
        
        # 0.04초 대기 (약 25 FPS)
        socketio.sleep(0.04)

# --- [웹소켓 이벤트 핸들러] ---

@socketio.on('connect')
def handle_connect():
    global camera_started
    print("브라우저 접속됨")
    
    # active_count 대신 전역 플래그를 사용하여 확실하게 스레드 시작
    if not camera_started:
        camera_started = True
        t = threading.Thread(target=frame_stream, daemon=True)
        t.start()
        print("카메라 스레드 기동 완료")

@socketio.on('move_control')
def handle_move(data):
    angle = data.get('angle')
    distance = data.get('distance')
    command = data.get('command')

    if command == 'stop':
        px.stop()
        px.set_dir_servo_angle(0)
        log_event("MOVE", "STOP")
        return

    if angle is not None and distance is not None:
        speed = min(int(distance * 1.5), 100)
        steering = (90 - angle) * 0.6 if 0 <= angle <= 180 else (angle - 270) * 0.6
        px.set_dir_servo_angle(steering)
        if 0 <= angle <= 180: px.forward(speed)
        else: px.backward(speed)
        # 이동 로그도 남기고 싶다면 주석 해제 (단, 로그가 너무 많아질 수 있음)
        # log_event("MOVE", "DRIVE", f"speed:{speed}")

@socketio.on('camera_control')
def handle_camera(data):
    global pan_angle, tilt_angle
    direction = data.get('direction')
    step = 5

    if direction == 'up': tilt_angle = max(-45, tilt_angle - step)
    elif direction == 'down': tilt_angle = min(45, tilt_angle + step)
    elif direction == 'left': pan_angle = min(90, pan_angle + step)
    elif direction == 'right': pan_angle = max(-90, pan_angle - step)
    elif direction == 'center': pan_angle, tilt_angle = 0, 0
        
    px.set_cam_pan_angle(pan_angle)
    px.set_cam_tilt_angle(tilt_angle)
    log_event("CAMERA", "ROTATE", f"pan:{pan_angle}, tilt:{tilt_angle}")

@socketio.on('record_control')
def handle_record(data):
    global is_recording, video_writer
    action = data.get('action')

    if action == 'start' and not is_recording:
        filename = f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
        filepath = os.path.join(output_dir, filename)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        # 녹화 해상도는 카메라 설정 해상도(320x240)와 일치시켜야 함
        video_writer = cv2.VideoWriter(filepath, fourcc, 20.0, (320, 240))
        is_recording = True
        log_event("RECORD", "START", filename)
        emit('record_status', {'status': 'recording'})
        print(f"녹화 시작: {filename}")
        
    elif action == 'stop' and is_recording:
        is_recording = False
        if video_writer:
            video_writer.release()
            video_writer = None
        log_event("RECORD", "STOP")
        emit('record_status', {'status': 'stopped'})
        print("녹화 종료")

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    init_db()
    # allow_unsafe_werkzeug=True는 개발용이므로 그대로 유지
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    print("서버 시작 완료 - http://localhost:5000")