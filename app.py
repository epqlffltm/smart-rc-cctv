from flask import Flask, render_template, request
from picarx import Picarx
import math

app = Flask(__name__)
px = Picarx()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/control')
def control():
    # 1. 조이스틱 데이터(각도, 거리) 받기
    angle = request.args.get('angle', type=float)
    distance = request.args.get('distance', type=float)
    command = request.args.get('command')

    # 정지 명령 처리
    if command == 'stop':
        px.stop()
        px.set_dir_servo_angle(0)
        return "Stopped"

    if angle is not None and distance is not None:
        # 조이스틱 각도에 따른 방향 설정 (-30 ~ 30도 사이로 매핑)
        # 90도(위)를 기준으로 왼쪽/오른쪽 계산
        steering = 0
        if 0 <= angle <= 180: # 전진 방향 영역
            # 90도(정면)에서 얼마나 벗어났는지 계산하여 서보 각도 조절
            steering = (90 - angle) * 0.6  # 0.6은 감도 조절값
            px.set_dir_servo_angle(steering)
            px.forward(int(distance))
        elif 181 <= angle <= 360: # 후진 방향 영역
            steering = (angle - 270) * 0.6
            px.set_dir_servo_angle(steering)
            px.backward(int(distance))

    return "OK"

if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, threaded=True)
    finally:
        px.stop()