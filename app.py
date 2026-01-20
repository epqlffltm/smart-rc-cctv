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

def init_db():
    """로그를 저장할 테이블이 없으면 생성합니다."""
    with sqlite3.connect(DB_FILE) as conn:
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
            conn.execute("INSERT INTO logs (timestamp, category, action, details) VALUES (?, ?, ?, ?)",
                         (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), category, action, str(details)))
    except:
        pass # 로그 기록 실패가 메인 로직에 영향을 주지 않도록 함

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
    global is_recording, video_writer
    # 중요: CAP_V4L2 옵션을 주어 리눅스 카메라 장치를 명확히 지정합니다.
    camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
    
    # 해상도를 살짝 낮춰 전송 속도를 확보합니다.
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 480)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 320)

    if not camera.isOpened():
        print("❌ 카메라를 열 수 없습니다! 케이블 연결이나 Legacy 설정을 확인하세요.")
        return

    print("✅ 카메라 스트리밍 시작")
    while True:
        success, frame = camera.read()
        if not success:
            continue

        # 녹화 처리
        if is_recording and video_writer:
            video_writer.write(frame)

        # 이미지 인코딩 및 전송
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            socketio.emit('video_frame', {'image': buffer.tobytes()})
        
        socketio.sleep(0.04) # 약 25 FPS

# --- [웹소켓 이벤트 핸들러] ---

@socketio.on('connect')
def handle_connect():
    print("사용자 접속됨")
    # 스레드가 이미 돌아가고 있는지 확인 후 시작
    if threading.active_count() < 3:
        t = threading.Thread(target=frame_stream, daemon=True)
        t.start()

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
        filename = f"rec_{datetime.now().strftime('%H%M%S')}.avi"
        filepath = os.path.join(output_dir, filename)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        video_writer = cv2.VideoWriter(filepath, fourcc, 20.0, (480, 320))
        is_recording = True
        log_event("RECORD", "START", filename)
        emit('record_status', {'status': 'recording'})
        
    elif action == 'stop' and is_recording:
        is_recording = False
        if video_writer:
            video_writer.release()
            video_writer = None
        log_event("RECORD", "STOP")
        emit('record_status', {'status': 'stopped'})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    init_db()
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)