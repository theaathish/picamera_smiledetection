#!/usr/bin/env python3
"""Render the annotated AI feed (:8001) onto the SPI TFT (/dev/fb0, 320x480).
Fetches snapshots, resizes, converts to RGB565, writes framebuffer ~8fps.
Replaces fbcp-ili9341 (dead on Bookworm/KMS) with a direct fb writer.
"""
import cv2
import time
import urllib.request
import numpy as np

SRC = "http://127.0.0.1:8001/snapshot.jpg"
FB = "/dev/fb0"
W, H = 320, 480
PERIOD = 0.12


def fetch():
    try:
        with urllib.request.urlopen(SRC, timeout=5) as r:
            return r.read()
    except Exception:
        return None


def to_rgb565(bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.uint16)
    r = (rgb[:, :, 0] >> 3) << 11
    g = (rgb[:, :, 1] >> 2) << 5
    b = rgb[:, :, 2] >> 3
    return (r | g | b).astype(np.uint16).tobytes()


def main():
    fb = open(FB, "wb")
    n = 0
    t0 = time.time()
    print("fb renderer started -> /dev/fb0 320x480", flush=True)
    while True:
        ts = time.time()
        raw = fetch()
        if raw is None:
            time.sleep(0.3)
            continue
        img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            time.sleep(0.3)
            continue
        img = cv2.rotate(cv2.resize(img, (W, H)), cv2.ROTATE_180)
        fb.seek(0)
        fb.write(to_rgb565(img))
        fb.flush()
        n += 1
        if n % 40 == 0:
            print(f"frames={n} fps={n/(time.time()-t0):.1f}", flush=True)
        dt = time.time() - ts
        time.sleep(max(0, PERIOD - dt))


main()
