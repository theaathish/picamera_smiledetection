#!/usr/bin/env python3
"""Face + smile detection for Pi 3 (Haar cascades, CPU-light).

Polls the local MJPEG server (127.0.0.1:8000/snapshot.jpg), uprights the
sideways-mounted camera frame, detects faces then smiles inside each face
ROI, and serves an annotated MJPEG stream on :8001.
Events appended to /tmp/face_events.log
"""
import cv2
cv2.setNumThreads(2)  # don't starve rpicam-vid on the Pi 3's 4 cores
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FACE_XML = "/home/adhi/cascades/haarcascade_frontalface_default.xml"
SMILE_XML = "/home/adhi/cascades/haarcascade_smile.xml"
SRC = "http://127.0.0.1:8000/snapshot.jpg"

# Camera is mounted sideways (head points right) -> rotate CCW to upright.
# If boxes look wrong, flip to cv2.ROTATE_90_CLOCKWISE or None.
ROTATE = cv2.ROTATE_90_COUNTERCLOCKWISE

# Detection resolution (small = fast). 240x320 preserves the rotated aspect.
DET_W, DET_H = 240, 320
PERIOD = 0.2  # target ~5 fps
OUT_W = 480  # downscale served images (display is 480x320 anyway)

face_cascade = cv2.CascadeClassifier(FACE_XML)
smile_cascade = cv2.CascadeClassifier(SMILE_XML)
print("face cascade loaded:", not face_cascade.empty(), flush=True)
print("smile cascade loaded:", not smile_cascade.empty(), flush=True)

latest_jpg = None
stats = {"faces": 0, "smiles": 0, "fps": 0.0}
lock = threading.Lock()


def fetch():
    try:
        with urllib.request.urlopen(SRC, timeout=5) as r:
            return r.read()
    except Exception:
        return None


def detect_loop():
    global latest_jpg
    import numpy as np
    last = time.time()
    while True:
        t0 = time.time()
        raw = fetch()
        if raw is None:
            time.sleep(0.3)
            continue
        img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            time.sleep(0.3)
            continue
        if ROTATE is not None:
            img = cv2.rotate(img, ROTATE)
        small = cv2.resize(img, (DET_W, DET_H))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)  # helps NoIR washed-out tones
        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.3, minNeighbors=4, minSize=(30, 30)
        )
        smiles = 0
        sx = img.shape[1] / float(DET_W)
        sy = img.shape[0] / float(DET_H)
        for (x, y, w, h) in faces:
            X, Y, W, H = int(x * sx), int(y * sy), int(w * sx), int(h * sy)
            cv2.rectangle(img, (X, Y), (X + W, Y + H), (0, 255, 0), 2)
            # mouth ROI from FULL-RES frame (more pixels = better hits)
            mx0, my0 = X + W // 10, Y + int(H * 0.55)
            mx1, my1 = X + W * 9 // 10, Y + int(H * 0.95)
            mouth = img[max(my0, 0):my1, max(mx0, 0):mx1]
            if mouth.size:
                mg = cv2.cvtColor(mouth, cv2.COLOR_BGR2GRAY)
                mg = cv2.equalizeHist(mg)
                found = smile_cascade.detectMultiScale(
                    mg, scaleFactor=1.3, minNeighbors=12, minSize=(12, 12)
                )
                if len(found):
                    smiles += 1
                    cv2.putText(img, "SMILE", (X, max(Y - 8, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        out = img
        if out.shape[1] > OUT_W:
            sc = OUT_W / float(out.shape[1])
            out = cv2.resize(out, (OUT_W, int(out.shape[0] * sc)))
        ok, jpg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 70])
        now = time.time()
        with lock:
            if ok:
                latest_jpg = jpg.tobytes()
            stats.update(faces=len(faces), smiles=smiles,
                         fps=1.0 / max(now - last, 1e-3))
        last = now
        with open("/tmp/face_events.log", "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} faces={len(faces)} smiles={smiles}\n")
        dt = time.time() - t0
        time.sleep(max(0, PERIOD - dt))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/":
            with lock:
                s = dict(stats)
            html = (
                "<html><head><title>Face+Smile</title>"
                "<meta http-equiv='refresh' content='5'></head>"
                f"<body style='margin:0;background:#111;color:#eee;font-family:sans-serif'>"
                f"<img src='/stream.mjpg' style='width:100vw;height:88vh;object-fit:contain'/>"
                f"<div style='padding:8px'>faces={s['faces']} smiles={s['smiles']} "
                f"detect-fps={s['fps']:.1f}</div></body></html>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif self.path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=FRAME")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    with lock:
                        frame = latest_jpg
                    if frame is None:
                        time.sleep(0.1)
                        continue
                    self.wfile.write(
                        b"--FRAME\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
                    time.sleep(0.2)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.path == "/snapshot.jpg":
            with lock:
                frame = latest_jpg
            if frame is None:
                self.send_error(503, "warming up")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
        else:
            self.send_error(404)


threading.Thread(target=detect_loop, daemon=True).start()
print("face+smile server on :8001", flush=True)
ThreadingHTTPServer(("0.0.0.0", 8001), Handler).serve_forever()
