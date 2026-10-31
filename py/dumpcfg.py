#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""烧录前备份 DSO 的 EEPROM 表: 校准表/输出偏移/延时模型/DtTbl/设置/版本。
用法: python py/dumpcfg.py [COM5] [out.json]
"""
import json
import struct
import sys
import time

import serial

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
OUT = sys.argv[2] if len(sys.argv) > 2 else "build/eeprom_backup.json"

ser = serial.Serial(PORT, 115200, timeout=0.2)
p = g.FrameParser()


def rf(sec, want=None):
    """read for sec seconds, return list of frames; stop early if want type seen"""
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


def cmd(typ, timeout=4.0):
    ser.reset_input_buffer()
    ser.write(g.build_frame(typ))
    ser.flush()
    for t, pl in rf(timeout, want=typ):
        if t == typ:
            return pl
    return None


res = {}
info = cmd(0x19)
if info and len(info) >= 3:
    res["fw"] = "%d.%d.%d" % (info[0], info[1], info[2])
    print("固件版本:", res["fw"])

cal = cmd(0x17)
if cal and len(cal) >= 42:
    res["caltable"] = [cal[i * 2] | (cal[i * 2 + 1] << 8) for i in range(21)]
    print("CalTable:", res["caltable"])
else:
    print("CalTable: 读取失败")

outo = cmd(0x1D)
if outo and len(outo) >= 42:
    res["outoff"] = [struct.unpack("<h", outo[i * 2:i * 2 + 2])[0] for i in range(21)]
    print("OutOff:", res["outoff"])
else:
    print("OutOff: 读取失败")

dtm = cmd(0x1F)
if dtm and len(dtm) >= 10:
    res["dtmodel"] = list(struct.unpack("<5H", dtm[:10]))
    print("DtModel:", res["dtmodel"])
else:
    print("DtModel: 读取失败")

dtt = cmd(0x21)
if dtt and len(dtt) >= 84:
    res["dttbl"] = list(struct.unpack("<21I", dtt[:84]))
    print("DtTbl:", res["dttbl"])
else:
    print("DtTbl(0x21): 读取失败")

settings = cmd(0x12)
if settings:
    res["settings_hex"] = settings.hex()

if res:
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("已保存", OUT)
else:
    print("什么都没读到——设备没在跑固件?")
ser.close()
sys.exit(0 if res else 1)
