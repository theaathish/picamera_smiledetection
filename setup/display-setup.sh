#!/bin/bash
# 3.5" RPi TFT (ILI9486, XPT2046) on Bookworm: vendor overlay + SPI.
# Run ONCE on the Pi, then reboot. Display becomes /dev/fb0 (320x480).
set -e
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.pre-lcd
cd /tmp
curl -sL -o Waveshare35a.zip https://files.waveshare.com/wiki/common/Waveshare35a.zip
unzip -o Waveshare35a.zip waveshare35a.dtbo
sudo cp waveshare35a.dtbo /boot/overlays/
if ! grep -q 'dtparam=spi=on' /boot/firmware/config.txt; then
  echo 'dtparam=spi=on' | sudo tee -a /boot/firmware/config.txt
else
  sudo sed -i 's/^#dtparam=spi=on/dtparam=spi=on/' /boot/firmware/config.txt
fi
if ! grep -q 'dtoverlay=waveshare35a' /boot/firmware/config.txt; then
  printf '\n# 3.5inch RPi LCD (A) - ILI9486\n dtoverlay=waveshare35a:rotate=0\n' \
    | sed 's/^ //' | sudo tee -a /boot/firmware/config.txt
fi
echo 'OK. Reboot, then verify: ls /dev/fb* ; dmesg | grep fb_ili9486'
