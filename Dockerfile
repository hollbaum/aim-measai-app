FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY room_daemon.py room_viewer.py start.sh ./
COPY seed_rooms ./seed_rooms
RUN chmod +x start.sh

ENV ROOMS_DIR=/data/rooms
ENV DEFAULT_SENDER=Guest
ENV PORT=8000

EXPOSE 8000

VOLUME ["/data/rooms"]

CMD ["./start.sh"]
