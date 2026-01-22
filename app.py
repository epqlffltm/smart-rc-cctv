from flask import Flask, render_template, request, jsonify
from picarx import Picarx
from vilib import Vilib
import os
from time import strftime, localtime
import sqlite3
import time

app = Flask(__name__)
px = Picarx()

# 카메라 초기화
try:
    Vilib.camera_start(vflip=False, hflip=False)
    Vilib.display(local=False, web=True)
except:
    pass

current_pan = 0
current_tilt = 0

# 1. DB 초기화 (함수 내부 재귀 호출 삭제)
def init_db():
    conn = sqlite3.connect('picarx.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            filesize_mb REAL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# 앱 실행 전 DB 초기화 호출
init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/move')
def move():
    cmd = request.args.get('cmd')
    if cmd == 'forward':
        px.set_dir_servo_angle(0)
        px.forward(50)
    elif cmd == 'backward':
        px.set_dir_servo_angle(0)
        px.backward(50)
    elif cmd == 'left':
        px.set_dir_servo_angle(-35)
        px.forward(40)
    elif cmd == 'right':
        px.set_dir_servo_angle(35)
        px.forward(40)
    elif cmd == 'stop':
        px.stop()
    return "OK"

@app.route('/camera')
def camera_control():
    global current_pan, current_tilt
    cmd = request.args.get('cmd')
    step = 10
    if cmd == 'up': current_tilt += step
    elif cmd == 'down': current_tilt -= step
    elif cmd == 'left': current_pan -= step
    elif cmd == 'right': current_pan += step
    elif cmd == 'center': current_pan, current_tilt = 0, 0

    current_pan = max(min(current_pan, 35), -35)
    current_tilt = max(min(current_tilt, 35), -35)
    px.set_cam_pan_angle(current_pan)
    px.set_cam_tilt_angle(current_tilt)
    return "OK"

@app.route('/record')
def record():
    status = request.args.get('status')
    username = os.getlogin()
    save_path = f"/media/{username}/PIcarX_Video/"
    
    if status == 'start':
        if not os.path.exists(save_path):
            os.makedirs(save_path)
            
        Vilib.rec_video_set["path"] = save_path
        # .avi 확장자는 vilib 내부에서 붙으므로 이름만 저장
        video_name = strftime("%Y-%m-%d-%H.%M.%S", localtime())
        Vilib.rec_video_set["name"] = video_name
        
        Vilib.rec_video_run()
        Vilib.rec_video_start()
        return jsonify(status="recording", file=video_name)
    
    else:
        # 녹화 중지
        Vilib.rec_video_stop()
        
        # 실제 저장된 파일 정보 조합
        filename = Vilib.rec_video_set["name"] + ".avi"
        filepath = os.path.join(save_path, filename)
        
        # 파일이 물리적으로 생성될 때까지 잠시 대기
        time.sleep(0.5)
        
        if os.path.exists(filepath):
            filesize = round(os.path.getsize(filepath) / (1024 * 1024), 2) # MB 단위
            created_at = strftime("%Y-%m-%d %H:%M:%S", localtime())
            
            # DB 저장
            try:
                conn = sqlite3.connect('picarx.db')
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO videos (filename, filepath, filesize_mb, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (filename, filepath, filesize, created_at))
                conn.commit()
                conn.close()
                print(f"DB 저장 성공: {filename} ({filesize}MB)")
            except Exception as e:
                print(f"DB 에러: {e}")
                
        return jsonify(status="stopped")

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        px.stop()