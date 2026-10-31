#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测各 UART 命令是否回复: 0x12 GET / 0x19 INFO / 0x1F DTM / 0x21 DTT / 0x22 DTTW。"""
import struct
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
ser = serial.Serial(PORT, 115200, timeout=0.05)

H0, H1 = 0xA5, 0x5A


def build(t, pay=b""):
    fr = bytes([H0, H1, t, (len(pay) >> 8) & 0xFF, len(pay) & 0xFF]) + pay
    return fr + bytes([sum(fr[2:]) & 0xFF])


class P:
    def __init__(self):
        self.buf = b""

    def feed(self, d):
        self.buf += d
        out = []
        while True:
            i = self.buf.find(bytes([H0, H1]))
            if i < 0:
                self.buf = self.buf[-1:]
                break
            if i:
                self.buf = self.buf[i:]
            if len(self.buf) < 6:
                break
            t = self.buf[2]
            ln = (self.buf[3] << 8) | self.buf[4]
            if ln > 400:
                self.buf = self.buf[1:]
                continue
            if len(self.buf) < 6 + ln:
                break
            pay = self.buf[5:5 + ln]
            s = self.buf[5 + ln]
            if s == sum(self.buf[2:5 + ln]) & 0xFF:
                out.append((t, pay))
                self.buf = self.buf[6 + ln:]
            else:
                self.buf = self.buf[1:]
        return out


p = P()
ser.reset_input_buffer()
print("port", PORT, "open")

for name, typ, pay in [
    ("0x12 GET ", 0x12, b""),
    ("0x19 INFO", 0x19, b""),
    ("0x1F DTM ", 0x1F, b""),
    ("0x21 DTT ", 0x21, b""),
]:
    ser.reset_input_buffer()
    ser.write(build(typ, pay))
    t0 = time.time()
    got = []
    while time.time() - t0 < 1.0:
        d = ser.read(4096)
        if d:
            got += p.feed(d)
    cnt = {}
    for t, _ in got:
        cnt[t] = cnt.get(t, 0) + 1
    print("%s -> frames by type: %s" % (name, {("0x%02X" % k): v for k, v in sorted(cnt.items())}))
    for t, pl in got:
        if t != 0x01:
            print("     reply type=0x%02X len=%d %s" % (t, len(pl), pl.hex()))

ser.close()
