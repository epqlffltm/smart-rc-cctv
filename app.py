from flask import Flask, render_template, request, jsonify
from picarx import Picarx
from vilib import Vilib
import os
from time import strftime, localtime

app = Flask(__name__)

# Picar-X 및 카메라 초기화
px = Picarx()
Vilib.camera_start(vflip=False, hflip=False)
Vilib.display(local=False, web=True) # 웹 스트리밍 활성화 (포트 9000)

# 현재 카메라 각도 상태 저장
current_pan = 0
current_tilt = 0
rec_status = 'stop'
vname = ""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/move', methods=['POST'])
def move():
    data = request.json
    angle = data.get('angle', 0)
    speed = data.get('speed', 0)
    
    # 조이스틱 각도와 속도를 이용해 조향 및 주행 제어
    px.set_dir_servo_angle(angle)
    if speed > 0:
        px.forward(speed)
    elif speed < 0:
        px.backward(abs(speed))
    else:
        px.stop()
    return jsonify(status="success")

@app.route('/camera', methods=['POST'])
def camera_control():
    global current_pan, current_tilt
    data = request.json
    action = data.get('action')
    
    if action == 'left': current_pan += 5
    elif action == 'right': current_pan -= 5
    elif action == 'up': current_tilt -= 5
    elif action == 'down': current_tilt += 5
    elif action == 'center': 
        current_pan = 0
        current_tilt = 0

    # 각도 제한 (-35 ~ 35)
    current_pan = max(min(current_pan, 35), -35)
    current_tilt = max(min(current_tilt, 35), -35)
    
    px.set_cam_pan_angle(current_pan)
    px.set_cam_tilt_angle(current_tilt)
    return jsonify(pan=current_pan, tilt=current_tilt)

@app.route('/record', methods=['POST'])
def record_video():
    global rec_status, vname
    username = os.getlogin()
    Vilib.rec_video_set["path"] = f"/home/{username}/Videos/"

    if rec_status == 'stop':
        rec_status = 'start'
        vname = strftime("%Y-%m-%d-%H.%M.%S", localtime())
        Vilib.rec_video_set["name"] = vname
        Vilib.rec_video_run()
        Vilib.rec_video_start()
        return jsonify(status="recording", file=vname)
    else:
        rec_status = 'stop'
        Vilib.rec_video_stop()
        return jsonify(status="stopped")

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000)
    finally:
        px.stop()
        Vilib.camera_close()