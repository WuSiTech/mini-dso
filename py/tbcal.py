#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用外部基准(STM32 方波)逐档校准示波器时基
   原理: 数出一个周期占多少个采样点 -> 反推真实采样间隔 -> 按比例修正 CalTable
   用法: python py/tbcal.py [基准频率Hz] [起始档] [结束档] [--write]
"""
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

F_REF = float(sys.argv[1]) if len(sys.argv) > 1 else 1000.0
IDX0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
IDX1 = int(sys.argv[3]) if len(sys.argv) > 3 else 15
WRITE = "--write" in sys.argv

port = "COM5"
ser = serial.Serial(port, 115200, timeout=0.3)
p = g.FrameParser()


def rf(sec):
    out = []
    t0 = time.time()
    while time.time() - t0 < sec:
        d = ser.read(1024)
        if d:
            out += p.feed(d)
    return out


def getset(sec=2.5):
    ser.write(g.build_frame(0x12))
    time.sleep(0.2)
    for t, pl in rf(sec):
        if t == 0x03:
            return g.settings_from_bytes(pl)
    return None


def setset(s):
    ser.write(g.build_frame(g.T_SET, g.settings_to_bytes(s)))
    time.sleep(0.5)
    rf(0.2)


def get_caltable(sec=4.0):
    ser.write(g.build_frame(0x17))
    time.sleep(0.2)
    for t, pl in rf(sec):
        if t == 0x17 and len(pl) >= 42:
            return [pl[i * 2] | (pl[i * 2 + 1] << 8) for i in range(21)]
    return None


def period_samples(raw):
    """用迟滞过零点估计一个周期占多少采样点; 失败返回 0"""
    n = len(raw)
    if n < 20:
        return 0.0
    lo, hi = min(raw), max(raw)
    if hi - lo < 20:
        return 0.0
    mid = (lo + hi) / 2.0
    up, dn = mid + (hi - lo) * 0.2, mid - (hi - lo) * 0.2
    armed = False
    cross = []
    for i in range(1, n):
        a, b = raw[i - 1], raw[i]
        if not armed and b < dn:
            armed = True
        elif armed and b > up:
            armed = False
            if b != a:
                cross.append(i - 1 + (mid - a) / (b - a))
    if len(cross) < 2:
        return 0.0
    return (cross[-1] - cross[0]) / (len(cross) - 1)


def capture():
    """抓一帧原始数据"""
    t0 = time.time()
    while time.time() - t0 < 8:
        for t, pl in rf(0.4):
            if t == 0x01:
                sp = g.parse_sample(pl)
                if sp and len(sp["raw"]) > 30:
                    return sp
    return None


tbl = get_caltable()
cur = getset()
if tbl is None or cur is None:
    print("读不到时基表/参数, 中止")
    sys.exit(1)
print("基准 %.1f Hz, 校准档 %d..%d" % (F_REF, IDX0, IDX1))
print("原表:", tbl)

new = list(tbl)
for idx in range(IDX0, IDX1 + 1):
    dt_nom = g.SCALE_H_SEC[idx] / 25.0          # 标称采样间隔(秒)
    # 该档需要几个周期 (每周期采样点数最好 >= 8)
    s = dict(cur)
    s["scaleh"] = idx
    s["trimode"] = 0
    s["scalev_auto"] = 1
    setset(s)
    time.sleep(0.4)
    rf(0.4)
    ps_list = []
    for _ in range(3):
        sp = capture()
        if sp:
            ps = period_samples(sp["raw"])
            if ps > 3:
                ps_list.append(ps)
    if not ps_list:
        print("档 %2d: 测不到周期, 跳过" % idx)
        continue
    ps = sorted(ps_list)[len(ps_list) // 2]
    t_meas = (1.0 / F_REF) / ps                    # 实测采样间隔
    k = t_meas / dt_nom
    old = tbl[idx]
    val = max(0, min(65535, int(round(old * k))))
    new[idx] = val
    print("档 %2d: 周期=%6.2f 点  标称步长=%8.1fus 实测步长=%8.1fus  k=%.4f  表 %d->%d"
          % (idx, ps, dt_nom * 1e6, t_meas * 1e6, k, old, val))

if not WRITE:
    print("\n(预览模式, 未写入) 新表:", new)
    ser.close()
    sys.exit(0)

pay = b"".join(bytes([v & 0xFF, (v >> 8) & 0xFF]) for v in new)
ok = 0
ser.write(g.build_frame(0x16, pay))
time.sleep(0.2)
for t, pl in rf(3.0):
    if t == 0x02 and len(pl) >= 2:
        ok = pl[1]
ser.write(g.build_frame(0x11))
rf(1.5)
print("\n写入: %s  新表: %s" % ("成功" if ok else "失败", new))
ser.close()
