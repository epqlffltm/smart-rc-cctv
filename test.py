from picarx import Picarx
import time

px = Picarx()

try:
    while True:
        dist = px.ultrasonic.read()
        print(f"현재 측정 거리: {dist} cm", flush=True)
        time.sleep(0.5)
except KeyboardInterrupt:
    pass