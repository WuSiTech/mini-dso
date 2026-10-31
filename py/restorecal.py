#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""烧录后写回时基校准表(0x16)并保存(0x11)。
用法:
  python py/restorecal.py               # 用内置的当前实测表
  python py/restorecal.py 15242 9203 ...  # 指定 21 个值
  python py/restorecal.py --read        # 只读
"""
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

CAL = [15242, 9203, 6047, 4596, 3045, 1513, 896, 594, 436, 288,
       129, 72, 43, 32, 17, 20, 2, 6, 1, 1, 0]
PORT = "COM5"

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


if "--read" in sys.argv:
    r = cmd(0x17)
    if r and len(r) >= 42:
        print([r[i * 2] | (r[i * 2 + 1] << 8) for i in range(21)])
    else:
        print("读取失败")
    ser.close()
    raise SystemExit(0)

vals = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else CAL
if len(vals) != 21:
    print("需要 21 个值, 实际", len(vals))
    raise SystemExit(1)

pay = b"".join(bytes([v & 0xFF, (v >> 8) & 0xFF]) for v in vals)
time.sleep(0.05)
ser.write(g.build_frame(0x16, pay))
ser.flush()
ok = None
for t, pl in rf(4.0):
    if t == 0x02 and len(pl) >= 2:
        ok = pl[1]
print("写校准表:", "ACK 成功" if ok else "失败/无应答")

ser.write(g.build_frame(0x11))
ser.flush()
ok2 = None
for t, pl in rf(3.0):
    if t == 0x02 and len(pl) >= 2:
        ok2 = pl[1]
print("保存 EEPROM:", "成功" if ok2 else "失败/无应答")

r = cmd(0x17)
if r and len(r) >= 42:
    back = [r[i * 2] | (r[i * 2 + 1] << 8) for i in range(21)]
    print("回读:", back)
    print("一致" if back == vals else "不一致!")
else:
    print("回读失败")
ser.close()
