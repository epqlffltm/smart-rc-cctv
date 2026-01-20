from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from picarx import Picarx
from vilib import Vilib  # Vilib 도입
import cv2  # 영상 인코딩 및 녹화를 위해 사용
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
camera_started = False 

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS control_logs 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      timestamp TEXT, 
                      category TEXT, 
                      action TEXT, 
                      details TEXT)''')
    print("✅ SQLite 데이터베이스 준비 완료")

def log_event(category, action, details=""):
    try:
        with sqlite3.connect(DB_FILE) as conn:
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

# --- [카메라 스트리밍 스레드 (Vilib 기반)] ---
def frame_stream():
    global is_recording, video_writer, camera_started
    
    print("🚀 Vilib 카메라 시작 중...")
    Vilib.camera_start(vflip=False, hflip=False)
    # Vilib 내부 서버 기능을 끄고 싶다면 web=False, 필요하면 True
    Vilib.display(local=False, web=True) 
    
    time.sleep(2)  # 카메라 안정화 대기
    print("✅ Vilib 스트리밍 시작")

    while True:
        # Vilib에서 현재 프레임을 가져옵니다 (OpenCV 형식)
        frame = Vilib.img
        
        if frame is None:
            time.sleep(0.01)
            continue

        # 녹화 처리 (cv2.VideoWriter 활용)
        if is_recording and video_writer:
            video_writer.write(frame)

        # 프론트엔드 전송을 위해 JPEG 인코딩
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ret:
            socketio.emit('video_frame', {'image': buffer.tobytes()})
        
        socketio.sleep(0.05) # 약 20 FPS

# --- [웹소켓 이벤트 핸들러] ---

@socketio.on('connect')
def handle_connect():
    global camera_started
    print("🌐 브라우저 접속됨")
    if not camera_started:
        camera_started = True
        t = threading.Thread(target=frame_stream, daemon=True)
        t.start()

@socketio.on('move_control')
def handle_move(data):
    angle, dist, cmd = data.get('angle'), data.get('distance'), data.get('command')
    if cmd == 'stop':
        px.stop()
        px.set_dir_servo_angle(0)
        log_event("MOVE", "STOP")
    elif angle is not None:
        speed = min(int(dist * 1.5), 100)
        steering = (90 - angle) * 0.6 if 0 <= angle <= 180 else (angle - 270) * 0.6
        px.set_dir_servo_angle(steering)
        if 0 <= angle <= 180: px.forward(speed)
        else: px.backward(speed)

@socketio.on('camera_control')
def handle_camera(data):
    global pan_angle, tilt_angle
    direction = data.get('direction')
    if direction == 'up': tilt_angle = max(-45, tilt_angle - 5)
    elif direction == 'down': tilt_angle = min(45, tilt_angle + 5)
    elif direction == 'left': pan_angle = min(90, pan_angle + 5)
    elif direction == 'right': pan_angle = max(-90, pan_angle - 5)
    elif direction == 'center': pan_angle, tilt_angle = 0, 0
    px.set_cam_pan_angle(pan_angle)
    px.set_cam_tilt_angle(tilt_angle)
    log_event("CAMERA", "ROTATE", f"p:{pan_angle}, t:{tilt_angle}")

@socketio.on('record_control')
def handle_record(data):
    global is_recording, video_writer
    if data.get('action') == 'start' and not is_recording:
        filename = f"rec_{datetime.now().strftime('%H%M%S')}.avi"
        filepath = os.path.join(output_dir, filename)
        # Vilib 기본 해상도 640x480에 맞춤
        video_writer = cv2.VideoWriter(filepath, cv2.VideoWriter_fourcc(*'XVID'), 20.0, (640, 480))
        is_recording = True
        log_event("RECORD", "START", filename)
        emit('record_status', {'status': 'recording'})
    elif data.get('action') == 'stop' and is_recording:
        is_recording = False
        if video_writer: video_writer.release()
        video_writer = None
        log_event("RECORD", "STOP")
        emit('record_status', {'status': 'stopped'})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    init_db()
    try:
        socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    finally:
        Vilib.camera_close() # 종료 시 카메라 자원 해제