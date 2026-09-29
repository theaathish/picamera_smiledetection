#!/usr/bin/env python3
"""MJPEG HTTP server for Pi Camera (no picamera2 needed).
Runs rpicam-vid with MJPEG to stdout, splits JPEG frames,
serves multipart MJPEG on port 8000 for browsers.
Routes: / (viewer page), /stream.mjpg (MJPEG), /snapshot.jpg
"""
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

latest_frame = None
lock = threading.Lock()


def camera_loop():
    global latest_frame
    cmd = [
        "rpicam-vid", "-t", "0", "-n",
        "--width", "1280", "--height", "720",
        "--framerate", "15",
        "--codec", "mjpeg", "--quality", "70",
        "-o", "-",
    ]
    while True:
        proc = None
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            buf = bytearray()
            while True:
                chunk = proc.stdout.read(8192)
                if not chunk:
                    break
                buf.extend(chunk)
                while True:
                    start = buf.find(b"\xff\xd8")
                    end = buf.find(b"\xff\xd9")
                    if start >= 0 and end > start:
                        frame = bytes(buf[start:end + 2])
                        del buf[:end + 2]
                        with lock:
                            latest_frame = frame
                    else:
                        if len(buf) > 4_000_000:
                            del buf[:len(buf) - 2_000_000]
                        break
        except Exception as e:
            print("camera error:", e, flush=True)
        try:
            if proc is not None:
                proc.kill()
        except Exception:
            pass
        time.sleep(2)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            html = (
                b"<html><head><title>Pi Camera</title>"
                b"<meta name='viewport' content='width=device-width,initial-scale=1'>"
                b"</head><body style='margin:0;background:#111;color:#eee;font-family:sans-serif'>"
                b"<img src='/stream.mjpg' style='width:100vw;height:92vh;object-fit:contain;display:block'/>"
                b"<div style='padding:8px'>Pi Camera live (MJPEG 1280x720) - "
                b"<a style='color:#6cf' href='/stream.mjpg'>raw stream</a> | "
                b"<a style='color:#6cf' href='/snapshot.jpg'>snapshot</a></div>"
                b"</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif self.path == "/stream.mjpg":
            self.send_response(200)
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=FRAME"
            )
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                while True:
                    with lock:
                        frame = latest_frame
                    if frame is None:
                        time.sleep(0.05)
                        continue
                    header = (
                        b"--FRAME\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(frame)).encode()
                        + b"\r\n\r\n"
                    )
                    self.wfile.write(header + frame + b"\r\n")
                    time.sleep(1 / 15)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.path == "/snapshot.jpg":
            with lock:
                frame = latest_frame
            if frame is None:
                self.send_error(503, "no frame yet, try again")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
        else:
            self.send_error(404)


if __name__ == "__main__":
    threading.Thread(target=camera_loop, daemon=True).start()
    print("MJPEG server on :8000", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
