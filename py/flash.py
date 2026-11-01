#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动烧录 + 完整保留用户 EEPROM（默认 1 KB），烧后逐字节校验。

流程:
  0) 设备在跑固件时: 用 0x18 把整块用户 EEPROM dump 到 build/eeprom_backup.bin
     （读取失败会重试; 有读不到的块就中止烧录, 绝不拿残缺备份去覆盖）
  1) 0x14 软复位进 ISP（这块板不可靠, 失败就提示拔插冷启动）
  2) stcgal 烧录: -o program_eeprom_split=64512（1 KB EEPROM），
     并把 dump 出来的 1024 B 作为 eeprom_image 一起写回
     => 设置 / CalTable / DtTbl / TK+WS / OutOff / 延时模型 逐字节不变
  3) 烧完等固件启动, 再 dump 一次与备份比对:
       完全一致 -> EEPROM 保留 OK
       只有 0x1F9~0x1FF 不同 -> 那是芯片 UID 尾区, ISP 烧录时重写, 也视为 OK
  4) 若第 0 步读不到 EEPROM（设备没跑固件）, 烧完退化为 restore_all.py 写回三张表

用法:
  python py/flash.py                         # COM5 + build/wusi_minidso.hex
  python py/flash.py COM5 build/wusi_minidso.hex
  python py/flash.py --cold                  # 跳过 0x14, 直接等拔插冷启动
  python py/flash.py --split 63488           # 改 EEPROM 分区(2KB), 备份大小随之变化
  python py/flash.py --no-eeprom             # 不做 EEPROM 备份/写回/校验
  python py/flash.py --no-restore            # 没备份时也不写回三张表

关于"不改变频率":
  - 输出频率: 由 EEPROM 的 TK + WS(和方波偏移表) 决定, 本脚本逐字节保留 EEPROM => 不变;
  - 频率读数: 由 DtTbl 决定, 同样保留 => 不变;
  - MCU IRC trim: stcgal 每次烧录都会按芯片里存的目标频率重新校准（目标值不变,
    实测偏差通常 < 0.1%）, 这是 stcgal 的行为, CLI 无法完全跳过。
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g          # noqa: E402

import serial                # noqa: E402

T_REBOOT = 0x14
DEFAULT_SPLIT = 64512        # 65536-64512 = 1024 B EEPROM
DEFAULT_EEPROM_BIN = os.path.join("build", "eeprom_backup.bin")
UID_TAIL = (0x1F9, 0x200)    # 芯片 UID 存在 EEPROM 最后 7 字节, ISP 烧录时会重写

try:                                               # 中文在 GBK 控制台也能安全输出
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


def say(*a):
    print(*a, flush=True)


def _rf(ser, p, sec, want=None):
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


def _cmd(ser, p, typ, pay=b"", want=None, timeout=2.0, retries=5):
    want = typ if want is None else want
    for _ in range(retries):
        ser.reset_input_buffer()
        ser.write(g.build_frame(typ, pay))
        ser.flush()
        for t, pl in _rf(ser, p, timeout, want):
            if t == want:
                return pl
    return None


# --------------------------------------------------------------------------
# EEPROM 读取（0x18 读 IAP 任意地址 16 字节）
# --------------------------------------------------------------------------
def dump_eeprom(port, size, path=None):
    """读完整 EEPROM。失败返回 None（不会用 0xFF 假数据冒充）。"""
    try:
        ser = serial.Serial(port, 115200, timeout=0.2)
    except Exception as exc:
        say("   串口打不开:", exc)
        return None
    p = g.FrameParser()
    try:
        info = None
        for _ in range(6):
            info = _cmd(ser, p, 0x19, b"", timeout=1.5, retries=2)
            if info:
                break
            time.sleep(0.3)
        if not info:
            say("   设备没有响应 0x19(没在跑固件?), 读不到 EEPROM")
            return None
        say("   固件 %d.%d.%d, 暂停采样后读取 %d B EEPROM ..."
            % (info[0], info[1], info[2], size))
        _cmd(ser, p, 0x1C, bytes([0]), want=0x02, timeout=2.0)   # 暂停采样

        data = bytearray(b"\xff" * size)
        fails = []
        for addr in range(0, size, 16):
            r = _cmd(ser, p, 0x18, bytes([addr & 0xFF, addr >> 8]),
                     want=0x18, timeout=1.5, retries=6)
            if r and len(r) >= 16:
                data[addr:addr + 16] = r[:16]
            else:
                fails.append(addr)
        # 失败块再补几轮
        for _ in range(3):
            if not fails:
                break
            still = []
            for addr in fails:
                r = _cmd(ser, p, 0x18, bytes([addr & 0xFF, addr >> 8]),
                         want=0x18, timeout=1.5, retries=10)
                if r and len(r) >= 16:
                    data[addr:addr + 16] = r[:16]
                else:
                    still.append(addr)
            fails = still
        if fails:
            say("   !! EEPROM 读取不完整: %d 块失败 (%s ...), 中止, 不覆盖 EEPROM"
                % (len(fails), ", ".join("0x%03X" % a for a in fails[:6])))
            return None

        if path:
            with open(path, "wb") as f:
                f.write(bytes(data))
        nz = sum(1 for b in data if b != 0xFF)
        say("   读到 %d B (非 0xFF %d B)%s"
            % (len(data), nz, (", 已存 " + path) if path else ""))
        return bytes(data)
    finally:
        ser.close()


def diff_list(a, b):
    return [i for i in range(min(len(a), len(b))) if a[i] != b[i]]


