#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐档测量真实采样间隔(DtTbl, 单位 0.01us)并写入 DSO 的 EEPROM。

原理: STM32 基准给输入端一个已知频率 f, DSO 在某一档采集 100 个点,
      测出每周期占多少样点 n, 则该档真实采样间隔 dt = (1/f)/n。
      所有档测完后用 0x22 写入 DtTbl, 0x11 保存。

用法:
  python py/dtcal.py --all                  # 自动换频(5/50/1k/3k/10k)测全部 21 档并写入
  python py/dtcal.py --freq 1000 --ranges 11-14 [--write]
  python py/dtcal.py --verify --freq 1000 --ranges 11-14
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g  # noqa: E402
import serial  # noqa: E402

PORT = "COM5"
HERE = os.path.dirname(os.path.abspath(__file__))
SETFREQ = os.path.join(HERE, "refgen", "setfreq.py")

# 每个参考频率覆盖的档位(保证屏幕上能看到 ~2 个以上周期)
GROUPS = [
    (5.0, [0, 1, 2, 3, 4]),
    (50.0, [5, 6, 7, 8, 9]),
    (1000.0, [10, 11, 12, 13, 14]),
    (3000.0, [15, 16, 17, 18]),
    (10000.0, [19, 20]),
]

ser = None
p = None


def connect():
    global ser, p
    if ser is None:
        ser = serial.Serial(PORT, 115200, timeout=0.2)
        p = g.FrameParser()
        time.sleep(1.2)


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


def cmd(typ, pay=b"", want=None, timeout=2.5, retries=4):
    want = typ if want is None else want
    for _ in range(retries):
        ser.reset_input_buffer()
        ser.write(g.build_frame(typ, pay))
        ser.flush()
        for t, pl in rf(timeout, want):
            if t == want:
                return pl
    return None


def ack(typ, pay=b""):
    return cmd(typ, pay, 0x02)


def get_settings():
    st = cmd(0x12, b"", 0x03)
    return g.settings_from_bytes(st) if st and len(st) >= 8 else None


def set_settings(s):
    ser.write(g.build_frame(0x10, g.settings_to_bytes(s)))
    ser.flush()
    rf(0.25)


def apply_range(idx, base):
    s = dict(base)
    s["scaleh"] = idx
    s["trimode"] = 0        # 自动触发: 波形和幅值最容易稳定
    s["scalev_auto"] = 1
    s["outuart"] = 1
    set_settings(s)
    time.sleep(0.25)
    rf(0.2)
    ack(0x1C, bytes([1]))   # 运行


def psc(raw):
    """返回每周期样点数(0 = 没测到)"""
    lo, hi = min(raw), max(raw)
    if hi - lo < 15:
        return 0
    mid = (lo + hi) / 2.0
    up, dn = mid + (hi - lo) * 0.2, mid - (hi - lo) * 0.2
    armed = False
    cr = []
    for i in range(1, len(raw)):
        a, b = raw[i - 1], raw[i]
        if not armed and b < dn:
            armed = True
        elif armed and b > up:
            armed = False
            if b != a:
                cr.append(i - 1 + (mid - a) / (b - a))
    return (cr[-1] - cr[0]) / (len(cr) - 1) if len(cr) > 1 else 0


def collect_frames(idx, need=4, timeout=14.0):
    """只收 scaleh == idx 的帧, 避免切档后拿到上一档的旧帧"""
    out = []
    t0 = time.time()
    while time.time() - t0 < timeout and len(out) < need:
        for t, pl in rf(0.5):
            if t == 0x01:
                sp = g.parse_sample(pl)
                if sp and sp["scaleh"] == idx:
                    out.append(sp)
    return out


