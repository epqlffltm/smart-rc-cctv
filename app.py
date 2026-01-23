from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from picarx import Picarx
from vilib import Vilib
import os
from time import strftime, localtime, sleep
import sqlite3
import subprocess
import threading

app = Flask(__name__)
px = Picarx()

# --- 전역 변수 및 설정 ---
audio_proc = None
current_pan = 0
current_tilt = 0
auto_mode = False  # 스마트 모드 활성화 여부
SAVE_PATH = "/media/epqlffltm/storage/PIcarX_Video/"

# 낭떠러지 감지 기준값 설정
px.set_cliff_reference([200, 200, 200])

# 카메라 초기화 (1080p 설정)
try:
    Vilib.camera_start(vflip=False, hflip=False, size=(1920, 1080))
    Vilib.display(local=False, web=True)
except Exception as e:
    print(f"카메라 연결 오류: {e}")

# DB 초기화
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

init_db()

# --- 스마트 모드(자율 주행) 스레드 로직 ---
def auto_pilot_loop():
    global auto_mode
    POWER = 50
    SafeDistance = 40
    DangerDistance = 20

    while True:
        if auto_mode:
            # 1. 낭떠러지 감지 (최우선순위)
            gm_val_list = px.get_grayscale_data()
            gm_state = px.get_cliff_status(gm_val_list)

            if gm_state:  # 낭떠러지 감지됨 (danger)
                px.stop()
                px.backward(80)
                sleep(0.3)
                px.stop()
                continue

            # 2. 장애물 회피
            distance = round(px.ultrasonic.read(), 2)
            if distance >= SafeDistance:
                px.set_dir_servo_angle(0)
                px.forward(POWER)
            elif distance >= DangerDistance:
                px.set_dir_servo_angle(30)
                px.forward(POWER)
                sleep(0.1)
            else: # 아주 가까운 경우
                px.set_dir_servo_angle(-30)
                px.backward(POWER)
                sleep(0.5)
        
        sleep(0.1)

# 백그라운드 스레드 시작
threading.Thread(target=auto_pilot_loop, daemon=True).start()

# --- Flask 라우트 ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/move')
def move():
    global auto_mode
    if auto_mode: return "Auto Mode Active"
    cmd = request.args.get('cmd')
    if cmd == 'forward': px.forward(50)
    elif cmd == 'backward': px.backward(50)
    elif cmd == 'left': px.set_dir_servo_angle(-35); px.forward(40)
    elif cmd == 'right': px.set_dir_servo_angle(35); px.forward(40)
    elif cmd == 'stop': px.stop()
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

@app.route('/auto_mode')
def toggle_auto_mode():
    global auto_mode
    status = request.args.get('status')
    auto_mode = (status == 'on')
    if not auto_mode: px.stop()
    return jsonify(auto_mode=auto_mode)

@app.route('/record')
def record():
    global audio_proc
    status = request.args.get('status')
    
    if status == 'start':
        if not os.path.exists(SAVE_PATH):
            os.makedirs(SAVE_PATH, exist_ok=True)
        
        v_name = strftime("%Y-%m-%d-%H.%M.%S", localtime())
        Vilib.rec_video_set["path"] = SAVE_PATH
        Vilib.rec_video_set["name"] = v_name
        Vilib.rec_video_set["resolution"] = (1920, 1080)
        
        Vilib.rec_video_run()
        Vilib.rec_video_start()
        
        audio_temp = os.path.join(SAVE_PATH, f"{v_name}.wav")
        audio_proc = subprocess.Popen([
            'arecord', '-D', 'plughw:4,0', '-f', 'S16_LE', '-r', '44100', '-c', '1', '-t', 'wav', audio_temp
        ])
        return jsonify(status="recording")
    
    else:
        Vilib.rec_video_stop()
        if audio_proc:
            audio_proc.terminate(); audio_proc.wait(); audio_proc = None
        
        v_name = Vilib.rec_video_set["name"]
        v_path = os.path.join(SAVE_PATH, v_name + ".avi")
        a_path = os.path.join(SAVE_PATH, v_name + ".wav")
        final_mp4 = os.path.join(SAVE_PATH, v_name + ".mp4")
        
        sleep(2)
        if os.path.exists(v_path) and os.path.exists(a_path):
            subprocess.run([
                'ffmpeg', '-y', '-i', v_path, '-i', a_path,
                '-af', 'volume=2.0,aresample=async=1',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-shortest', final_mp4
            ])
            os.remove(v_path); os.remove(a_path)
            
            fsize = round(os.getsize(final_mp4) / (1024 * 1024), 2)
            db_time = strftime("%Y-%m-%d %H:%M:%S", localtime())
            conn = sqlite3.connect('picarx.db')
            conn.execute('INSERT INTO videos (filename, filepath, filesize_mb, created_at) VALUES (?,?,?,?)', (os.path.basename(final_mp4), final_mp4, fsize, db_time))
            conn.commit(); conn.close()
            
        return jsonify(status="stopped")

@app.route('/videos')
def video_list():
    conn = sqlite3.connect('picarx.db')
    conn.row_factory = sqlite3.Row
    videos = conn.execute('SELECT * FROM videos ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('videos.html', videos=videos)

@app.route('/play/<filename>')
def play_video(filename):
    return render_template('player.html', filename=filename)

@app.route('/stream/<filename>')
def stream_video(filename):
    return send_from_directory(SAVE_PATH, filename)

@app.route('/delete/<int:video_id>')
def delete_video(video_id):
    conn = sqlite3.connect('picarx.db')
    cursor = conn.cursor()
    row = cursor.execute('SELECT filepath FROM videos WHERE id = ?', (video_id,)).fetchone()
    if row and os.path.exists(row[0]): os.remove(row[0])
    cursor.execute('DELETE FROM videos WHERE id = ?', (video_id,))
    conn.commit(); conn.close()
    return redirect(url_for('video_list'))

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        px.stop()