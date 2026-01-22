# 1. 라즈베리 파이용 파이썬 이미지 (ARM64 호환)
FROM python:3.11-slim-bookworm

# 2. 시스템 필수 패키지 설치 (git 추가됨)
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    alsa-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    i2c-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. SunFounder 하드웨어 라이브러리 설치
# (프로젝트 코드 복사 전에 미리 설치하는 것이 빌드 속도에 유리합니다)
#RUN git clone https://github.com/sunfounder/picar-x.git && \
#    cd picar-x && python3 setup.py install && cd .. && rm -rf picar-x

#RUN git clone https://github.com/sunfounder/vilib.git && \
#    cd vilib && python3 setup.py install && cd .. && rm -rf vilib
RUN pip install --no-cache-dir gpiozero RPi.GPIO
RUN pip install --no-cache-dir git+https://github.com/sunfounder/robot-hat.git
RUN pip install --no-cache-dir git+https://github.com/sunfounder/picar-x.git
RUN pip install --no-cache-dir git+https://github.com/sunfounder/vilib.git

# 4. 일반 파이썬 라이브러리 설치 (requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 사용자 소스 코드 복사
COPY . .

# 6. 포트 개방 (Flask: 5000, Vilib Stream: 9000)
EXPOSE 5000 9000

# 7. 실행 명령
CMD ["python", "app.py"]