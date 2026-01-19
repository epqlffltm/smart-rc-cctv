from flask import Flask, render_template, request
from picarx import Picarx
import time

app = Flask(__name__)
px = Picarx()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/control')
def control():
    command = request.args.get('command')
    
    if command == 'forward':
        px.forward(30)
    elif command == 'backward':
        px.backward(30)
    elif command == 'left':
        px.set_dir_servo_angle(-30)
    elif command == 'right':
        px.set_dir_servo_angle(30)
    elif command == 'stop':
        px.stop()
        px.set_dir_servo_angle(0)
    
    return "OK"

if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000)
    finally:
        px.stop()