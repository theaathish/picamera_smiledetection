#!/usr/bin/env python3
"""Probe which SPI chip-select has a live chip (XPT2046 touch?).
Reads XPT2046 X/Y/Z1 channels on both CS0 and CS1, prints raw bytes.
Live chip => varying non-trivial bytes. Touch needs no init.
"""
import spidev
import time


def read_ch(spi, cmd):
    return spi.xfer([cmd, 0x00, 0x00])


for cs in (1, 0):
    try:
        spi = spidev.SpiDev()
        spi.open(0, cs)
        spi.max_speed_hz = 2000000
        spi.mode = 0
        print(f"--- CS{cs} ---", flush=True)
        for name, cmd in (("X", 0x90), ("Y", 0xD0), ("Z1", 0xB0)):
            vals = []
            for _ in range(3):
                r = read_ch(spi, cmd)
                vals.append("-".join(f"{b:02x}" for b in r))
                time.sleep(0.05)
            print(f"{name}: {vals}", flush=True)
        spi.close()
    except Exception as e:
        print(f"CS{cs} error: {e}", flush=True)
