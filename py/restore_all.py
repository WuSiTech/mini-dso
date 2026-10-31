#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""烧录后一键恢复 EEPROM 标定数据（全部三张表）:
  1) CalTable   时基校准表   0x16 / 读 0x17
  2) DtTbl      每档采样间隔 0x22 / 读 0x21
  3) TK + 6×WS  生成器系数   0x24 / 读 0x23
最后 0x11 保存，回读校验，并可选 0x13 软复位验证掉电保持。

用法: python py/restore_all.py [COM5] [--no-reboot]
数据来源: build/dtcal.json 优先（DtTbl），否则用内置实测值。
"""
import json
import os
import struct
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
PORT = ARGS[0] if ARGS else "COM5"
DO_REBOOT = "--no-reboot" not in sys.argv

# ---- 实测/标定值 ----
CAL = [15242, 9203, 6047, 4596, 3045, 1513, 896, 594, 436, 288,
       129, 72, 43, 32, 17, 20, 2, 6, 1, 1, 0]
DTT = [2127710, 1276656, 842095, 645127, 425527, 212761, 127664, 85103,
       62500, 42554, 20652, 12766, 8421, 6316, 4167, 1667, 1389, 844, 659, 889, 421]
TK = 117
WS = [12281, 5799, 3229, 1559, 774, 395]

jsonf = os.path.join("build", "dtcal.json")
if os.path.exists(jsonf):
    try:
        d = json.load(open(jsonf, encoding="utf-8"))["dt"]
        if len(d) == 21 and all(v > 0 for v in d):
            DTT = d
            print("DtTbl 来源:", jsonf)
    except Exception as exc:
        print("读 dtcal.json 失败, 用内置值:", exc)

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


def ack(typ, pay=b"", retries=3, timeout=4.0):
    for _ in range(retries):
        r = cmd(typ, pay, 0x02, timeout)
        if r:
            return r[1]
    return None


def read_cal():
    r = cmd(0x17)
    return [r[i * 2] | (r[i * 2 + 1] << 8) for i in range(21)] if r and len(r) >= 42 else None


def read_dtt():
    r = cmd(0x21)
    return list(struct.unpack("<21I", r[:84])) if r and len(r) >= 84 else None


def read_tkws():
    r = cmd(0x23)
    return list(struct.unpack("<7H", r[:14])) if r and len(r) >= 14 else None


def report(tag=""):
    c, d, t = read_cal(), read_dtt(), read_tkws()
    print(tag + "CalTable:", "OK" if c == CAL else c)
    print(tag + "DtTbl:   ", "OK" if d == DTT else d)
    print(tag + "TK/WS:   ", ("OK  TK=%d WS=%s" % (t[0], t[1:])) if t == [TK] + WS else t)
    return c == CAL and d == DTT and t == [TK] + WS


info = cmd(0x19)
if info:
    print("固件 %d.%d.%d" % (info[0], info[1], info[2]))
    if (info[0], info[1], info[2]) < (1, 7, 10):
        print("警告: 固件低于 1.7.10, 可能有 EEPROM 保存死循环/长度截断问题")

print("\n== 写入 ==")
cal_pay = b"".join(bytes([v & 0xFF, (v >> 8) & 0xFF]) for v in CAL)
dtt_pay = b"".join(bytes([(v >> s) & 0xFF for s in (0, 8, 16, 24)]) for v in DTT)
tk_pay = struct.pack("<7H", TK, *WS)

print("0x16 CalTable:", "成功" if ack(0x16, cal_pay) else "失败")
print("0x22 DtTbl:   ", "成功" if ack(0x22, dtt_pay) else "失败")
print("0x24 TK/WS:   ", "成功" if ack(0x24, tk_pay) else "失败")
print("0x11 保存:    ", "成功" if ack(0x11) else "失败")

print("\n== 回读校验 ==")
ok = report("")

if ok and DO_REBOOT:
    print("\n== 0x13 软复位后验证掉电保持 ==")
    ser.write(g.build_frame(0x13))
    ser.flush()
    ser.close()
    time.sleep(3.5)
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    p = g.FrameParser()
    info = cmd(0x19)
    if info:
        print("重启后固件 %d.%d.%d" % (info[0], info[1], info[2]))
    ok = report("重启后 ")

print("\n结果:", "全部写回并验证通过" if ok else "有项目不一致, 请检查")
ser.close()
sys.exit(0 if ok else 1)
