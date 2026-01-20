from flask import Flask, render_template, request, Response
from picarx import PicarX
from vilib import Vilib
import time

app = Flask(__name__)

# PiCar-X 및 카메라 초기화
px = PicarX()
Vilib.camera_start(vflip=False, hflip=False)
Vilib.display(local=False, web=True) # 웹 스트리밍 활성화

@app.route('/')
def index():
    return render_template('index.html')

# 주행 제어 (조이스틱 데이터 처리)
@app.route('/control')
def control():
    direction = request.args.get('dir')
    speed = int(request.args.get('speed', 0))
    angle = int(request.args.get('angle', 0))

    if direction == 'move':
        px.set_dir_servo_angle(angle)
        px.forward(speed)
    elif direction == 'stop':
        px.forward(0)
    return "OK"

# 카메라 방향 제어 (Pan/Tilt)
@app.route('/camera')
def camera_control():
    cmd = request.args.get('cmd')
    # 현재 각도를 읽어와서 조절 (예시 각도)
    if cmd == 'up':
        px.set_camera_tilt_angle(10) # 실제 구현시 현재값 + 알파 필요
    elif cmd == 'down':
        px.set_camera_tilt_angle(-10)
    return "OK"

# 녹화 기능
@app.route('/record')
def record():
    status = request.args.get('status')
    if status == 'start':
        Vilib.video_record('picar_video')
    else:
        Vilib.video_stop_record()
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)