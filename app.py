from flask import Flask, render_template, request, jsonify
from picarx import Picarx
from vilib import Vilib
import os
from time import strftime, localtime

app = Flask(__name__)

# Picar-X 및 카메라 초기화
px = Picarx()
try:
    Vilib.camera_start(vflip=False, hflip=False)
    Vilib.display(local=False, web=True)
except Exception as e:
    print(f"카메라 초기화 중 경고(무시 가능): {e}")

# 상태 변수
current_pan = 0
current_tilt = 0
rec_status = 'stop'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/control')
def control():
    # 속도와 각도를 받아옵니다.
    speed = int(request.args.get('speed', 0))
    angle = int(request.args.get('angle', 0))
    
    # [수정됨] 좌우 반전 로직 제거 (angle 값 그대로 사용)
    px.set_dir_servo_angle(angle)
    
    if speed >= 0:
        px.forward(speed)
    else:
        px.backward(abs(speed)) # 음수면 절댓값으로 후진
    return "OK"

@app.route('/camera')
def camera_control():
    global current_pan, current_tilt
    cmd = request.args.get('cmd')
    step = 10
    
    # [수정됨] 카메라 방향 정방향으로 수정
    # Picar-X 기준: 각도가 커지면 위/왼쪽, 작아지면 아래/오른쪽
    if cmd == 'up': current_tilt += step      # 증가(+)로 변경
    elif cmd == 'down': current_tilt -= step  # 감소(-)로 변경
    elif cmd == 'left': current_pan += step   # 증가(+)로 변경
    elif cmd == 'right': current_pan -= step  # 감소(-)로 변경
    elif cmd == 'center': current_pan, current_tilt = 0, 0

    # 각도 제한 (-35 ~ 35)
    current_pan = max(min(current_pan, 35), -35)
    current_tilt = max(min(current_tilt, 35), -35)
    
    px.set_cam_pan_angle(current_pan)
    px.set_cam_tilt_angle(current_tilt)
    return jsonify(pan=current_pan, tilt=current_tilt)

# ... (녹화 기능 /record는 기존과 동일합니다) ...
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
        # use_reloader=False로 카메라 중복 점유 방지
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        px.stop()
        # Vilib.camera_close()는 생략하여 종료 시 에러 방지