# --------------------------------------------------------------------------
# 烧录
# --------------------------------------------------------------------------
def soft_reset(port):
    say("1) 请求 DSO 软复位进 ISP 模式 ...")
    try:
        with serial.Serial(port, 115200, timeout=0.3) as ser:
            ser.write(g.build_frame(T_REBOOT))
            ser.flush()
            t0 = time.time()
            while time.time() - t0 < 1.2:
                d = ser.read(64)
                if d:
                    say("   DSO 应答:", d.hex())
                    return True
        say("   (没收到 ACK: 这块板 0x14 软复位不可靠, 需要拔插冷启动)")
        return False
    except Exception as exc:
        say("   串口错误:", exc)
        return False


def run_stcgal(args, eeprom_bin=None):
    cmd = [sys.executable, "-m", "stcgal", "-P", "stc8d", "-p", args.port,
           "-o", "program_eeprom_split=%d" % args.split, args.hex]
    if eeprom_bin:
        cmd.append(eeprom_bin)
    say("2) stcgal 烧录 %s%s (EEPROM=%d B)"
        % (args.hex, (" + " + eeprom_bin) if eeprom_bin else "", 65536 - args.split))
    say("   " + " ".join(cmd))
    say("   若一直停在 'Waiting for MCU': 把 DSO 的 USB 拔插一次 (冷启动进 ISP)")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        say("   烧录超时 (设备没进 ISP?)")
        return False, ""
    except OSError as exc:
        say("   (无法捕获输出, 改为直接运行:", exc, ")")
        r = subprocess.run(cmd, timeout=180)
        return r.returncode == 0, ""
    out = ((r.stdout or "") + (r.stderr or ""))
    for line in out.strip().splitlines():
        if line.startswith("Writing flash"):
            continue
        if line.strip():
            say("   " + line)
    return ("Disconnected!" in out), out


def restore_fallback(port):
    say("4) 没有可用 EEPROM 备份, 退化为写回三张表 (CalTable + DtTbl + TK/WS) ...")
    time.sleep(2.5)
    cmd = [sys.executable, "py/restore_all.py", port]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        say(((r.stdout or "") + (r.stderr or "")).strip())
        return r.returncode == 0
    except Exception as exc:
        say("   restore_all.py 调用失败:", exc)
        return False


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("port", nargs="?", default="COM5")
    ap.add_argument("hex", nargs="?", default="build/wusi_minidso.hex")
    ap.add_argument("--split", type=int, default=DEFAULT_SPLIT,
                    help="program_eeprom_split, EEPROM=65536-split (默认 %d = 1KB)" % DEFAULT_SPLIT)
    ap.add_argument("--eeprom-bin", default=DEFAULT_EEPROM_BIN,
                    help="EEPROM 备份文件路径 (默认 %s)" % DEFAULT_EEPROM_BIN)
    ap.add_argument("--cold", action="store_true", help="跳过 0x14 软复位, 直接等冷启动")
    ap.add_argument("--no-eeprom", action="store_true", help="不做 EEPROM 备份 / 写回 / 校验")
    ap.add_argument("--no-restore", action="store_true", help="没有备份时也不写回三张表")
    args = ap.parse_args()

    if 512 > args.split or args.split > 65024 or args.split % 512:
        say("--split 必须是 512..65024 之间 512 的倍数")
        return 1
    eeprom_size = 65536 - args.split

    # ---- 0) 备份整块用户 EEPROM ----
    backup = None
    if not args.no_eeprom:
        say("0) 备份当前用户 EEPROM (%d B) ..." % eeprom_size)
        backup = dump_eeprom(args.port, eeprom_size, args.eeprom_bin)
        if backup is None:
            say("   !! 没有完整备份: 中止烧录（避免丢 EEPROM）。")
            say("      如果设备没在跑固件, 先上电进用户程序再烧; 或加 --no-eeprom 强制烧。")
            return 1
    else:
        say("0) --no-eeprom: 跳过 EEPROM 备份")

    # ---- 1) 软复位进 ISP ----
    if not args.cold:
        soft_reset(args.port)
    else:
        say("1) --cold: 跳过软复位, 直接等拔插冷启动")

    # ---- 2) 烧录 (代码 + EEPROM 镜像) ----
    ok, out = run_stcgal(args, args.eeprom_bin if backup is not None else None)
    say("烧录", "成功" if ok else "失败/中断")
    if not ok:
        say("提示: 重新运行本脚本, 或保持 stcgal 运行后拔插 DSO 的 USB; 也可用 STC-ISP 手动下载")
        return 1

    # ---- 3) 校验 EEPROM 是否逐字节保留 ----
    if backup is not None:
        say("3) 等固件启动, 回读 EEPROM 与备份比对 ...")
        time.sleep(2.5)
        got = dump_eeprom(args.port, eeprom_size, None)
        if got is None:
            say("   回读失败(设备没起来?), 请手动确认")
            return 1
        diffs = diff_list(backup, got)
        if not diffs:
            say("   EEPROM 校验: 完全一致 OK  (%d B: 设置/CalTable/DtTbl/TK+WS/OutOff 都没变)"
                % eeprom_size)
        else:
            lo, hi = UID_TAIL
            only_uid = all(lo <= i < hi for i in diffs)
            if only_uid:
                say("   EEPROM 校验: OK (只有 0x%03X~0x%03X 芯片 UID 尾区不同, ISP 烧录时重写)"
                    % (lo, hi - 1))
            else:
                other = [i for i in diffs if not (lo <= i < hi)]
                say("   EEPROM 校验: 不一致 FAIL  共 %d B 不同, 首个 @0x%04X (备份 0x%02X / 现在 0x%02X)"
                    % (len(other), other[0], backup[other[0]], got[other[0]]))
                if not args.no_restore:
                    restore_fallback(args.port)
                return 1
    else:
        if not args.no_restore:
            restore_fallback(args.port)

    say("完成: 固件已烧入" + ("" if args.no_eeprom else ", 用户 EEPROM 已完整保留"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
