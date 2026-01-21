from flask import Flask, render_template, request, jsonify
from picarx import Picarx
from vilib import Vilib
import os
from time import strftime, localtime

app = Flask(__name__)
px = Picarx() #

# 카메라 초기화
try:
    Vilib.camera_start(vflip=False, hflip=False) #
    Vilib.display(local=False, web=True) #
except:
    pass

# 카메라 각도 상태 저장 변수
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
        px.set_dir_servo_angle(-35)
        px.forward(40)
    elif cmd == 'right':
        px.set_dir_servo_angle(35)
    elif cmd == 'stop':
        px.stop()
    return "OK"

@app.route('/camera')
def camera_control():
    global current_pan, current_tilt
    cmd = request.args.get('cmd')
    step = 10 # 한 번 누를 때 움직일 각도
    
    # [방향 교정 완료] 좌우 방향을 반대로 수정했습니다.
    if cmd == 'up': 
        current_tilt += step
    elif cmd == 'down': 
        current_tilt -= step
    elif cmd == 'left': 
        current_pan -= step
    elif cmd == 'right': 
        current_pan += step
    elif cmd == 'center': 
        current_pan, current_tilt = 0, 0

    # 각도 제한 (-35 ~ 35도)
    current_pan = max(min(current_pan, 35), -35)
    current_tilt = max(min(current_tilt, 35), -35)
    
    px.set_cam_pan_angle(current_pan)
    px.set_cam_tilt_angle(current_tilt)
    return "OK"

@app.route('/record')
def record():
    status = request.args.get('status')
    if status == 'start':
        username = os.getlogin() 
        save_path = f"/media/{username}/PIcarX_Video/"
        
        # 만약 폴더가 없다면 자동으로 생성하는 기능
        if not os.path.exists(save_path):
            os.makedirs(save_path)
            
        Vilib.rec_video_set["path"] = save_path
        Vilib.rec_video_set["name"] = strftime("%Y-%m-%d-%H.%M.%S", localtime())
        
        Vilib.rec_video_run()
        Vilib.rec_video_start()
    else:
        Vilib.rec_video_stop()
    return "OK"

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        px.stop() #