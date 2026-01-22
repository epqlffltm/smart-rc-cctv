from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from picarx import Picarx
from vilib import Vilib
import os
from time import strftime, localtime
import sqlite3
import time
import subprocess

app = Flask(__name__)
px = Picarx()

audio_proc = None
current_pan = 0
current_tilt = 0

try:
    Vilib.camera_start(vflip=False, hflip=False)
    Vilib.display(local=False, web=True)
except:
    pass

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
    global audio_proc
    status = request.args.get('status')
    save_path = "/media/epqlffltm/storage/PIcarX_Video/"
    
    if status == 'start':
        if not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)
        video_name = strftime("%Y-%m-%d-%H.%M.%S", localtime())
        Vilib.rec_video_set["path"] = save_path
        Vilib.rec_video_set["name"] = video_name
        
        # 영상 및 오디오 동시 시작
        Vilib.rec_video_run()
        Vilib.rec_video_start()
        audio_temp_path = os.path.join(save_path, f"{video_name}.wav")
        audio_proc = subprocess.Popen([
            'arecord', '-D', 'plughw:4,0', '-f', 'S16_LE', '-r', '44100', '-c', '1', '-t', 'wav', audio_temp_path
        ])
        return jsonify(status="recording")
    
    else:
        Vilib.rec_video_stop()
        if audio_proc:
            audio_proc.terminate()
            audio_proc.wait()
            audio_proc = None
        
        video_name = Vilib.rec_video_set["name"]
        video_path = os.path.join(save_path, video_name + ".avi")
        audio_path = os.path.join(save_path, video_name + ".wav")
        final_mp4 = os.path.join(save_path, video_name + ".mp4")
        
        time.sleep(2) # 파일이 완전히 닫힐 때까지 넉넉히 대기
        
        if os.path.exists(video_path) and os.path.exists(audio_path):
            # [싱크 최적화 FFmpeg 명령어]
            # -filter_complex "[1:a]aresample=async=1": 오디오 타임스탬프 보정
            # -fflags +genpts: 영상 타임스탬프 재생성
            subprocess.run([
                'ffmpeg', '-y', 
                '-i', video_path, 
                '-i', audio_path,
                '-filter_complex', '[1:a]aresample=async=1',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '128k',
                '-shortest', final_mp4
            ])
            os.remove(video_path)
            os.remove(audio_path)
            
            filesize = round(os.path.getsize(final_mp4) / (1024 * 1024), 2)
            created_at = strftime("%Y-%m-%d %H:%M:%S", localtime())
            conn = sqlite3.connect('picarx.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO videos (filename, filepath, filesize_mb, created_at) VALUES (?,?,?,?)', (os.path.basename(final_mp4), final_mp4, filesize, created_at))
            conn.commit(); conn.close()
            
        return jsonify(status="stopped")

@app.route('/videos')
def video_list():
    conn = sqlite3.connect('picarx.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM videos ORDER BY created_at DESC')
    videos = cursor.fetchall()
    conn.close()
    return render_template('videos.html', videos=videos)

# 영상 재생 페이지 라우트
@app.route('/play/<filename>')
def play_video(filename):
    return render_template('player.html', filename=filename)

# 실제 파일 전송 라우트 (재생 및 다운로드 공용)
@app.route('/stream/<filename>')
def stream_video(filename):
    save_path = "/media/epqlffltm/storage/PIcarX_Video/"
    return send_from_directory(save_path, filename)

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
    return redirect(url_for('video_list'))

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        px.stop()