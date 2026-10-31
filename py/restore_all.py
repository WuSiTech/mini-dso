#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""烧录后一键恢复 EEPROM 校准数据: 时基校准表(0x16) + DtTbl(0x22) + 保存(0x11)。
数据来源: 内置当前实测 CalTable; DtTbl 优先用 build/dtcal.json, 否则用内置实测值。
用法: python py/restore_all.py
"""
import json
import os
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

CAL = [15242, 9203, 6047, 4596, 3045, 1513, 896, 594, 436, 288,
       129, 72, 43, 32, 17, 20, 2, 6, 1, 1, 0]
DTT = [2127710, 1276656, 842095, 645127, 425527, 212761, 127664, 85103,
       62500, 42554, 20652, 12766, 8421, 6316, 4167, 1667, 1389, 844, 659, 889, 421]

jsonf = os.path.join("build", "dtcal.json")
if os.path.exists(jsonf):
    try:
        d = json.load(open(jsonf, encoding="utf-8"))["dt"]
        if len(d) == 21 and all(v > 0 for v in d):
            DTT = d
            print("DtTbl 来自", jsonf)
    except Exception as exc:
        print("读 dtcal.json 失败, 用内置值:", exc)

ser = serial.Serial("COM5", 115200, timeout=0.2)
p = g.FrameParser()


def rf(sec, want=None):
    out = []
    t0 = time.time()
    while time.time() - t0 < sec:
        d = ser.read(4096)
        if d:
            fr = p.feed(d)
            if fr:
                out += fr
                if want is not None and any(t == want for t, _ in fr):
                    break
    return out


def cmd(typ, pay=b"", want=None, timeout=3.0, retries=3):
    want = typ if want is None else want
    for _ in range(retries):
        ser.reset_input_buffer()
        ser.write(g.build_frame(typ, pay))
        ser.flush()
        for t, pl in rf(timeout, want):
            if t == want:
                return pl
    return None


def ack(typ, pay=b"", retries=3):
    for _ in range(retries):
        r = cmd(typ, pay, 0x02, 4.0)
        if r:
            return r[1]
    return None


info = cmd(0x19)
if info:
    print("固件 %d.%d.%d" % (info[0], info[1], info[2]))

print("0x16 写 CalTable:", "成功" if ack(0x16, b"".join(bytes([v & 0xFF, v >> 8]) for v in CAL)) else "失败")
print("0x22 写 DtTbl:  ", "成功" if ack(0x22, b"".join(bytes([(v >> s) & 0xFF for s in (0, 8, 16, 24)]) for v in DTT)) else "失败")
print("0x11 保存:      ", "成功" if ack(0x11) else "失败")

import struct
c = cmd(0x17)
d = cmd(0x21)
cb = [c[i * 2] | (c[i * 2 + 1] << 8) for i in range(21)] if c and len(c) >= 42 else None
db = list(struct.unpack("<21I", d[:84])) if d and len(d) >= 84 else None
print("回读 CalTable:", "一致" if cb == CAL else cb)
print("回读 DtTbl:  ", "一致" if db == DTT else db)
ser.close()
