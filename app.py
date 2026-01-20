from flask import Flask, render_template, request, jsonify
from picarx import Picarx
from vilib import Vilib
import os
from time import strftime, localtime

app = Flask(__name__)
px = Picarx()

# 카메라 초기화 (에러 방지용 try-except)
try:
    Vilib.camera_start(vflip=False, hflip=False)
    Vilib.display(local=False, web=True)
except:
    pass

current_pan = 0
current_tilt = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/control')
def control():
    speed = int(request.args.get('speed', 0))
    angle = int(request.args.get('angle', 0))
    
    # [방향 교정] 조향 각도가 반대로 작동한다면 여기서 -angle로 수정
    px.set_dir_servo_angle(-angle) 
    
    if speed >= 0:
        px.forward(speed)
    else:
        px.backward(abs(speed))
    return "OK"

@app.route('/camera')
def camera_control():
    global current_pan, current_tilt
    cmd = request.args.get('cmd')
    step = 10
    # 카메라 모터 방향 교정
    if cmd == 'up': current_tilt += step
    elif cmd == 'down': current_tilt -= step
    elif cmd == 'left': current_pan += step
    elif cmd == 'right': current_pan -= step
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