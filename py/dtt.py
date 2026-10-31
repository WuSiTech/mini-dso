#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读写每档真实采样间隔 DtTbl(0x21 读 / 0x22 写, 单位 0.01us, 21 x uint32)。

用法:
  python py/dtt.py                 # 读
  python py/dtt.py --nominal       # 读 CalTable, 按延时模型算出标称表并写入
  python py/dtt.py v0 v1 ... v20   # 写指定 21 个值
  python py/dtt.py --raw "1,2,3"   # 同上
"""
import struct
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

PORT = "COM5"
DT_A1, DT_B1, DT_A2, DT_B2, DT_THR = 12955, 1800, 14258, 1550, 300

ser = serial.Serial(PORT, 115200, timeout=0.2)
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


def cmd(typ, pay=b"", timeout=3.0):
    ser.reset_input_buffer()
    ser.write(g.build_frame(typ, pay))
    ser.flush()
    for t, pl in rf(timeout):
        if t == typ:
            return pl
    return None


def acmd(typ, pay=b"", timeout=3.0):
    ser.write(g.build_frame(typ, pay))
    ser.flush()
    for t, pl in rf(timeout):
        if t == 0x02 and len(pl) >= 2:
            return pl[1]
    return None


def read_cal():
    r = cmd(0x17)
    if r and len(r) >= 42:
        return [r[i * 2] | (r[i * 2 + 1] << 8) for i in range(21)]
    return None


def read_dtt():
    r = cmd(0x21)
    if r and len(r) >= 84:
        return list(struct.unpack("<21I", r[:84]))
    return None


def nominal(cal):
    out = []
    for i, cc in enumerate(cal):
        if i == 15:
            n = 2000
        elif i == 16:
            n = 1200
        elif i == 17:
            n = 800
        elif i == 18:
            n = 600
        elif i == 19:
            n = 400
        elif i == 20:
            n = 320
        elif cc >= DT_THR:
            n = cc * DT_A1 // 100 + DT_B1
        else:
            n = cc * DT_A2 // 100 + DT_B2
        out.append(n)
    return out


def write_dtt(vals):
    pay = struct.pack("<21I", *vals)
    return acmd(0x22, pay)


if "--raw" in sys.argv:
    vals = [int(x) for x in sys.argv[sys.argv.index("--raw") + 1].split(",")]
elif len(sys.argv) > 1 and sys.argv[1] != "--nominal":
    vals = [int(x) for x in sys.argv[1:]]
else:
    vals = None

if "--nominal" in sys.argv:
    cal = read_cal()
    if not cal:
        print("读 CalTable 失败")
        raise SystemExit(1)
    vals = nominal(cal)
    print("CalTable:", cal)
    print("标称 DtTbl:", vals)

if vals is not None:
    if len(vals) != 21:
        print("需要 21 个值")
        raise SystemExit(1)
    ok = write_dtt(vals)
    print("0x22 写入:", "ACK 成功" if ok else "失败/无应答")
    print("0x11 保存:", "成功" if acmd(0x11) else "失败/无应答")

back = read_dtt()
if back:
    print("0x21 回读:", back)
    if vals is not None:
        print("一致" if back == vals else "不一致!")
else:
    print("0x21 读取失败")
ser.close()
