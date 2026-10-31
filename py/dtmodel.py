#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读写延时模型系数(EEPROM): A1 B1 A2 B2 THR
用法:
  python py/dtmodel.py                # 读取
  python py/dtmodel.py 12955 1800 14258 1550 300   # 写入
"""
import struct
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

T_DTM, T_DTMW = 0x1F, 0x20
ser = serial.Serial("COM5", 115200, timeout=0.3)
p = g.FrameParser()


def rf(sec):
    out = []
    t0 = time.time()
    while time.time() - t0 < sec:
        d = ser.read(1024)
        if d:
            out += p.feed(d)
    return out


if len(sys.argv) >= 6:
    vals = [int(x) for x in sys.argv[1:6]]
    pay = b"".join(struct.pack("<H", max(0, min(65535, v))) for v in vals)
    ser.write(g.build_frame(T_DTMW, pay))
    time.sleep(0.2)
    ok = 0
    for t, pl in rf(3.0):
        if t == 0x02 and len(pl) >= 2:
            ok = pl[1]
    print("写入:", "成功" if ok else "失败")
else:
    ser.write(g.build_frame(T_DTM))
    time.sleep(0.2)
    got = None
    for t, pl in rf(4.0):
        if t == T_DTM and len(pl) >= 10:
            got = struct.unpack("<5H", pl[:10])
    print("当前系数 A1,B1,A2,B2,THR =", got)
ser.close()
