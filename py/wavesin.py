import struct
import sys
import time
import statistics

sys.path.insert(0, "py")
import dso_gui as g
import serial

HZ = [8.8, 17.6, 35.2, 70.4, 140.8, 281.6]
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


def getoff():
    ser.write(g.build_frame(0x1D))
    time.sleep(0.2)
    for t, pl in rf(4.0):
        if t == 0x1D and len(pl) >= 42:
            return list(struct.unpack("<21h", pl[:42]))


def writeoff(vals):
    pay = b"".join(struct.pack("<h", max(-30000, min(30000, int(v)))) for v in vals)
    for _ in range(5):
        ser.write(g.build_frame(0x1E, pay))
        time.sleep(0.4)
        for t, pl in rf(3.0):
            if t == 0x02 and len(pl) >= 2 and pl[1]:
                return True
    return False


def picktb(period_us, dt):
    want = period_us / 150.0 * 100.0
    best, bd = 9, 1e18
    for i in range(21):
        v = dt[i]
        if v <= 0:
            continue
        if 220.0 * v < 6.0 * period_us * 100.0:
            continue
        dd = abs(v - want)
        if dd < bd:
            bd, best = dd, i
    return best


def meas(i, tb):
    s = getset()
    s["outpwm"] = 0
    s["outsin"] = 1
    s["wavetype"] = 0
    s["wavescroll"] = i
    s["scaleh"] = tb
    s["trimode"] = 0
    s["scalev_auto"] = 1
    ser.write(g.build_frame(g.T_SET, g.settings_to_bytes(s)))
    time.sleep(0.6)
    rf(0.3)
    fs = []
    t0 = time.time()
    while time.time() - t0 < 8 and len(fs) < 4:
        for t, pl in rf(0.5):
            if t == 0x01:
                sp = g.parse_sample(pl)
                if sp and sp["freq"] and sp["freq"] > 0:
                    fs.append(sp["freq"])
    return statistics.median(fs) if fs else 0


dt = getdt() or [100] * 21
off = getoff() or [0] * 21
for i, hz in enumerate(HZ):
    tb = picktb(1e6 / hz, dt)
    f = meas(i, tb)
    if not f:
        print("波档%d 标称%6.1fHz 测不到(时基%d)" % (i, hz, tb))
        continue
    d = int(round(1e7 * (1.0 / hz - 1.0 / f)))
    off[15 + i] = max(-30000, min(30000, off[15 + i] + d))
    print("波档%d 标称%6.1f 实测%8.2f 偏差%+6.1f%% 偏移=%6d (时基%d)"
          % (i, hz, f, (f / hz - 1) * 100, off[15 + i], tb))
ok = writeoff(off)
print("写入:", "成功" if ok else "失败")
ser.close()
