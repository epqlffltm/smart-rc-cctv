from flask import Flask, render_template, request, jsonify
from picarx import Picarx
from vilib import Vilib
import os
from time import strftime, localtime

app = Flask(__name__)
px = Picarx()

def init_camera():
    Vilib.camera_start(vflip=False, hflip=False)
    Vilib.display(local=False, web=True) #
    print("시스템: 카메라 및 웹 스트리밍 시작됨 (Port 9000)")

current_pan = 0
current_tilt = 0
rec_status = 'stop'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/move', methods=['POST'])
def move():
    data = request.json
    angle = data.get('angle', 0)
    speed = data.get('speed', 0)
    
    # 터미널에 로그 출력
    print(f"제어: 조향 {angle:.1f}, 속도 {speed:.1f}") #
    
    px.set_dir_servo_angle(angle)
    if speed > 0: px.forward(speed)
    elif speed < 0: px.backward(abs(speed))
    else: px.stop()
    return jsonify(status="success")

@app.route('/camera', methods=['POST'])
def camera_control():
    global current_pan, current_tilt
    data = request.json
    action = data.get('action')
    
    if action == 'left': current_pan += 10
    elif action == 'right': current_pan -= 10
    elif action == 'up': current_tilt -= 10
    elif action == 'down': current_tilt += 10
    elif action == 'center': current_pan, current_tilt = 0, 0
    
    current_pan = max(min(current_pan, 35), -35)
    current_tilt = max(min(current_tilt, 35), -35)
    
    # 터미널에 로그 출력
    print(f"카메라: Pan {current_pan}, Tilt {current_tilt}") #
    
    px.set_cam_pan_angle(current_pan)
    px.set_cam_tilt_angle(current_tilt)
    return jsonify(pan=current_pan, tilt=current_tilt)

@app.route('/record', methods=['POST'])
def record_video():
    global rec_status
    username = os.getlogin()
    Vilib.rec_video_set["path"] = f"/home/{username}/Videos/"

    if rec_status == 'stop':
        rec_status = 'start'
        vname = strftime("%Y-%m-%d-%H.%M.%S", localtime())
        Vilib.rec_video_set["name"] = vname
        Vilib.rec_video_run()
        Vilib.rec_video_start()
        print(f"녹화: 시작됨 -> {vname}.avi") #
        return jsonify(status="recording")
    else:
        rec_status = 'stop'
        Vilib.rec_video_stop()
        print("녹화: 중지 및 저장 완료") #
        return jsonify(status="stopped")

if __name__ == '__main__':
    try:
        init_camera()
        print("시스템: Flask 서버 가동 중... (Port 5000)")
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\n시스템: 사용자에 의해 종료됨")
    finally:
        px.stop()
        Vilib.camera_close() # 여기서 발생하는 OpenCV 에러는 무시해도 좋습니다.
        print("시스템: 모든 하드웨어 연결 종료")