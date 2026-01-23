import RPi.GPIO as GPIO
import time

# Robot Hat의 Ultrasonic 핀 번호를 직접 지정 (보통 BCM 24, 25 등 보드 확인 필요)
TRIG = 24 
ECHO = 25

GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

def get_dist():
    GPIO.output(TRIG, False)
    time.sleep(0.000002)
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)
    
    while GPIO.input(ECHO) == 0:
        start = time.time()
    while GPIO.input(ECHO) == 1:
        stop = time.time()
        
    return (stop - start) * 17000

print(f"직결 테스트 거리: {get_dist()} cm")