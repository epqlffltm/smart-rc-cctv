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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/control')
def control():
    speed = int(request.args.get('speed', 0))
    angle = int(request.args.get('angle', 0))
    
    # 조향: 왼쪽은 -, 오른쪽은 + (반대라면 angle 앞의 -를 제거하세요)
    px.set_dir_servo_angle(-angle) 
    
    # [방향 확정] speed가 양수면 전진, 음수면 후진
    if speed > 0:
        px.forward(speed)
    elif speed < 0:
        px.backward(abs(speed))
    else:
        px.stop()
    return "OK"

@app.route('/camera')
def camera_control():
    cmd = request.args.get('cmd')
    # 카메라 모터 제어 (생략 가능하나 기능 유지를 위해 포함)
    if cmd == 'up': px.set_cam_tilt_angle(20)
    elif cmd == 'down': px.set_cam_tilt_angle(-20)
    elif cmd == 'center': 
        px.set_cam_tilt_angle(0)
        px.set_cam_pan_angle(0)
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)