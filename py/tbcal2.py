#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐档绝对校准时基(用 STM32 1kHz 基准, 只需烧一次 STM32)
思路: 每档实际采样间隔 t = a*表值 + b (固定开销), 用几档实测点拟合 a,b,
      再反算每档应有的表值, 覆盖全部 21 档(两组: DelayUs 档 / DelayFine 快档)
"""
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

F_REF = float(sys.argv[1]) if sys.argv[1].replace(chr(46),chr(48)).isdigit() else 1000.0
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


def setset(s):
    ser.write(g.build_frame(g.T_SET, g.settings_to_bytes(s)))
    time.sleep(0.45)
    rf(0.2)


def get_caltable(sec=4.0):
    ser.write(g.build_frame(0x17))
    time.sleep(0.2)
    for t, pl in rf(sec):
        if t == 0x17 and len(pl) >= 42:
            return [pl[i * 2] | (pl[i * 2 + 1] << 8) for i in range(21)]
    return None


def period_samples(raw):
    n = len(raw)
    if n < 20:
        return 0.0
    lo, hi = min(raw), max(raw)
    if hi - lo < 15:
        return 0.0
    mid = (lo + hi) / 2.0
    up, dn = mid + (hi - lo) * 0.2, mid - (hi - lo) * 0.2
    armed, cross = False, []
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
    t0 = time.time()
    while time.time() - t0 < 8:
        for t, pl in rf(0.4):
            if t == 0x01:
                sp = g.parse_sample(pl)
                if sp and len(sp["raw"]) > 30:
                    return sp
    return None


def measure_dt(idx, cur):
    """返回该档实测采样间隔(秒), 失败 None"""
    dt_nom = g.SCALE_H_SEC[idx] / 25.0
    s = dict(cur)
    s["scaleh"] = idx
    s["trimode"] = 0
    s["scalev_auto"] = 1
    setset(s)
    time.sleep(0.4)
    rf(0.4)
    ps = []
    for _ in range(3):
        sp = capture()
        if not sp:
            continue
        v = period_samples(sp["raw"])
        # 周期点数要在 6..120 之间才可信(避开混叠/越界)
        if 6 <= v <= 120:
            ps.append(v)
    if not ps:
        return None
    ps = sorted(ps)[len(ps) // 2]
    return (1.0 / F_REF) / ps


tbl = get_caltable()
cur = getset()
if tbl is None or cur is None:
    print("读表失败")
    sys.exit(1)
print("原表:", tbl)

# ---- 1) 测几档, 拟合两个线性关系 ----
DU = [] if '--fine' in sys.argv else [10, 11, 12, 13, 14]          # DelayUs 组(1kHz 在这些档周期点数合适)
DF = [15, 16, 17, 18, 20] if '--fine' in sys.argv else []                  # DelayFine 组
# 快档 15: dt=20us -> 周期 50 点; 16: 12us -> 83 点; 17: 8us -> 125 点(可能超, 由过滤决定)
pts_du, pts_df = [], []
for idx in DU:
    dt = measure_dt(idx, cur)
    print("DelayUs 档 %2d: 表=%5d  实测步长=%s" % (idx, tbl[idx], "测不到" if not dt else "%.2f us" % (dt * 1e6)))
    if dt:
        pts_du.append((tbl[idx], dt))
for idx in DF:
    dt = measure_dt(idx, cur)
    print("Fine 档  %2d: 表=%5d  实测步长=%s" % (idx, tbl[idx], "测不到" if not dt else "%.2f us" % (dt * 1e6)))
    if dt:
        pts_df.append((tbl[idx], dt))


def fit(pts):
    """最小二乘 t = a*x + b"""
    n = len(pts)
    if n < 2:
        return None, None
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    den = n * sxx - sx * sx
    if den == 0:
        return None, None
    a = (n * sxy - sx * sy) / den
    b = (sy - a * sx) / n
    return a, b


a_u, b_u = fit(pts_du)
a_f, b_f = fit(pts_df)
print("\nDelayUs  : a=%.4f us/单位, b=%.2f us" % (a_u * 1e6, b_u * 1e6) if a_u else "\nDelayUs 拟合点不足")
print("DelayFine: a=%.4f us/单位, b=%.2f us" % (a_f * 1e6, b_f * 1e6) if a_f else "DelayFine 拟合点不足")

new = list(tbl)
if a_u:
    for idx in range(0, 15):
        dt_nom = g.SCALE_H_SEC[idx] / 25.0
        x = int(round((dt_nom - b_u) / a_u))
        new[idx] = max(0, min(65535, x))
    # 100us 档(idx19)也是 DelayUs(v)
    idx = 19
    dt_nom = g.SCALE_H_SEC[idx] / 25.0
    x = int(round((dt_nom - b_u) / a_u))
    new[idx] = max(1, min(65535, x))
if a_f:
    for idx in (15, 16, 17, 18, 20):
        dt_nom = g.SCALE_H_SEC[idx] / 25.0
        x = int(round((dt_nom - b_f) / a_f))
        new[idx] = max(0, min(65535, x))

print("\n新表:", new)
if not WRITE:
    print("(预览, 未写入)")
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
print("写入:", "成功" if ok else "失败")

# ---- 复核: 用设备自己的频率读数看几档 ----
print("\n复核 (基准 1000Hz, 读数应接近 1000):")
for idx in [15, 14, 12, 10, 8, 6, 3, 1]:
    s = dict(cur)
    s["scaleh"] = idx
    s["trimode"] = 0
    setset(s)
    time.sleep(0.4)
    rf(0.3)
    fs = []
    t0 = time.time()
    while time.time() - t0 < 4 and len(fs) < 3:
        for t, pl in rf(0.4):
            if t == 0x01:
                sp = g.parse_sample(pl)
                if sp and sp["freq"]:
                    fs.append(sp["freq"])
    print("  档 %2d (%s): %s" % (idx, g.SCALE_H_TXT[idx], fs))
ser.close()
