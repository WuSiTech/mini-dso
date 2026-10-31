#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 STM32 基准(Blue Pill)设置任意输出频率: 改 TIM2 分频 -> 编译 -> pyocd 烧录。

用法:
  python py/refgen/setfreq.py 50
  python py/refgen/setfreq.py 1000 --noflash   # 只编译不烧
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))     # 项目根目录

TARGET_HZ = 72_000_000


def calc(pcs_arr_freq):
    """返回 (psc, arr, actual_hz)。72MHz/((psc+1)*(arr+1))"""
    total = int(round(TARGET_HZ / pcs_arr_freq))
    for div in range(1, 65537):
        if total % div == 0:
            arr1 = total // div
            if 2 <= arr1 <= 65536:
                return div - 1, arr1 - 1, TARGET_HZ / (div * arr1)
    raise ValueError("cannot divide %d" % total)


def zig_path():
    import ziglang
    return os.path.join(os.path.dirname(ziglang.__file__), "zig.exe")


def build(freq):
    psc, arr, actual = calc(freq)
    cache = os.path.join(ROOT, "build", "zig-cache")
    gcache = os.path.join(ROOT, "build", "zig-global-cache")
    os.makedirs(cache, exist_ok=True)
    os.makedirs(gcache, exist_ok=True)
    env = dict(os.environ)
    env["ZIG_LOCAL_CACHE_DIR"] = cache
    env["ZIG_GLOBAL_CACHE_DIR"] = gcache
    cmd = [zig_path(), "cc", "-target", "thumb-freestanding-eabi", "-mcpu=cortex_m3",
           "-Os", "-nostdlib", "-ffreestanding", "-fno-builtin",
           "-DREFGEN_PSC=%d" % psc, "-DREFGEN_ARR=%d" % arr,
           "-T", "link.ld", "-Wl,--entry=Reset_Handler", "-o", "refgen.elf", "refgen.c"]
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError("build failed:\n%s\n%s" % (r.stdout, r.stderr))
    return actual


def flash():
    cmd = [sys.executable, "-m", "pyocd", "flash", "--target", "stm32f103c8",
           "--erase", "chip", os.path.join(HERE, "refgen.elf")]
    r = subprocess.run(cmd, cwd=".", capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0
    return ok, out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    freq = float(sys.argv[1])
    psc, arr, actual = calc(freq)
    print("目标 %.3f Hz -> PSC=%d ARR=%d  实际 %.6f Hz" % (freq, psc, arr, actual))
    actual = build(freq)
    print("编译完成")
    if "--noflash" in sys.argv:
        return 0
    ok, out = flash()
    print("烧录:", "成功" if ok else "失败")
    if not ok:
        print(out[-2000:])
        return 1
    print("实际输出 %.6f Hz" % actual)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
