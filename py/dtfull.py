#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全档位 DtTbl 校准: 自动切换 STM32 基准频率 -> 测各档采样间隔 -> 写 EEPROM
   (烧录后 EEPROM 被擦, DtTbl 会回默认值, 跑这个恢复实测值)"""
import os
import struct
import subprocess
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SETFREQ = os.path.join(HERE, "refgen", "setfreq.py")

GROUPS = [
    (5.0, [0, 1, 2, 3, 4]),
    (50.0, [5, 6, 7, 8, 9]),
    (1000.0, [10, 11, 12, 13, 14]),
    (3000.0, [15, 16, 17, 18]),
    (10000.0, [19, 20]),
]

ser = serial.Serial("COM5", 115200, timeout=0.5)
p = g.FrameParser()


def rf(sec):
    out = []
    t0 = time.time()
    while time.time() - t0 < sec:
        d = ser.read(1024)
        if d:
            out += p.feed(d)
    return out


def getset():
    ser.write(g.build_frame(0x12))
    time.sleep(0.2)
    for t, pl in rf(2.5):
        if t == 0x03:
            return g.settings_from_bytes(pl)


def getdt():
    ser.write(g.build_frame(0x21))
    time.sleep(0.2)
    for t, pl in rf(4.0):
        if t == 0x21 and len(pl) >= 84:
            return list(struct.unpack("<21I", pl[:84]))


def write_dt(dt):
    pay = b"".join(struct.pack("<I", v) for v in dt)
    for _ in range(5):
        ser.write(g.build_frame(0x22, pay))
        time.sleep(0.4)
        t0 = time.time()
        while time.time() - t0 < 6:
            for t, pl in rf(0.4):
                if t == 0x02 and len(pl) >= 2 and pl[1]:
                    return True
    return False


def ps(raw):
    lo, hi = min(raw), max(raw)
    if hi - lo < 15:
        return 0
    mid = (lo + hi) / 2.0
    up, dn = mid + (hi - lo) * 0.2, mid - (hi - lo) * 0.2
    armed, cr = False, []
    for i in range(1, len(raw)):
        a, b = raw[i - 1], raw[i]
        if not armed and b < dn:
            armed = True
        elif armed and b > up:
            armed = False
            if b != a:
                cr.append(i - 1 + (mid - a) / (b - a))
    return (cr[-1] - cr[0]) / (len(cr) - 1) if len(cr) > 1 else 0


def measure(idx, F):
    s = getset()
    s["scaleh"] = idx
    s["trimode"] = 0
    s["scalev_auto"] = 1
    ser.write(g.build_frame(g.T_SET, g.settings_to_bytes(s)))
    time.sleep(0.6)
    rf(0.4)
    vals = []
    t0 = time.time()
    while time.time() - t0 < 10 and len(vals) < 3:
        for t, pl in rf(0.5):
            if t == 0x01:
                sp = g.parse_sample(pl)
                if sp:
                    v = ps(sp["raw"])
                    if 6 <= v <= 110:
                        vals.append(v)
    if not vals:
        return None
    return (1.0 / F) / sorted(vals)[len(vals) // 2]


dt = getdt()
if not dt:
    print("读表失败")
    sys.exit(1)
print("起始表[0..4]:", dt[:5])

for F, idxs in GROUPS:
    r = subprocess.run([sys.executable, SETFREQ, str(F)], capture_output=True, text=True)
    if r.returncode != 0:
        print("设置基准 %.0fHz 失败: %s" % (F, (r.stderr or "").strip()[:100]))
        continue
    time.sleep(1.0)
    print("== 基准 %.0f Hz ==" % F)
    for idx in idxs:
        d = measure(idx, F)
        if d is None:
            print("   档%2d 测不到" % idx)
            continue
        old = dt[idx]
        dt[idx] = int(round(d * 1e8))
        print("   档%2d: %.2fus  表 %d -> %d" % (idx, d * 1e6, old, dt[idx]))

ok = write_dt(dt)
print("写入:", "成功" if ok else "失败")
print("最终表:", dt)

# 恢复 1kHz 基准
subprocess.run([sys.executable, SETFREQ, "1000"], capture_output=True, text=True)
ser.close()
