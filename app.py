from flask import Flask, render_template, request, jsonify, send_from_directory, redirect
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/move')
def move():
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

@app.route('/record')
def record():
    status = request.args.get('status')
    username = os.getlogin()
    save_path = f"/media/{username}/storage/PIcarX_Video/"
    
    if status == 'start':
        if not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)
        video_name = strftime("%Y-%m-%d-%H.%M.%S", localtime())
        Vilib.rec_video_set["path"] = save_path
        Vilib.rec_video_set["name"] = video_name
        Vilib.rec_video_run(); Vilib.rec_video_start()
        return jsonify(status="recording", file=video_name)
    else:
        Vilib.rec_video_stop()
        filename = Vilib.rec_video_set["name"] + ".avi"
        filepath = os.path.join(save_path, filename)
        time.sleep(0.5)
        if os.path.exists(filepath):
            filesize = round(os.path.getsize(filepath) / (1024 * 1024), 2)
            created_at = strftime("%Y-%m-%d %H:%M:%S", localtime())
            conn = sqlite3.connect('picarx.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO videos (filename, filepath, filesize_mb, created_at) VALUES (?,?,?,?)', 
                           (filename, filepath, filesize, created_at))
            conn.commit(); conn.close()
        return jsonify(status="stopped")

# [추가된 부분] 영상 목록 보기
@app.route('/videos')
def video_list():
    conn = sqlite3.connect('picarx.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM videos ORDER BY created_at DESC')
    videos = cursor.fetchall()
    conn.close()
    return render_template('videos.html', videos=videos)

# [추가된 부분] 영상 다운로드
@app.route('/download/<filename>')
def download_video(filename):
    username = os.getlogin()
    save_path = f"/media/{username}/storage/PIcarX_Video/"
    return send_from_directory(save_path, filename)

# [추가된 부분] 영상 삭제
@app.route('/delete/<int:video_id>')
def delete_video(video_id):
    conn = sqlite3.connect('picarx.db')
    cursor = conn.cursor()
    cursor.execute('SELECT filepath FROM videos WHERE id = ?', (video_id,))
    row = cursor.fetchone()
    if row and os.path.exists(row[0]):
        os.remove(row[0])
    cursor.execute('DELETE FROM videos WHERE id = ?', (video_id,))
    conn.commit(); conn.close()
    return redirect('/videos')

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        px.stop()