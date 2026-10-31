#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成器输出频率校准: 把 PWM/SIN 环接回示波器 INPUT, 用已校准的频响读数闭环修正
   - 方波 15 档 -> OutOff[0..14] (周期偏移, 0.1us)
   - 波形 6 档  -> OutOff[15..20]
用法: python py/wavecal.py sq   |   python py/wavecal.py wv
"""
import struct
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

GROUP = sys.argv[1] if len(sys.argv) > 1 else "sq"
SQ_HZ = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 18000, 42000]
WV_HZ = [8.8, 17.6, 35.2, 70.4, 140.8, 281.6]
# 该档频率对应的"每周期采样点数合适"的时基档(标称秒/格序号)
SQ_TB = [0, 0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 20]
WV_TB = [6, 6, 7, 9, 10, 11]

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


def req(typ, pay=b"", sec=1.2):
    ser.write(g.build_frame(typ, pay))
    time.sleep(0.1)
    return rf(sec)


def getset():
    for t, pl in req(0x12, sec=2.5):
        if t == 0x03:
            return g.settings_from_bytes(pl)


def setset(s):
    ser.write(g.build_frame(g.T_SET, g.settings_to_bytes(s)))
    time.sleep(0.4)
    rf(0.2)


def read_off():
    for t, pl in req(0x1D, sec=4.0):
        if t == 0x1D and len(pl) >= 42:
            return list(struct.unpack("<21h", pl[:42]))


def write_off(vals):
    pay = b"".join(struct.pack("<h", max(-30000, min(30000, int(v)))) for v in vals)
    for _ in range(4):
        ser.write(g.build_frame(0x1E, pay))
        time.sleep(0.4)
        for t, pl in rf(3.0):
            if t == 0x02 and len(pl) >= 2 and pl[1]:
                return True
    return False


def pick_tb(period_us, dttbl):
    want = period_us / 30.0 * 100.0      # 0.01us
    best, bd = 9, 1e18
    for i in range(21):
        dt = dttbl[i]
        if dt <= 0:
            continue
        # 至少 2 个周期进缓冲, 且采样间隔 < 周期/4
        if 220.0 * dt < 2.0 * period_us * 100.0:
            continue
        d = abs(dt - want)
        if d < bd:
            bd, best = d, i
    return best


def measure(idx_gen, tb, group, target_hz):
    """把 DSO 设到该档时基, 读报出的频率"""
    s = getset()
    if not s:
        return 0
    s["scaleh"] = tb
    s["trimode"] = 0
    s["scalev_auto"] = 1
    if group == "sq":
        s["outpwm"] = 1
        s["outsin"] = 0
        s["genfreq"] = idx_gen
    else:
        s["outpwm"] = 1
        s["outsin"] = 1
        s["wavetype"] = 0
        s["wavescroll"] = idx_gen
    setset(s)
    time.sleep(0.5)
    rf(0.3)
    fs = []
    t0 = time.time()
    while time.time() - t0 < 8 and len(fs) < 4:
        for t, pl in rf(0.5):
            if t == 0x01:
                sp = g.parse_sample(pl)
                if sp and sp["freq"]:
                    fs.append(sp["freq"])
    if not fs:
        return 0
    fs = sorted(fs)
    return fs[len(fs) // 2]


def read_dt():
    for t, pl in req(0x21, sec=4.0):
        if t == 0x21 and len(pl) >= 84:
            return list(struct.unpack('<21I', pl[:84]))
    return None


off = read_off()
if off is None:
    print("读偏移表失败")
    sys.exit(1)
DTT = read_dt() or [100] * 21
print("DtTbl ok:", len(DTT))

HZ = SQ_HZ if GROUP == "sq" else WV_HZ
TB = SQ_TB if GROUP == "sq" else WV_TB
FIRST = 0 if GROUP == "sq" else 15
print("组=%s 标称=%s" % (GROUP, HZ))

for it in range(3):
    print("-- 第 %d 轮 --" % (it + 1))
    for i, hz in enumerate(HZ):
        f = measure(i, pick_tb(1e6 / hz, DTT), GROUP, hz)
        if not f:
            print("  档%2d(标称%7.1fHz): 测不到" % (FIRST + i, hz))
            continue
        # 偏移单位 0.1us: delta = (实测周期 - 目标周期) * 1e7
        delta = int(round(1e7 * (1.0 / hz - 1.0 / f)))
        delta = max(-300, min(300, delta))
        old = off[FIRST + i]
        off[FIRST + i] = max(-30000, min(30000, old + delta))
        print("  档%2d 标称%8.1f 实测%8.1fHz  偏移 %d -> %d"
              % (FIRST + i, hz, f, old, off[FIRST + i]))
    ok = write_off(off)
    print("  写入:", "成功" if ok else "失败")

print("最终偏移表:", off)
ser.close()
