# PiCamera SmileDetection 🤖📷

Smart-camera system on a **Raspberry Pi 3 Model B+**: CSI camera → MJPEG stream →
face + smile detection overlay → 3.5" SPI TFT display + browser viewers.
Built and tuned over a live SSH session (WiFi hotspot networking, Bookworm 64-bit).

## Hardware

| Part | Detail |
|---|---|
| Board | Raspberry Pi 3 Model B Plus Rev 1.3, Debian 12 (bookworm) arm64 |
| Camera | Raspberry Pi Camera Module 3 NoIR (IMX708, `imx708_noir`, 4608×2592) |
| Display | 3.5" RPi TFT, 480×320, XPT2046 touch, **ILI9486** driver (`waveshare35a` overlay) |
| Network | WiFi (`wlan0`), DHCP — Pi IP changes between networks, find via MAC `b8:27:eb:80:4d:95` |

## Architecture

```
rpicam-vid (MJPEG 1280x720@15, /dev/video)
   └─> mjpeg-server.py ── :8000 ── raw camera MJPEG (+/snapshot.jpg)
          └─> face-smile.py ── :8001 ── annotated MJPEG: green face boxes,
                yellow SMILE tags, detect-fps counter (+/snapshot.jpg)
                 └─> fb-display.py ── /dev/fb0 (320x480 RGB565, ~8fps)
```

- `scripts/mjpeg-server.py` — wraps `rpicam-vid --codec mjpeg -o -`, splits JPEG
  frames, serves multipart MJPEG. No picamera2 needed.
- `scripts/face-smile.py` — polls `:8000`, upright-rotates the sideways-mounted
  frame, Haar `frontalface` + `smile` on a **full-res mouth crop**, serves `:8001`.
- `scripts/fb-display.py` — renders the `:8001` feed to the TFT framebuffer
  (fbcp-ili9341 is dead on Bookworm/KMS — this replaces it).
- `scripts/spi-id.py` / `touch-probe.py` — one-off SPI diagnostics (panel ID sweep,
  XPT2046 touch probe on CS1).

## Pi setup

```bash
# OS deps (Bookworm). NOTE: libcamera-dev and xxd are required but easy to miss.
sudo apt update
sudo apt install -y git cmake build-essential libssl-dev \
  libavformat-dev libavcodec-dev libswscale-dev libavutil-dev \
  libcamera-dev xxd python3-opencv python3-spidev

# Haar cascade models (~1.1 MB)
bash setup/setup_cascades.sh   # -> ~/cascades/*.xml

# SPI display (needs one reboot)
bash setup/display-setup.sh
sudo reboot
# verify: ls /dev/spidev*  /dev/fb*   (want spidev0.0/0.1 + fb0 = 320x480 ili9486)
```

Manual run (in order — each depends on the previous):

```bash
nohup python3 scripts/mjpeg-server.py > /tmp/mjpeg.log 2>&1 &
sleep 5
nohup python3 scripts/face-smile.py   > /tmp/face.log 2>&1 &
nohup python3 scripts/fb-display.py   > /tmp/fb.log 2>&1 &
# watch: http://<pi-ip>:8000  (raw)   http://<pi-ip>:8001  (faces/smiles)
```

Auto-start with systemd:

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now picam-mjpeg.service picam-face.service picam-display.service
```

## Key tuning notes (learned the hard way)

- **Sideways camera**: frame needs `ROTATE_90_COUNTERCLOCKWISE` before detection —
  Haar cascades never fire on sideways faces. TFT needed an extra `ROTATE_180`
  (diagnosed with a red/green/blue/white quadrant card: corners came back rotated).
- **Smile needs pixels**: detect on a full-res mouth crop (55–95% H, 10–90% W),
  `scaleFactor=1.3, minNeighbors=12` — the tiny-preview ROI never fired.
- **NoIR tones**: `equalizeHist` before detection; keep subjects ≥1m (autofocus
  VCM `dw9807` errors — focus is effectively fixed).
- **`vcgencmd get_camera` reads `detected=0`** on Bookworm — normal (legacy stack
  off); camera works via libcamera/rpicam.
- **CPU budget** (Pi 3, quad-core %): rpicam ~40 + detect ~30–70 + fb-write ~35–50
  of one core each ≈ 25–35% machine. `cv2.setNumThreads(2)` in the detector.
- **fbcp-ili9341 does NOT work on Bookworm** (author-declared EOL: DispmanX is gone
  under KMS). Kernel `waveshare35a` (fbtft `fb_ili9486`) + direct fb writes used.
- **Shell footgun**: `pkill -f <name>` matches its own `bash -c` command line over
  SSH and kills the session — use bracket patterns (`pkill -f '[f]ace-smile[.]py'`)
  and keep pkill in a separate SSH call from the command containing the name.
- **Boot**: trimmed 19.4s → 15.7s (BT/hciuart/ModemManager/triggerhappy off,
  `boot_delay=0`, `quiet`, NM wait-online timeout 10s). Kept fsck + avahi.
- Verify pipeline with `samples`: `haarcascade_frontalface` finds 1 face in
  OpenCV's `lena.jpg`; neutral mouth correctly yields 0 smiles.

## Layout

```
scripts/   the five Python programs (synced from the live Pi)
systemd/   auto-start units (mjpeg -> face -> display chain)
setup/     cascade downloader + display overlay installer
```

> Display photos, DNGs and logs from the bring-up session are not committed.
> If the Pi was re-imaged, re-sync `scripts/` from `/home/adhi/` (live fixes land there first).
