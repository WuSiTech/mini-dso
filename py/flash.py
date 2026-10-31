#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动烧录 + 烧后恢复 EEPROM 校准数据。

用法:
  python py/flash.py                        # COM5 + build/wusi_minidso.hex
  python py/flash.py COM5                    # 指定串口
  python py/flash.py COM5 build/wusi_minidso.hex
  python py/flash.py --cold                  # 跳过 0x14 软复位, 直接等拔插冷启动
  python py/flash.py --split 63488           # EEPROM 设成 2KB (默认 64512 = 1KB)
  python py/flash.py --no-restore            # 烧完不写回校准表

流程:
  1) 发 0x14 让固件软复位进 ISP (这块板不可靠, 失败就提示拔插冷启动; stcgal 会一直等)
  2) stcgal 烧录, 显式带 program_eeprom_split (默认 64512 = 1KB EEPROM)
  3) 烧完等固件启动, 调 py/restore_all.py 写回 CalTable + DtTbl
"""
import argparse
import subprocess
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g          # noqa: E402

import serial                # noqa: E402

T_REBOOT = 0x14
DEFAULT_SPLIT = 64512        # 65536-64512 = 1KB EEPROM
SCRIPT_DIR = "py"


def parse_args():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("port", nargs="?", default="COM5")
    ap.add_argument("hex", nargs="?", default="build/wusi_minidso.hex")
    ap.add_argument("--split", type=int, default=DEFAULT_SPLIT,
                    help="program_eeprom_split, EEPROM=65536-split (默认 %d = 1KB)" % DEFAULT_SPLIT)
    ap.add_argument("--cold", action="store_true", help="跳过 0x14 软复位, 直接等冷启动")
    ap.add_argument("--no-restore", action="store_true", help="烧完不写回校准表")
    # 兼容旧用法: python py/flash.py COM5 hex
    return ap.parse_args()


def soft_reset(port):
    print("1) 请求 DSO 软复位进 ISP 模式 ...")
    try:
        with serial.Serial(port, 115200, timeout=0.3) as ser:
            ser.write(g.build_frame(T_REBOOT))
            ser.flush()
            t0 = time.time()
            while time.time() - t0 < 1.2:
                d = ser.read(64)
                if d:
                    print("   DSO 应答:", d.hex())
                    return True
        print("   (没收到 ACK: 0x14 软复位不可靠)")
        return False
    except Exception as exc:
        print("   串口错误:", exc)
        return False


def run_stcgal(args):
    cmd = [sys.executable, "-m", "stcgal", "-P", "stc8d", "-p", args.port,
           "-o", "program_eeprom_split=%d" % args.split, args.hex]
    print("2) stcgal 烧录 %s (EEPROM=%d B)" % (args.hex, 65536 - args.split))
    print("   " + " ".join(cmd))
    if not args.cold:
        print("   若一直停在 'Waiting for MCU': 把 DSO 的 USB 拔插一次 (冷启动进 ISP)")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        print("   烧录超时")
        return False, ""
    except OSError as exc:
        # 某些受限环境不允许 capture 管道: 退化为直接继承 stdio
        print("   (无法捕获输出, 改为直接运行:", exc, ")")
        r = subprocess.run(cmd, timeout=180)
        return r.returncode == 0, ""
    out = ((r.stdout or "") + (r.stderr or ""))
    for line in out.strip().splitlines():
        if line.startswith("Writing flash"):
            continue
        if line.strip():
            print("   " + line)
    ok = "Disconnected!" in out
    return ok, out


def restore(port, split):
    print("3) 等固件启动并写回 EEPROM 校准数据 (CalTable + DtTbl) ...")
    time.sleep(2.5)
    cmd = [sys.executable, "py/restore_all.py", port]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        print(out)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        print("   恢复超时")
        return False
    except OSError as exc:
        # 受限环境: 直接 import 执行
        print("   (无法捕获输出, 改为直接运行:", exc, ")")
        r = subprocess.run(cmd, timeout=90)
        return r.returncode == 0


def main():
    args = parse_args()
    if 512 > args.split or args.split > 65024 or args.split % 512:
        print("--split 必须是 512..65024 之间 512 的倍数")
        return 1

    if not args.cold:
        soft_reset(args.port)
    else:
        print("1) --cold: 跳过软复位, 直接等拔插冷启动")

    ok, out = run_stcgal(args)
    print("烧录", "成功" if ok else "失败/中断")
    if not ok:
        # 常见失败: 冷启动没进 ISP
        print("提示: 让 stcgal 保持运行, 重新拔插 DSO 的 USB; 或改用 STC-ISP 手动下载")
        return 1

    if not args.no_restore:
        restore(args.port, args.split)
    print("完成: 固件已烧入" + ("" if args.no_restore else ", 校准数据已写回"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
