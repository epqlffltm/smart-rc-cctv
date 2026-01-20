from flask import Flask, render_template, request, jsonify
from picarx import Picarx
from vilib import Vilib
import os
from time import strftime, localtime

app = Flask(__name__)
px = Picarx()

# 카메라 초기화
try:
    Vilib.camera_start(vflip=False, hflip=False)
    Vilib.display(local=False, web=True)
except:
    pass

# 카메라 각도 상태
current_pan = 0
current_tilt = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/move')
def move():
    cmd = request.args.get('cmd')
    # 주행 제어 로직
    if cmd == 'forward':
        px.set_dir_servo_angle(0)
        px.forward(50)
    elif cmd == 'backward':
        px.set_dir_servo_angle(0)
        px.backward(50)
    elif cmd == 'left':
        px.set_dir_servo_angle(-35) # 왼쪽으로 꺾기
        px.forward(40)
    elif cmd == 'right':
        px.set_dir_servo_angle(35)  # 오른쪽으로 꺾기
        px.forward(40)
    elif cmd == 'stop':
        px.stop()
    return "OK"

@app.route('/camera')
def camera_control():
    global current_pan, current_tilt
    cmd = request.args.get('cmd')
    step = 10
    
    # [방향 교정] 사용자 피드백 반영하여 반대로 수정
    if cmd == 'up': current_tilt -= step      # 위로 (반대면 += 로 수정)
    elif cmd == 'down': current_tilt += step  # 아래로
    elif cmd == 'left': current_pan -= step   # 왼쪽
    elif cmd == 'right': current_pan += step  # 오른쪽
    elif cmd == 'center': current_pan, current_tilt = 0, 0

    current_pan = max(min(current_pan, 35), -35)
    current_tilt = max(min(current_tilt, 35), -35)
    
    px.set_cam_pan_angle(current_pan)
    px.set_cam_tilt_angle(current_tilt)
    return "OK"

@app.route('/record')
def record():
    status = request.args.get('status')
    if status == 'start':
        Vilib.rec_video_set["name"] = strftime("%Y-%m-%d-%H.%M.%S", localtime())
        Vilib.rec_video_run()
        Vilib.rec_video_start()
    else:
        Vilib.rec_video_stop()
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)