#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 DSO 输入端有没有信号(STM32 基准), 并粗略估周期/频率。
用法: python py/sigcheck.py [scaleh]
"""
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

SCALE = int(sys.argv[1]) if len(sys.argv) > 1 else 16

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


def cmd(typ, pay=b"", want=None, timeout=2.5, retries=4):
    want = typ if want is None else want
    for _ in range(retries):
        ser.reset_input_buffer()
        ser.write(g.build_frame(typ, pay))
        ser.flush()
        for t, pl in rf(timeout, want):
            if t == want:
                return pl
    return None


st = cmd(0x12, b"", 0x03)
if not st:
    print("读设置失败")
    raise SystemExit(1)
s = g.settings_from_bytes(st)
print("当前 scaleh=%d outuart=%d trimode=%d scalev_auto=%d" %
      (s["scaleh"], s["outuart"], s["trimode"], s["scalev_auto"]))

s["scaleh"] = SCALE
s["trimode"] = 0          # auto trigger
s["scalev_auto"] = 1
s["outuart"] = 1
ser.write(g.build_frame(0x10, g.settings_to_bytes(s)))
time.sleep(0.6)
rf(0.3)
print("已切到 scaleh=%d (%s)" % (SCALE, g.SCALE_H_TXT[SCALE]))
print("运行:", cmd(0x1C, bytes([1]), 0x02))


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


frames = []
t0 = time.time()
while time.time() - t0 < 4 and len(frames) < 6:
    for t, pl in rf(0.4):
        if t == 0x01:
            sp = g.parse_sample(pl)
            if sp is not None:
                frames.append(sp)

print("收到 %d 帧" % len(frames))
if frames:
    for i, f in enumerate(frames[:4]):
        raw = f["raw"]
        print("帧%d: min=%d max=%d p-p=%d 前16点=%s" % (i, min(raw), max(raw), max(raw) - min(raw), list(raw[:16])))
    per = psc(frames[-1]["raw"])
    nom = g.SCALE_H_SEC[SCALE] / 25.0
    print("估算周期样点数:", per, " 标称 dt=%.2fus" % (nom * 1e6))
    if per:
        print("按标称 dt 估算频率 ≈ %.2f Hz" % (1.0 / (per * nom)))
ser.close()
