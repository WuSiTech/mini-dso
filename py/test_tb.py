#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""时基自测脚本 v4

对每个时基档:
  1. 通过 UART 命令 0x15 让固件在 P1.1 输出一个已知频率的方波 (慢档用 2Hz/10Hz/100Hz,
     快档直接用 9.014kHz PWM)
  2. 下发 ScaleH, 收采样帧, 用带回滞的边沿检测测出"一个周期多少个采样点"
  3. 采样间隔 = 参考周期 / 采样点数, 与标签对比得到时基偏差

用法: python py/test_tb.py [COM5] [idx列表, 如 0,1,15]
"""
import statistics
import sys
import time

sys.path.insert(0, "py")
import dso_gui as g          # noqa: E402

import serial                # noqa: E402

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
IDX_ARG = sys.argv[2] if len(sys.argv) > 2 else ""

T_TEST = 0x15
PWM_FREQ = 9014.0            # P1.1 正常 9.014kHz PWM
TICK = 72115.0 / 2.0         # Timer1 中断 72.115kHz, 每 TestDiv 次翻转
TEST_DIV_2HZ = 18029
TEST_DIV_10HZ = 3606
TEST_DIV_100HZ = 361


TEST_DIV_1KHZ = 36


def testdiv_for(idx):
    """给每个档位挑一个合适频率的参考方波, 保证 100 点帧里至少 1.2 个周期"""
    if idx <= 1:      # 500ms..300ms
        return TEST_DIV_2HZ
    if idx <= 5:      # 200ms..50ms
        return TEST_DIV_10HZ
    if idx <= 10:     # 30ms..5ms
        return TEST_DIV_100HZ
    if idx <= 14:     # 3ms..1ms
        return TEST_DIV_1KHZ
    return 0          # 500us 及更快: 用 9.014kHz PWM


class Dso:
    def __init__(self, port):
        self.ser = serial.Serial(port, 115200, timeout=0.02)
        self.parser = g.FrameParser()

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def send(self, frame):
        self.ser.write(frame)

    def drain(self, sec):
        t0 = time.time()
        while time.time() - t0 < sec:
            self.ser.read(1024)

    def get_settings(self, timeout=1.0):
        self.send(g.build_frame(g.T_GET))
        t0 = time.time()
        while time.time() - t0 < timeout:
            data = self.ser.read(1024)
            if not data:
                continue
            for t, p in self.parser.feed(data):
                if t == g.T_SETTINGS and len(p) >= g.SETTINGS_LEN:
                    return g.settings_from_bytes(p)
        return None

    def wait_scaleh(self, idx, timeout=2.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            data = self.ser.read(256)
            if not data:
                continue
            for t, p in self.parser.feed(data):
                if t == g.T_SETTINGS and len(p) >= g.SETTINGS_LEN:
                    if g.settings_from_bytes(p)["scaleh"] == idx:
                        return True
        return False

    def set_testdiv(self, div):
        self.send(g.build_frame(T_TEST, bytes([div & 0xFF, (div >> 8) & 0xFF])))
        self.drain(0.1)

    def frames(self, want=3, timeout=20.0):
        out = []
        t0 = time.time()
        while time.time() - t0 < timeout and len(out) < want:
            data = self.ser.read(1024)
            if not data:
                continue
            for t, p in self.parser.feed(data):
                if t == g.T_SAMPLE:
                    sp = g.parse_sample(p)
                    if sp:
                        out.append(sp)
        return out


def main():
    d = Dso(PORT)
    rows = []
    try:
        d.set_testdiv(0)      # 先确保不在测试方波模式
    except Exception:
        pass
    try:
        cur = d.get_settings()
        if cur is None:
            print("no SETTINGS reply on", PORT)
            return 1
        cur["trimode"] = 0
        cur["scalev_auto"] = 1
        print("settings:", {k: cur[k] for k in ("scaleh", "lsb", "outuart")})

        idxs = [int(x) for x in IDX_ARG.split(",")] if IDX_ARG else list(range(len(g.SCALE_H_TXT)))
        for idx in idxs:
            div_set = testdiv_for(idx)
            f_ref = (TICK / div_set) if div_set else PWM_FREQ
            period_ref = 1.0 / f_ref

            d.set_testdiv(div_set)
            d.drain(0.15)
            cur["scaleh"] = idx
            d.send(g.build_frame(g.T_SET, g.settings_to_bytes(cur)))
            d.drain(0.1)
            d.wait_scaleh(idx, timeout=2.0)

            target = g.SCALE_H_SEC[idx] / 25.0 * 1e6        # us
            sweep = target * 1e-6 * 220
            settle = min(30.0, sweep * 2.2 + 0.4 + 2.0 / f_ref)
            d.drain(settle)
            want = 3 if div_set else 6
            fr = d.frames(want=want, timeout=max(8.0, min(40.0, sweep * (want + 2) + 4.0)))

            pers = [g.measure_period(sp["raw"]) for sp in fr]
            pers = [p for p in pers if p]
            if not pers:
                print("%2d %-7s ref=%7.3fHz frames=%d  period too few samples"
                      % (idx, g.SCALE_H_TXT[idx], f_ref, len(fr)))
                continue
            per = statistics.mean(pers)
            iv = period_ref / per * 1e6
            row = dict(idx=idx, label=g.SCALE_H_TXT[idx], target=target, per=per,
                       interval=iv, err=(iv / target - 1.0) * 100.0)
            rows.append(row)
            print("%2d %-7s ref=%7.3fHz per=%6.2f  interval=%8.2fus  target=%8.2fus  %+6.1f%%"
                  % (idx, row["label"], f_ref, per, iv, target, row["err"]))

        print("\n%-4s %-7s %9s %10s %8s" % ("idx", "label", "target", "measured", "err%"))
        for r in rows:
            print("%-4d %-7s %8.1fus %9.1fus %+7.1f%%" % (r["idx"], r["label"], r["target"],
                                                         r["interval"], r["err"]))
        return 0
    finally:
        try:
            d.set_testdiv(0)      # 无论正常结束还是被中断, 都恢复正常 9.01kHz 方波
        except Exception:
            pass
        d.close()


if __name__ == "__main__":
    raise SystemExit(main())