def measure_range(idx, freq, base):
    """返回 (dt_seconds, n_samples_per_period) 或 (None, 0)"""
    apply_range(idx, base)
    for _ in range(2):
        frames = collect_frames(idx, need=4)
        vals = []
        for sp in frames:
            v = psc(sp["raw"])
            if 3.0 <= v <= 400.0:
                vals.append(v)
        if vals:
            vals.sort()
            n = vals[len(vals) // 2]
            dt = (1.0 / freq) / n
            return dt, n
        time.sleep(0.3)
    return None, 0


def read_dtt():
    r = cmd(0x21)
    if r and len(r) >= 84:
        import struct
        return list(struct.unpack("<21I", r[:84]))
    return None


def write_dtt(vals):
    import struct
    for attempt in range(3):
        ser.reset_input_buffer()
        ser.write(g.build_frame(0x22, struct.pack("<21I", *vals)))
        ser.flush()
        ok = None
        for t, pl in rf(4.0):
            if t == 0x02 and len(pl) >= 2:
                ok = pl[1]
        if ok:
            ack(0x11)
            return ok
        time.sleep(0.4)
    return None


def read_frame_freq(idx, base, timeout=8.0):
    """切到该档, 等一帧确实属于该档的, 返回固件算出的频率"""
    apply_range(idx, base)
    t0 = time.time()
    while time.time() - t0 < timeout:
        for t, pl in rf(0.5):
            if t == 0x01:
                sp = g.parse_sample(pl)
                if sp and sp["scaleh"] == idx:
                    return sp["freq"], sp
    return None, None


def refgen_freq(f):
    print("== 基准换频 -> %.1f Hz ==" % f, flush=True)
    r = subprocess.run([sys.executable, SETFREQ, "%g" % f], cwd=".", capture_output=True, text=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    for line in out[-4:]:
        print("   " + line, flush=True)
    if r.returncode != 0:
        raise RuntimeError("refgen 换频失败")
    time.sleep(0.8)


def parse_ranges(text):
    if "-" in text:
        a, b = text.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in text.split(",")]


def main():
    args = sys.argv[1:]
    allmode = "--all" in args
    verify_only = "--verify" in args
    do_write = "--write" in args or allmode

    connect()
    base = get_settings()
    if not base:
        print("读设置失败")
        return 1
    info = cmd(0x19)
    if info and len(info) >= 3:
        print("固件 %d.%d.%d" % (info[0], info[1], info[2]))

    dtt = read_dtt() or [0] * 21
    results = {}
    failed = []

    if verify_only:
        freq = float(args[args.index("--freq") + 1])
        ranges = parse_ranges(args[args.index("--ranges") + 1])
        for idx in ranges:
            f, sp = read_frame_freq(idx, base)
            n_out = sp["raw"] if sp else []
            print("档 %2d %-6s 固件读数 %s Hz (基准 %.1f Hz)"
                  % (idx, g.SCALE_H_TXT[idx], ("%u" % f) if f else "无", freq), flush=True)
        return 0

    if allmode:
        for freq, ranges in GROUPS:
            refgen_freq(freq)
            for idx in ranges:
                dt, n = measure_range(idx, freq, base)
                if dt is None:
                    print("档 %2d %-6s 测量失败(没信号?)" % (idx, g.SCALE_H_TXT[idx]), flush=True)
                    failed.append(idx)
                    continue
                val = max(1, min(4000000, int(round(dt * 1e8))))
                results[idx] = (val, n, freq)
                old = dtt[idx]
                dtt[idx] = val
                print("档 %2d %-6s 周期 %6.2f 样点 @ %.0fHz -> dt=%9.2f us  DtTbl %d -> %d"
                      % (idx, g.SCALE_H_TXT[idx], n, freq, dt * 1e6, old, val), flush=True)
            if do_write:
                print("   写入 DtTbl:", "成功" if write_dtt(dtt) else "失败", flush=True)
            # 用当前基准复测这一组
            print("   -- 复测 --", flush=True)
            for idx in ranges:
                f, sp = read_frame_freq(idx, base)
                if f:
                    print("   档 %2d 固件读数 %6u Hz / 基准 %6.0f Hz  误差 %+6.2f%%"
                          % (idx, f, freq, (f - freq) * 100.0 / freq), flush=True)
    else:
        freq = float(args[args.index("--freq") + 1])
        ranges = parse_ranges(args[args.index("--ranges") + 1])
        for idx in ranges:
            dt, n = measure_range(idx, freq, base)
            if dt is None:
                print("档 %2d 测量失败" % idx, flush=True)
                failed.append(idx)
                continue
            val = int(round(dt * 1e8))
            results[idx] = (val, n, freq)
            old = dtt[idx]
            dtt[idx] = val
            print("档 %2d %-6s 周期 %6.2f 样点 @ %.0fHz -> dt=%9.2f us  DtTbl %d -> %d"
                  % (idx, g.SCALE_H_TXT[idx], n, freq, dt * 1e6, old, val), flush=True)
        if do_write and not failed:
            ok = write_dtt(dtt)
            print("写入 DtTbl:", "成功" if ok else "失败")
            print("回读:", read_dtt())

    out = os.path.join(os.path.dirname(HERE), "build", "dtcal.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"dt": dtt, "results": {str(k): v for k, v in results.items()},
                   "failed": failed}, f, indent=1)
    print("结果已保存", out)
    if ser:
        ser.close()
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
