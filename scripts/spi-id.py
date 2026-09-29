#!/usr/bin/env python3
"""Probe TFT panel ID over SPI by sweeping DC/RST pin candidates.
Sends RDDID (0x04) + RDDST (0x09) and prints non-trivial responses.
HAT wiring unknown -> try common DC/RST GPIOs. Harmless: panel re-resets.
"""
import spidev
import subprocess
import time

PINS = [17, 22, 23, 24, 25, 26, 27]


def pin(pin, mode):
    subprocess.run(["pinctrl", "set", str(pin), mode],
                   capture_output=True)


def setup():
    for p in PINS:
        pin(p, "op")


def restore():
    for p in PINS:
        pin(p, "ip")


def read_id(spi, dc, rst):
    pin(rst, "dl")
    time.sleep(0.12)
    pin(rst, "dh")
    time.sleep(0.15)
    pin(dc, "dl")
    spi.xfer([0x04])
    pin(dc, "dh")
    rddid = spi.xfer([0x00] * 5)
    pin(dc, "dl")
    spi.xfer([0x09])
    pin(dc, "dh")
    rddst = spi.xfer([0x00] * 5)
    return rddid, rddst


def interesting(b):
    return not (all(v == 0 for v in b) or all(v == 0xFF for v in b))


def main():
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 2000000
    spi.mode = 0
    setup()
    hits = []
    try:
        for dc in PINS:
            for rst in PINS:
                if dc == rst:
                    continue
                try:
                    rddid, rddst = read_id(spi, dc, rst)
                except Exception:
                    continue
                if interesting(rddid) or interesting(rddst):
                    line = (f"DC={dc} RST={rst} "
                            f"RDDID={[hex(x) for x in rddid]} "
                            f"RDDST={[hex(x) for x in rddst]}")
                    print(line, flush=True)
                    hits.append(line)
    finally:
        restore()
    print(f"combos with signal: {len(hits)}", flush=True)


main()
