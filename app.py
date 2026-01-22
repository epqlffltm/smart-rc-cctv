from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from picarx import Picarx
from vilib import Vilib
import os
from time import strftime, localtime
import sqlite3
import time
import subprocess # 오디오 녹음 및 병합용

app = Flask(__name__)
px = Picarx()

# 전역 변수로 오디오 프로세스 관리
audio_proc = None

# 카메라 초기화
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
    # ... 카메라 조절 로직 (이전과 동일) ...
    return "OK"

@app.route('/record')
def record():
    global audio_proc
    status = request.args.get('status')
    username = os.getlogin()
    save_path = f"/media/{username}/storage/PIcarX_Video/"
    
    if status == 'start':
        if not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)
        
        video_name = strftime("%Y-%m-%d-%H.%M.%S", localtime())
        Vilib.rec_video_set["path"] = save_path
        Vilib.rec_video_set["name"] = video_name
        
        # 1. 영상 녹화 시작
        Vilib.rec_video_run()
        Vilib.rec_video_start()
        
        # 2. 오디오 녹음 시작 (설정 최적화)
        audio_temp_path = os.path.join(save_path, f"{video_name}.wav")
        audio_proc = subprocess.Popen([
            'arecord', 
            '-D', 'plughw:4,0', 
            '-f', 'S16_LE',    # 16비트 형식
            '-r', '44100',      # CD 음질 샘플링
            '-c', '1',          # 모노(USB 마이크는 보통 모노)
            '-t', 'wav', 
            audio_temp_path
        ])
        return jsonify(status="recording")
    
    else:
        # 1. 녹화 중지
        Vilib.rec_video_stop()
        if audio_proc:
            audio_proc.terminate()
            audio_proc.wait()
            audio_proc = None
        
        video_name = Vilib.rec_video_set["name"]
        video_path = os.path.join(save_path, video_name + ".avi")
        audio_path = os.path.join(save_path, video_name + ".wav")
        final_mp4 = os.path.join(save_path, video_name + ".mp4")
        
        time.sleep(1.5) # 파일이 완전히 닫힐 때까지 대기
        
        if os.path.exists(video_path) and os.path.exists(audio_path):
            # 2. FFmpeg 병합 (소리가 작을 수 있으니 volume=2.0으로 2배 증폭 옵션 추가)
            subprocess.run([
                'ffmpeg', '-y', 
                '-i', video_path, 
                '-i', audio_path,
                '-af', 'volume=2.0', # 소리 2배 증폭
                '-c:v', 'copy', 
                '-c:a', 'aac', 
                '-shortest',        # 영상/음성 중 짧은 쪽에 맞춤
                final_mp4
            ])
            
            # 3. 임시 파일 삭제
            os.remove(video_path)
            os.remove(audio_path)
            
            # 4. DB 저장
            filesize = round(os.path.getsize(final_mp4) / (1024 * 1024), 2)
            created_at = strftime("%Y-%m-%d %H:%M:%S", localtime())
            conn = sqlite3.connect('picarx.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO videos (filename, filepath, filesize_mb, created_at) VALUES (?,?,?,?)', (os.path.basename(final_mp4), final_mp4, filesize, created_at))
            conn.commit()
            conn.close()
            
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

@app.route('/download/<filename>')
def download_video(filename):
    username = os.getlogin()
    save_path = f"/media/{username}/storage/PIcarX_Video/"
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