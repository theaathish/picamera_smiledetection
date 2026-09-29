#!/bin/bash
# Download Haar cascade models (face + smile) onto the Pi.
set -e
mkdir -p ~/cascades
cd ~/cascades
BASE=https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades
curl -sL -o haarcascade_frontalface_default.xml "$BASE/haarcascade_frontalface_default.xml"
curl -sL -o haarcascade_smile.xml "$BASE/haarcascade_smile.xml"
ls -l ~/cascades/
head -c 15 haarcascade_frontalface_default.xml; echo
