import cv2, threading, time, os, sqlite3
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from picarx import Picarx
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
px = Picarx()

# --- [마개조] SQLite DB 초기화 ---
DB_FILE = 'cctv_logs.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS logs 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      timestamp TEXT, 
                      category TEXT, 
                      action TEXT, 
                      details TEXT)''')
    print("✅ SQLite DB 초기화 완료")

def log_event(category, action, details=""):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO logs (timestamp, category, action, details) VALUES (?, ?, ?, ?)",
                     (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), category, action, str(details)))

# --- 하드웨어 설정 ---
pan_angle, tilt_angle = 0, 0
px.set_cam_pan_angle(pan_angle)
px.set_cam_tilt_angle(tilt_angle)

# --- [핵심] 카메라 스트리밍 최적화 ---
def frame_stream():
    # 라즈베리 파이에서 가장 안정적인 V4L2 백엔드 강제 지정
    camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    global is_recording, video_writer
    is_recording = False
    video_writer = None

    if not camera.isOpened():
        print("❌ 카메라를 열 수 없습니다. /dev/video0 점검 필요")
        return

    while True:
        success, frame = camera.read()
        if not success: continue

        if is_recording and video_writer:
            video_writer.write(frame)

        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ret:
            socketio.emit('video_frame', {'image': buffer.tobytes()})
        socketio.sleep(0.05) # 약 20 FPS

# --- 웹소켓 이벤트 (조종 및 기록) ---

@socketio.on('move_control')
def handle_move(data):
    if data.get('command') == 'stop':
        px.stop()
        px.set_dir_servo_angle(0)
        log_event("MOVE", "STOP")
    else:
        angle, dist = data['angle'], data['distance']
        speed = min(int(dist * 1.5), 100)
        steering = (90 - angle) * 0.6 if 0 <= angle <= 180 else (angle - 270) * 0.6
        px.set_dir_servo_angle(steering)
        if 0 <= angle <= 180: px.forward(speed)
        else: px.backward(speed)
        # 잦은 기록 방지를 위해 이동은 'MOVE' 카테고리로 통합 기록 가능
        # log_event("MOVE", "DRIVE", f"speed:{speed}, steer:{steering}")

@socketio.on('camera_control')
def handle_camera(data):
    global pan_angle, tilt_angle
    dir = data['direction']
    if dir == 'up': tilt_angle = max(-45, tilt_angle - 5)
    elif dir == 'down': tilt_angle = min(45, tilt_angle + 5)
    elif dir == 'left': pan_angle = min(90, pan_angle + 5)
    elif dir == 'right': pan_angle = max(-90, pan_angle - 5)
    elif dir == 'center': pan_angle, tilt_angle = 0, 0
    
    px.set_cam_pan_angle(pan_angle)
    px.set_cam_tilt_angle(tilt_angle)
    log_event("CAMERA", "ROTATE", f"pan:{pan_angle}, tilt:{tilt_angle}")

@socketio.on('record_control')
def handle_record(data):
    global is_recording, video_writer
    if data['action'] == 'start':
        filename = f"rec_{datetime.now().strftime('%H%M%S')}.avi"
        path = os.path.join('recordings', filename)
        if not os.path.exists('recordings'): os.makedirs('recordings')
        video_writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'XVID'), 20.0, (640, 480))
        is_recording = True
        log_event("RECORD", "START", filename)
        emit('record_status', {'status': 'recording'})
    else:
        is_recording = False
        if video_writer: video_writer.release()
        log_event("RECORD", "STOP")
        emit('record_status', {'status': 'stopped'})

@app.route('/')
def index(): return render_template('index.html')

if __name__ == "__main__":
    init_db()
    threading.Thread(target=frame_stream, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)