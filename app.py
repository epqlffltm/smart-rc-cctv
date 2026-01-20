from flask import Flask, render_template, request, jsonify
from picarx import Picarx  # 제공된 파일 기준 lowercase 'x' 사용
from vilib import Vilib
import os
from time import strftime, localtime

app = Flask(__name__)

# Picar-X 및 카메라 초기화
px = Picarx()
Vilib.camera_start(vflip=False, hflip=False)
Vilib.display(local=False, web=True)  # 포트 9000번 스트리밍 활성화

# 상태 변수
current_pan = 0
current_tilt = 0
rec_status = 'stop'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/control')
def control():
    speed = int(request.args.get('speed', 0))
    angle = int(request.args.get('angle', 0))
    
    # 좌우 반전 해결: 전달받은 angle에 -1을 곱함
    fixed_angle = -angle 
    px.set_dir_servo_angle(fixed_angle)
    
    if speed >= 0:
        px.forward(speed)
    else:
        px.backward(abs(speed))
    return "OK"

@app.route('/camera')
def camera_control():
    global current_pan, current_tilt
    cmd = request.args.get('cmd')
    
    # 카메라 각도 조절
    step = 10
    if cmd == 'up': current_tilt -= step
    elif cmd == 'down': current_tilt += step
    elif cmd == 'left': current_pan += step
    elif cmd == 'right': current_pan -= step
    elif cmd == 'center': current_pan, current_tilt = 0, 0

    # 각도 제한 (-35 ~ 35)
    current_pan = max(min(current_pan, 35), -35)
    current_tilt = max(min(current_tilt, 35), -35)
    
    px.set_cam_pan_angle(current_pan)
    px.set_cam_tilt_angle(current_tilt)
    return jsonify(pan=current_pan, tilt=current_tilt)

@app.route('/record')
def record():
    global rec_status
    status = request.args.get('status')
    username = os.getlogin()
    Vilib.rec_video_set["path"] = f"/home/{username}/Videos/"

    if status == 'start' and rec_status == 'stop':
        rec_status = 'start'
        vname = strftime("%Y-%m-%d-%H.%M.%S", localtime())
        Vilib.rec_video_set["name"] = vname
        Vilib.rec_video_run()
        Vilib.rec_video_start()
        print(f"녹화 시작: {vname}")
    elif status == 'stop':
        rec_status = 'stop'
        Vilib.rec_video_stop()
        print("녹화 종료")
    return "OK"

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        px.stop()
        V