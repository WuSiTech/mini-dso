#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动烧录: 先让 DSO 软复位进 ISP 监控区，再用 stcgal 烧写

用法: python py/flash.py [COM5] [build/minidso_uart.hex]

前提: 板上固件支持 UART 命令 0x14 (软复位进 ISP)；第一次需要手动烧一次带该命令的固件。
"""
import subprocess
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g          # noqa: E402

import serial                # noqa: E402

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
HEX = sys.argv[2] if len(sys.argv) > 2 else "build/minidso_uart.hex"
T_REBOOT = 0x14


def main():
    print("1) 请求 DSO 软复位进 ISP 模式 ...")
    try:
        with serial.Serial(PORT, 115200, timeout=0.3) as ser:
            ser.write(g.build_frame(T_REBOOT))
            ser.flush()
            t0 = time.time()
            got = False
            while time.time() - t0 < 1.0:
                d = ser.read(64)
                if d:
                    print("   DSO:", d.hex())
                    got = True
                    break
            if not got:
                print("   (没收到 ACK, 也许固件还不支持 0x14)")
    except Exception as exc:
        print("   串口错误:", exc)
        return 1
    time.sleep(0.1)

    print("2) stcgal 烧录", HEX)
    cmd = [sys.executable, "-m", "stcgal", "-P", "stc8d", "-p", PORT, HEX]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.strip().splitlines():
        if not line.startswith("Writing flash"):
            print("   " + line)
    ok = "Disconnected!" in out
    print("烧录", "成功" if ok else "失败/中断")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
