#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按档位比例校准(不做全局拟合): 每档测 dt, 用 x_new = x_old * (dt_nom/dt_meas)
用法: python py/tbcal3.py <f_ref> <idx0> <idx1> [--write]"""
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

F = float(sys.argv[1])
I0, I1 = int(sys.argv[2]), int(sys.argv[3])
WRITE = "--write" in sys.argv

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


def getset():
    ser.write(g.build_frame(0x12))
    time.sleep(0.2)
    for t, pl in rf(2.5):
        if t == 0x03:
            return g.settings_from_bytes(pl)


def getcal():
    ser.write(g.build_frame(0x17))
    time.sleep(0.2)
    for t, pl in rf(4.0):
        if t == 0x17 and len(pl) >= 42:
            return [pl[i * 2] | (pl[i * 2 + 1] << 8) for i in range(21)]


def psc(raw):
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


tbl = getcal()
cur = getset()
new = list(tbl)
for idx in range(I0, I1 + 1):
    s = dict(cur)
    s["scaleh"] = idx
    s["trimode"] = 0
    s["scalev_auto"] = 1
    ser.write(g.build_frame(g.T_SET, g.settings_to_bytes(s)))
    time.sleep(0.5)
    rf(0.3)
    vals = []
    t0 = time.time()
    while time.time() - t0 < 10 and len(vals) < 3:
        for t, pl in rf(0.5):
            if t == 0x01:
                sp = g.parse_sample(pl)
                if sp:
                    v = psc(sp["raw"])
                    if 6 <= v <= 120:
                        vals.append(v)
    if not vals:
        print("档 %2d: 测不到, 跳过" % idx)
        continue
    v = sorted(vals)[len(vals) // 2]
    dt = (1.0 / F) / v
    dt_nom = g.SCALE_H_SEC[idx] / 25.0
    ratio = dt_nom / dt
    old = tbl[idx]
    nv = max(0, min(65535, int(round(old * ratio))))
    new[idx] = nv
    print("档 %2d (%s): 实测 %8.1fus 标称 %8.1fus 比例 %.3f  表 %5d -> %5d"
          % (idx, g.SCALE_H_TXT[idx], dt * 1e6, dt_nom * 1e6, ratio, old, nv))

if WRITE:
    pay = b"".join(bytes([v & 0xFF, (v >> 8) & 0xFF]) for v in new)
    ser.write(g.build_frame(0x16, pay))
    time.sleep(0.2)
    ok = 0
    for t, pl in rf(3.0):
        if t == 0x02 and len(pl) >= 2:
            ok = pl[1]
    ser.write(g.build_frame(0x11))
    rf(1.0)
    print("写入:", "成功" if ok else "失败")
else:
    print("(预览) 新表:", new)
ser.close()
