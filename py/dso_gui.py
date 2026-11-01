#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mini-DSO 上位机 (Python + tkinter)

功能:
  * 串口实时接收采样数据并显示波形（可暂停、纵向缩放、保存截图/波形）
  * 读取/修改示波器参数，除“保存设置(写EEPROM)”外全部即时生效
  * 右侧纵轴按实际电压标注 (mV / V)，带自动适配
  * 时基用滑块调节

串口协议 (115200 8N1):
  帧: A5 5A TYPE LENH LENL PAYLOAD[LEN] SUM
      SUM = (TYPE + LENH + LENL + sum(PAYLOAD)) & 0xFF
  DSO -> PC : 0x01 采样帧  0x02 ACK  0x03 设置帧
  PC -> DSO : 0x10 设置(立即生效)  0x11 保存到EEPROM  0x12 读取

采样帧负载: 22 字节头 + N*2 原始 ADC(小端)
  flags(B) ScaleH(B) PlotMode(B) TriMode(B) TriSlope(B) N(B)
  VMax(H) VMin(H) WaveFreq(I)            -- 波形最大/最小 mV、频率
  RulerVMin(H) RulerVMax(H)              -- 屏幕纵轴上下限 mV
  PlotADCMin(H) PlotADCMax(H)            -- 屏幕上下限对应的 ADC 值

用法:
  python dso_gui.py                 # 图形界面
  python dso_gui.py --demo          # 无硬件演示
  python dso_gui.py --selftest      # 协议自检
依赖: pip install pyserial   (保存截图 PNG 还需要 pillow，可选)
"""

import argparse
import csv
import os
import queue
import struct
import sys
import threading
import time

HEAD0 = 0xA5
HEAD1 = 0x5A

T_SAMPLE = 0x01
T_ACK = 0x02
T_SETTINGS = 0x03
T_SET = 0x10
T_SAVE = 0x11
T_GET = 0x12
T_INFO = 0x19       # 固件信息(版本/能力)
T_SCRL = 0x1A       # 读滚动位置
T_SCRS = 0x1B       # 写滚动位置
T_RUN = 0x1C        # 运行/暂停
T_DTM = 0x1F        # 读延时模型系数(10B)
T_DTMW = 0x20       # 写延时模型系数
T_OUTO = 0x1D       # 读输出波偏移表(21×int16)
T_OUTW = 0x1E       # 写输出波偏移表

BAUD = 115200
BAUD_CANDIDATES = [115200, 230400, 460800, 921600, 57600, 38400, 19200,
                   9600, 4800, 2400, 18000, 9570, 14350, 28700, 7200, 36000]

SCALE_H_TXT = [
    "500ms", "300ms", "200ms", "150ms", "100ms",
    "50ms", "30ms", "20ms", "15ms", "10ms",
    "5ms", "3ms", "2ms", "1.5ms", "1ms",
    "500us", "300us", "200us", "150us", "100us", "80us",
]
SCALE_H_SEC = [0.5, 0.3, 0.2, 0.15, 0.1, 0.05, 0.03, 0.02, 0.015, 0.01,
               0.005, 0.003, 0.002, 0.0015, 0.001, 500e-6, 300e-6, 200e-6,
               150e-6, 100e-6, 80e-6]
TRI_MODE_TXT = ["Auto", "Normal", "Single"]
PLOT_MODE_TXT = ["Dots", "Vect"]

# v1.2 新增: 信号源 15 档频率 / 波形类型 / 语言
GEN_FREQ_TXT = ["1Hz", "2Hz", "5Hz", "10Hz", "20Hz", "50Hz", "100Hz",
                "200Hz", "500Hz", "1kHz", "2kHz", "5kHz", "10kHz", "17kHz", "42kHz"]
SQ_FREQ_HZ = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 18000, 42000]
SQ_NOM_US10 = [10000000, 5000000, 2000000, 1000000, 500000, 200000, 100000, 50000, 20000,
               10000, 5000, 2000, 1000, 555, 238]
WV_FREQ_HZ = [8.8, 17.6, 35.2, 70.4, 140.8, 281.6]
WV_NOM_US10 = [17760, 8880, 4440, 2220, 1110, 555]
WAVE_FREQ_TXT = ["9Hz", "18Hz", "35Hz", "70Hz", "141Hz", "282Hz"]
WAVE_TYPE_TXT = ["正弦 Sine", "三角 Tri", "锯齿 Saw"]
LANG_TXT = ["中文", "English"]

# ---- 界面中英对照(按长度从长到短匹配, 所以长词优先) ----
TR_C2E = {
    "已自动识别示波器: ": "Auto-detected scope: ",
    "点「连接」": "click Connect",
    "扫描到波特率: ": "Detected baud: ",
    "校准完成并写入 EEPROM": "Calibration written to EEPROM",
    "校准写入失败": "Calibration write failed",
    "未收到任何数据": "No data received",
    "保存波形 (CSV)": "Save wave (CSV)",
    "保存截图 (PNG)": "Save shot (PNG)",
    "保存设置": "Save EEPROM",
    "示波器参数（旋转即刻生效）": "Scope parameters (live)",
    "自动识别失败，请手动选择串口": "Auto-detect failed, pick a port",
    "演示模式（无硬件）": "Demo mode (no hardware)",
    "没有波形数据": "No waveform data",
    "截图已保存": "Screenshot saved",
    "校准中...": "Calibrating...",
    "校准失败": "Calibration failed",
    "串口错误": "Serial error",
    "已断开": "Disconnected",
    "已连接": "Connected",
    "连接失败": "Connect failed",
    "请选择串口": "Select a port",
    "时基校准": "Time cal",
    "一键校准": "Time cal",
    "绘图模式": "Plot mode",
    "电压量程": "Range",
    "触发电平": "Trig level",
    "触发方式": "Trig mode",
    "触发沿": "Trig slope",
    "方波频率": "PWM freq",
    "波形类型": "Wave type",
    "波形频率": "Wave freq",
    "设备语言": "DSO lang",
    "纵向缩放": "V zoom",
    "自动适配": "Auto-fit",
    "亮度": "Brightness",
    "时基": "Time base",
    "占空比": "Duty",
    "已保存": "Saved",
    "截图失败": "Screenshot failed",
    "保存失败": "Save failed",
    "保存中...": "Saving...",
    "停止演示": "Stop demo",
    "演示模式": "Demo mode",
    "没有数据": "No data",
    "刷新": "Refresh",
    "已暂停": "PAUSED",
    "继续": "Resume",
    "连接": "Connect",
    "断开": "Disconnect",
    "读取": "Read",
    "暂停": "Pause",
    "频谱": "FFT",
    "波形": "Wave",
    "输出": "Output",
    "显示": "Display",
    "上升": "Rise",
    "下降": "Fall",
    "点": "Dots",
    "线": "Vect",
    "帧": "fr",
    "校准": "Calibrate",
}
TR_E2C = {}
for _k, _v in TR_C2E.items():
    TR_E2C.setdefault(_v, _k)

try:
    import serial
    from serial.tools import list_ports
    HAVE_SERIAL = True
except Exception:                                     # pragma: no cover
    HAVE_SERIAL = False
    serial = None
    list_ports = None

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    HAVE_TK = True
except Exception:                                     # pragma: no cover
    HAVE_TK = False
    tk = None
    ttk = None

try:
    from PIL import ImageGrab
    HAVE_PIL = True
except Exception:                                     # pragma: no cover
    HAVE_PIL = False


# --------------------------------------------------------------------------
# 协议
# --------------------------------------------------------------------------
def build_frame(type_, payload=b""):
    n = len(payload)
    hi, lo = (n >> 8) & 0xFF, n & 0xFF
    chk = (type_ + hi + lo + sum(payload)) & 0xFF
    return bytes([HEAD0, HEAD1, type_, hi, lo]) + bytes(payload) + bytes([chk])


class FrameParser:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        self.buf += data
        frames = []
        while True:
            i = self.buf.find(bytes([HEAD0, HEAD1]))
            if i < 0:
                if len(self.buf) > 1:
                    self.buf = self.buf[-1:]
                break
            if i > 0:
                del self.buf[:i]
            if len(self.buf) < 6:
                break
            type_ = self.buf[2]
            ln = (self.buf[3] << 8) | self.buf[4]
            if len(self.buf) < 6 + ln:
                break
            payload = bytes(self.buf[5:5 + ln])
            chk = self.buf[5 + ln]
            good = ((type_ + self.buf[3] + self.buf[4] + sum(payload)) & 0xFF) == chk
            del self.buf[:6 + ln]
            if good:
                frames.append((type_, payload))
        return frames


SETTINGS_FIELDS = [
    ("lsb", "H"), ("plotmode", "B"), ("scaleh", "B"), ("scalev_auto", "B"),
    ("rulervmax", "H"), ("rulervmin", "H"), ("trilevel", "H"),
    ("trimode", "B"), ("trislope", "B"), ("wavescroll", "B"),
    ("brightness", "B"), ("outpwm", "B"), ("outsin", "B"), ("outuart", "B"),
    ("genfreq", "B"), ("genduty", "B"), ("wavetype", "B"), ("lang", "B"),
]
SETTINGS_FMT = "<" + "".join(f for _, f in SETTINGS_FIELDS)
SETTINGS_LEN = struct.calcsize(SETTINGS_FMT)


def settings_from_bytes(payload):
    vals = struct.unpack(SETTINGS_FMT, payload[:SETTINGS_LEN])
    return {name: vals[i] for i, (name, _) in enumerate(SETTINGS_FIELDS)}


def settings_to_bytes(s):
    vals = []
    for name, _ in SETTINGS_FIELDS:
        v = int(s.get(name, 0))
        if v < 0:
            v += 65536
        vals.append(v & 0xFFFF)
    return struct.pack(SETTINGS_FMT, *vals)


SAMPLE_HDR_FMT = "<BBBBBBHHIHHHHHHH"
SAMPLE_HDR_LEN = struct.calcsize(SAMPLE_HDR_FMT)      # 28


def parse_sample(payload):
    if len(payload) < SAMPLE_HDR_LEN:
        return None
    (flags, scaleh, plotmode, trimode, trislope, n,
     vmax, vmin, freq, rvmin, rvmax, pamin, pamax,
     bgv, adcbg, lsb) = \
        struct.unpack(SAMPLE_HDR_FMT, payload[:SAMPLE_HDR_LEN])
    n = min(n, (len(payload) - SAMPLE_HDR_LEN) // 2)
    raw = struct.unpack("<%dH" % n, payload[SAMPLE_HDR_LEN:SAMPLE_HDR_LEN + 2 * n])
    return {
        "running": bool(flags & 0x01),
        "trifail": bool(flags & 0x02),
        "auto": bool(flags & 0x04),
        "scaleh": scaleh, "plotmode": plotmode, "trimode": trimode,
        "trislope": trislope, "vmax": vmax, "vmin": vmin, "freq": freq,
        "rvmin": rvmin, "rvmax": rvmax, "pamin": pamin, "pamax": pamax,
        "bgv": bgv, "adcbg": adcbg, "lsb": lsb,
        "raw": list(raw),
    }


def raw_to_mv(sp, raw):
    """原始 ADC -> mV，与固件完全相同的公式: raw*BGV*Lsb/ADCbg/100"""
    bgv, adcbg, lsb = sp.get("bgv", 0), sp.get("adcbg", 0), sp.get("lsb", 0)
    if bgv > 0 and adcbg > 0 and lsb > 0:
        return raw * bgv * lsb / adcbg / 100.0
    den = sp["pamax"] - sp["pamin"]
    if den == 0:
        den = 1
    return sp["rvmin"] + (raw - sp["pamin"]) * (sp["rvmax"] - sp["rvmin"]) / den


PWM_FREQ_NOMINAL = 9014.0   # 固件 P1.1 方波的设计频率 (Hz)，由 Timer1 精确分频


def measure_period(raw):
    """从原始 ADC 序列里测周期(样本数)：带回滞的上升沿检测 + 中值"""
    n = len(raw)
    if n < 12:
        return None
    lo_v, hi_v = min(raw), max(raw)
    amp = hi_v - lo_v
    if amp < 100:
        return None
    th = (lo_v + hi_v) / 2.0
    hyst = max(20.0, amp * 0.15)
    hi_th, lo_th = th + hyst / 2.0, th - hyst / 2.0
    edges = []
    armed = True
    for i, v in enumerate(raw):
        if armed and v >= hi_th:
            edges.append(i)
            armed = False
        elif (not armed) and v <= lo_th:
            armed = True
    if len(edges) < 2:
        return None
    diffs = [b - a for a, b in zip(edges, edges[1:])]
    diffs = [d for d in diffs if d >= 2]
    if not diffs:
        return None
    diffs.sort()
    med = diffs[len(diffs) // 2]
    # 一致性检查: 抖动太大说明波形/触发不稳，放弃
    if med <= 0 or max(diffs) > med * 1.6 or min(diffs) < med * 0.6:
        return None
    # 用整帧首尾边沿算平均周期(浮点)，比中值精度高
    span = edges[-1] - edges[0]
    if span > 0:
        return span / float(len(edges) - 1)
    return float(med)

def fmt_mv(mv):
    if abs(mv) >= 1000:
        return "%.2fV" % (mv / 1000.0)
    return "%.0fmV" % mv


def fmt_time(sec):
    if sec >= 1:
        return "%.2fs" % sec
    if sec >= 1e-3:
        return "%.2fms" % (sec * 1e3)
    return "%.1fus" % (sec * 1e6)


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------
def run_selftest():
    ok = True

    payload = bytes(range(20))
    parser = FrameParser()
    got = []
    for b in build_frame(T_SET, payload):
        got += parser.feed(bytes([b]))
    if len(got) != 1 or got[0][1] != payload:
        print("FAIL: frame parse"); ok = False
    else:
        print("OK  : frame parse")

    parser = FrameParser()
    frames = parser.feed(b"\x00\x11" + build_frame(T_ACK, b"\x00\x01") + build_frame(T_SETTINGS, bytes(18)))
    if [t for t, _ in frames] != [T_ACK, T_SETTINGS]:
        print("FAIL: stream parse"); ok = False
    else:
        print("OK  : stream parse")

    s = dict(lsb=600, plotmode=1, scaleh=4, scalev_auto=0, rulervmax=3000, rulervmin=0,
             trilevel=1500, trimode=0, trislope=1, wavescroll=0, brightness=10,
             outpwm=1, outsin=1, outuart=1, genfreq=0, genduty=50, wavetype=0, lang=0)
    b = settings_to_bytes(s)
    if len(b) != SETTINGS_LEN or settings_from_bytes(b) != s:
        print("FAIL: settings roundtrip"); ok = False
    else:
        print("OK  : settings roundtrip (18 bytes)")

    hdr = struct.pack(SAMPLE_HDR_FMT, 0x01, 4, 1, 0, 1, 100, 3300, 0, 12345,
                      0, 3300, 100, 3900, 1349, 1674, 600)
    samples = struct.pack("<100H", *[(i * 20) & 0xFFF for i in range(100)])
    sp = parse_sample(hdr + samples)
    if not sp or len(sp["raw"]) != 100 or sp["freq"] != 12345:
        print("FAIL: sample parse"); ok = False
    else:
        mv0 = raw_to_mv(sp, sp["pamin"])
        mv1 = raw_to_mv(sp, sp["pamax"])
        print("OK  : sample parse (100 pts), mv range %.1f..%.1f" % (mv0, mv1))

    parser = FrameParser()
    bad = bytearray(build_frame(T_ACK, b"\x00\x01"))
    bad[-1] ^= 0xFF
    if parser.feed(bytes(bad)):
        print("FAIL: bad checksum accepted"); ok = False
    else:
        print("OK  : bad checksum rejected")

    print("SELFTEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


# --------------------------------------------------------------------------
# 串口线程
# --------------------------------------------------------------------------
class Link(threading.Thread):
    def __init__(self, port, rx_queue, baud=BAUD):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.rx_queue = rx_queue
        self.ser = None
        self.running = False
        self.send_lock = threading.Lock()
        self.rx_bytes = 0
        self.rx_frames = 0

    def open(self):
        if not HAVE_SERIAL:
            raise RuntimeError("pyserial 未安装")
        self.ser = serial.Serial(self.port, self.baud, timeout=0.03)
        self.running = True
        self.start()

    def run(self):
        parser = FrameParser()
        while self.running:
            try:
                data = self.ser.read(256)
            except Exception as exc:
                self.rx_queue.put(("error", str(exc)))
                break
            if data:
                self.rx_bytes += len(data)
                for type_, payload in parser.feed(data):
                    self.rx_frames += 1
                    self.rx_queue.put(("frame", (type_, payload)))
        self.running = False

    def send(self, data):
        if not self.ser:
            return False
        with self.send_lock:
            try:
                self.ser.write(data)
                return True
            except Exception as exc:
                self.rx_queue.put(("error", str(exc)))
                return False

    def close(self):
        self.running = False
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            pass
        self.ser = None


class DemoSource(threading.Thread):
    def __init__(self, rx_queue):
        super().__init__(daemon=True)
        self.rx_queue = rx_queue
        self.running = True
        self.phase = 0.0

    def run(self):
        import math
        while self.running:
            n = 100
            self.phase += 0.15
            raw = [int(2048 + 900 * math.sin(2 * math.pi * i / 25 + self.phase)) for i in range(n)]
            hdr = struct.pack(SAMPLE_HDR_FMT, 0x01, 8, 1, 0, 1, n, 3300, 0, 1000,
                              0, 3300, 100, 4000, 1349, 1674, 600)
            payload = hdr + struct.pack("<%dH" % n, *[max(0, min(4095, v)) for v in raw])
            self.rx_queue.put(("frame", (T_SAMPLE, payload)))
            time.sleep(0.05)

    def stop(self):
        self.running = False


# --------------------------------------------------------------------------
# 界面
# --------------------------------------------------------------------------

class _Tip:
    """轻量悬停提示: 鼠标停留 350ms 显示, 跟随光标; 文本可为 str 或 callable"""
    _win = None
    _job = None

    def __init__(self, widget, text, delay=350):
        self.w = widget
        self.text = text
        self.delay = delay
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, _ev=None):
        self._cancel()
        self._job = self.w.after(self.delay, self._show)

    def _leave(self, _ev=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._job is not None:
            try:
                self.w.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _show(self):
        self._job = None
        txt = self.text() if callable(self.text) else self.text
        if not txt:
            return
        _Tip._hide()
        x, y = self.w.winfo_pointerxy()
        win = tk.Toplevel(self.w)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        lab = tk.Label(win, text=txt, justify="left", bg="#ffffe0", fg="#333",
                       relief="solid", bd=1, padx=6, pady=3,
                       font=("Segoe UI", 9), wraplength=300)
        lab.pack()
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        px = min(x + 14, sw - w - 8)
        py = min(y + 18, sh - h - 8)
        win.wm_geometry("+%d+%d" % (px, py))
        _Tip._win = win

    @classmethod
    def _hide(cls):
        if cls._win is not None:
            try:
                cls._win.destroy()
            except Exception:
                pass
            cls._win = None

class App:
    def __init__(self, root, demo=False):
        self.root = root
        self.demo = False
        self.rx_queue = queue.Queue()
        self.link = None
        self.demo_src = None
        self.samples = []
        self.last = {}
        self.paused = False
        self.pending_save = 0.0
        self.pending_get = 0.0
        self.scanning = False
        self.last_canvas = None
        self._updating = False
        self._apply_job = None
        self.hzoom = 1.0          # 横向缩放(1=整个缓冲区)
        self.hcenter = 0.5        # 横向中心(0..1)
        self._drag_x = None
        self.lang = 'cn'          # 界面语言 cn/en
        self.view_mode = 'wave'   # wave / fft
        self.cur = [None, None]   # 两个光标的样本位置
        self._cur_drag = None
        self.cal_busy = False
        self.stat = {}
        self.fw_ver = ""

        self.zoom = tk.DoubleVar(value=1.0)
        self.autofit = tk.IntVar(value=1)

        root.title("Mini-DSO 上位机 (cpv)")
        root.geometry("1280x760")
        root.minsize(980, 600)

        self._build_ui()
        self._translate_widgets(to_en=False)   # 初始中文: Dots/Vect -> 点/线
        self.root.after(400, self._autodetect_port)  # 启动时自动识别示波器串口
        self.root.after(30, self._tick)
        self._keep_awake()                      # 运行期间阻止系统息屏
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if demo:
            self._start_demo()

    # ---------------- 阻止息屏 / 退出 ----------------
    def _keep_awake(self):
        """Windows: 让显示器与系统保持唤醒, 直到程序退出"""
        self._es = None
        if sys.platform != "win32":
            return
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            self._es = ctypes.windll.kernel32
            r = self._es.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
            if r == 0:
                self._es = None
        except Exception:
            self._es = None

    def _allow_sleep(self):
        """恢复系统默认息屏策略"""
        try:
            if getattr(self, "_es", None) is not None:
                self._es.SetThreadExecutionState(0x80000000)   # ES_CONTINUOUS 单独用 = 清除
                self._es = None
        except Exception:
            pass

    def _on_close(self):
        self._allow_sleep()
        try:
            if self.link:
                self.link.close()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    # ---------------- UI ----------------
    def _build_ui(self):
        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True)

        # ================= 左侧: 波形 =================
        left = tk.Frame(main)
        left.pack(side="left", fill="both", expand=True, padx=(6, 0))

        # ================= 左栏最底端: 文字信息条 =================
        self.textbar = tk.Frame(left, bd=1, relief="sunken")
        self.textbar.pack(side="bottom", fill="x", pady=(2, 2))

        self.status = tk.StringVar(value="未连接")
        tk.Label(left, textvariable=self.status, anchor="w",
                 font=("Consolas", 10)).pack(fill="x")
        self.canvas = tk.Canvas(left, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=4)
        self.canvas.bind("<Configure>", lambda e: self._redraw(force=True))
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "_cur_drag", None))
        self.canvas.bind("<Double-Button-1>", self._on_double)
        self.canvas.bind("<Shift-Button-1>", self._on_shift_click)
        # 波形滚动条(与单片机同步, 仅暂停时可用)
        sf = tk.Frame(left)
        sf.pack(fill="x", padx=6, pady=(0, 2))
        self.scr_lbl = tk.Label(sf, text="滚动", width=5, anchor="w")
        self.scr_lbl.pack(side="left")
        self.scr_var = tk.DoubleVar(value=0)
        self.scr_scale = ttk.Scale(sf, from_=0, to=120, orient="horizontal",
                                   variable=self.scr_var, command=self._on_scroll_slider)
        self.scr_scale.pack(side="left", fill="x", expand=True)
        self.scr_val = tk.Label(sf, text="0", width=5, anchor="e")
        self.scr_val.pack(side="left")
        self.scr_scale.config(state="disabled")
        self.scr_scale.bind("<ButtonPress-1>", lambda e: setattr(self, "_scr_drag", True))
        self.scr_scale.bind("<ButtonRelease-1>", lambda e: setattr(self, "_scr_drag", False))

        self.hexlabel = tk.Label(left, text="", anchor="w", font=("Consolas", 9), fg="#666")
        self.hexlabel.pack(fill="x", padx=8)

        # ================= 右侧 =================
        right = tk.Frame(main, width=376)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        # ---- 底部固定区(按钮 + 状态) ----
        bot = tk.Frame(right)
        bot.pack(side="bottom", fill="x", padx=6, pady=(2, 4))

        self.save_msg = tk.StringVar(value="")
        tk.Label(self.textbar, textvariable=self.save_msg, fg="green", anchor="w",
                 font=("Segoe UI", 10, "bold")).pack(fill="x")
        self.hint = tk.Label(self.textbar, text="", anchor="w", justify="left",
                             fg="#a04000", font=("Segoe UI", 9))
        self.hint.pack(fill="x")
        self.stat_lbl = tk.Label(self.textbar, text="", anchor="w", justify="left",
                                 font=("Consolas", 9), fg="#0a6")
        self.stat_lbl.pack(fill="x")
        self.info = tk.Label(self.textbar, text="", anchor="w", justify="left",
                             font=("Consolas", 9))
        self.info.pack(fill="x")

        # ---- 按钮网格 (3 列 x 3 行, 单独一个 Frame 用 grid) ----
        # ---- 按钮区: 按功能分组, 校准类做成"两级" ----
        def srow(text):
            f = tk.Frame(bot)
            f.pack(fill="x", pady=(2, 0))
            tk.Label(f, text=text, anchor="w", fg="#555",
                     font=("Segoe UI", 8, "bold")).pack(side="top", anchor="w", padx=4)
            g = tk.Frame(f)
            g.pack(fill="x")
            return g

        def btns(parent, specs):
            for i, (txt, cb) in enumerate(specs):
                parent.columnconfigure(i, weight=1, uniform="b%d" % i)
                tk.Button(parent, text=txt, command=cb).grid(
                    row=0, column=i, padx=2, pady=0, sticky="ew")

        f = srow("运行")
        self.btn_pause = tk.Button(f, text="暂停", command=self._toggle_pause)
        self.btn_pause.grid(row=0, column=0, padx=2, pady=0, sticky="ew")

        self.btn_read = tk.Button(f, text="读取", command=self._read_all)
        self.btn_read.grid(row=0, column=1, padx=2, pady=1, sticky="ew")
        self.btn_save = tk.Button(f, text="保存设置", command=self._save)
        self.btn_save.grid(row=0, column=2, padx=2, pady=1, sticky="ew")
        f.columnconfigure(0, weight=1, uniform="pb"); f.columnconfigure(1, weight=1, uniform="pb")

        f = srow("导出")
        self.btn_wave = tk.Button(f, text="保存波形 CSV", command=self._save_wave)
        self.btn_wave.grid(row=0, column=0, padx=2, pady=1, sticky="ew")
        self.btn_shot = tk.Button(f, text="保存截图 PNG", command=self._save_shot)
        self.btn_shot.grid(row=0, column=1, padx=2, pady=1, sticky="ew")
        f.columnconfigure(0, weight=1, uniform="ex"); f.columnconfigure(1, weight=1, uniform="ex")

        f = srow("视图 / 界面")
        self.btn_view = tk.Button(f, text="频谱", command=self._toggle_view)
        self.btn_view.grid(row=0, column=0, padx=2, pady=1, sticky="ew")
        self.btn_cur = tk.Button(f, text="光标", command=self._toggle_cursors)
        self.btn_cur.grid(row=0, column=1, padx=2, pady=1, sticky="ew")
        self.btn_lang = tk.Button(f, text="English", command=self._toggle_lang)
        self.btn_lang.grid(row=0, column=2, padx=2, pady=1, sticky="ew")
        for i in range(3):
            f.columnconfigure(i, weight=1, uniform="vw")

        f = srow("校准 · 设备自校")
        self.btn_cal = tk.Button(f, text="时基自校", command=self._calibrate)
        self.btn_cal.grid(row=0, column=0, padx=2, pady=1, sticky="ew")
        self.btn_outcal = tk.Button(f, text="输出波偏移表", command=self._open_outcal)
        self.btn_outcal.grid(row=0, column=1, padx=2, pady=1, sticky="ew")
        for i in range(2):
            f.columnconfigure(i, weight=1, uniform="cal")

        f = srow("校准 · 声卡绝对基准 (需接线)")
        self.btn_tbcal = tk.Button(f, text="校时基", command=self._audio_tb_calibrate)
        self.btn_tbcal.grid(row=0, column=0, padx=2, pady=1, sticky="ew")
        self.btn_sqcal = tk.Button(f, text="校方波输出", command=lambda: self._audio_out_cal("sq"))
        self.btn_sqcal.grid(row=0, column=1, padx=2, pady=1, sticky="ew")
        self.btn_wvcal = tk.Button(f, text="校波形输出", command=lambda: self._audio_out_cal("wv"))
        self.btn_wvcal.grid(row=0, column=2, padx=2, pady=1, sticky="ew")
        for i in range(3):
            f.columnconfigure(i, weight=1, uniform="aud")

        # 文字条换行宽度跟随窗口宽度
        self.textbar.bind("<Configure>",
                          lambda e: self.hint.config(wraplength=max(200, e.width - 16)))

        self._add_tips()

        wrap = tk.Frame(right)
        wrap.pack(side="top", fill="both", expand=True)
        scr = tk.Scrollbar(wrap, orient="vertical")
        scr.pack(side="right", fill="y")
        scrv = tk.Canvas(wrap, highlightthickness=0, width=352)
        scrv.pack(side="left", fill="both", expand=True)
        scrv.configure(yscrollcommand=scr.set)
        scr.config(command=scrv.yview)
        panel = tk.Frame(scrv)
        scrv.create_window((0, 0), window=panel, anchor="nw", width=352)
        panel.bind("<Configure>", lambda e: scrv.configure(scrollregion=scrv.bbox("all")))
        scrv.bind("<MouseWheel>", lambda e: scrv.yview_scroll(-1 if getattr(e, "delta", 0) > 0 else 1, "units"))
        panel.bind("<MouseWheel>", lambda e: scrv.yview_scroll(-1 if getattr(e, "delta", 0) > 0 else 1, "units"))

        # --- 连接 ---
        box = tk.LabelFrame(panel, text="连接")
        box.pack(fill="x", padx=2, pady=1)
        self.port_var = tk.StringVar(value="")
        self.ports = [p.device for p in list_ports.comports()] if (HAVE_SERIAL and list_ports) else []
        self.port_box = ttk.Combobox(box, textvariable=self.port_var, values=self.ports, width=7)
        self.port_box.pack(side="left", padx=2, pady=2)
        self.baud_var = tk.StringVar(value=str(BAUD))
        ttk.Combobox(box, textvariable=self.baud_var, values=[str(b) for b in BAUD_CANDIDATES],
                     width=6).pack(side="left", padx=1)
        self.btn_connect = tk.Button(box, text="连接", width=5, command=self._toggle_connect)
        self.btn_connect.pack(side="left", padx=1)
        tk.Button(box, text="刷新", width=4, command=self._refresh_ports).pack(side="left", padx=1)

        # --- 示波器参数 ---
        p = tk.LabelFrame(panel, text="示波器参数（旋转即刻生效）")
        p.pack(fill="x", padx=2, pady=1)
        p.columnconfigure(1, weight=1)
        row = 0

        self.v_pmode = tk.IntVar(value=1)
        self.v_lsb = tk.IntVar(value=600)
        self.v_brt = tk.IntVar(value=10)
        self.v_scaleh = tk.IntVar(value=4)
        self.v_auto = tk.IntVar(value=0)
        self.v_vmax = tk.IntVar(value=3300)
        self.v_vmin = tk.IntVar(value=0)
        self.v_tri = tk.IntVar(value=1600)
        self.v_slope = tk.IntVar(value=1)
        self.v_trmode = tk.StringVar(value="Auto")
        self.v_outpwm = tk.IntVar(value=1)
        self.v_outsin = tk.IntVar(value=1)
        self.v_outuart = tk.IntVar(value=1)
        self.v_genfreq = tk.IntVar(value=0)
        self.v_genduty = tk.IntVar(value=50)
        self.v_wavefreq = tk.IntVar(value=2)
        self.v_wavefreq_txt = tk.StringVar(value=WAVE_FREQ_TXT[2])

        self.v_wavetype = tk.IntVar(value=0)
        self.v_lang = tk.IntVar(value=0)
        self.v_genfreq_txt = tk.StringVar(value=GEN_FREQ_TXT[0])
        self.v_wavetype_txt = tk.StringVar(value=WAVE_TYPE_TXT[0])
        self.v_lang_txt = tk.StringVar(value=LANG_TXT[0])

        def lab(text):
            nonlocal row
            tk.Label(p, text=text, anchor="w").grid(row=row, column=0, sticky="w", padx=3, pady=0)

        # 绘图模式
        lab("绘图模式")
        f = tk.Frame(p)
        f.grid(row=row, column=1, sticky="w")
        tk.Radiobutton(f, text="点", variable=self.v_pmode, value=0,
                       command=self._schedule_apply).pack(side="left")
        tk.Radiobutton(f, text="线", variable=self.v_pmode, value=1,
                       command=self._schedule_apply).pack(side="left")
        row += 1

        # LSB / 亮度
        lab("分压系数 LSB")
        tk.Spinbox(p, from_=50, to=750, textvariable=self.v_lsb, width=7,
                   command=self._schedule_apply).grid(row=row, column=1, sticky="w")
        row += 1

        lab("亮度 BRT")
        tk.Spinbox(p, from_=1, to=25, textvariable=self.v_brt, width=7,
                   command=self._schedule_apply).grid(row=row, column=1, sticky="w")
        row += 1

        # 时基
        lab("时基")
        f = tk.Frame(p)
        f.grid(row=row, column=1, sticky="ew")
        self.scaleh_lbl = tk.StringVar(value=SCALE_H_TXT[4])
        self.scaleh_var = tk.DoubleVar(value=4.0)
        ttk.Scale(f, from_=0, to=len(SCALE_H_TXT) - 1, orient="horizontal",
                  variable=self.scaleh_var, command=self._on_scaleh).pack(side="left", fill="x", expand=True)
        tk.Label(f, textvariable=self.scaleh_lbl, width=6, anchor="e").pack(side="left")
        row += 1

        # 量程
        lab("电压量程")
        f = tk.Frame(p)
        f.grid(row=row, column=1, sticky="w")
        tk.Checkbutton(f, text="AUTO", variable=self.v_auto,
                       command=self._schedule_apply).pack(side="left")
        tk.Label(f, text="max").pack(side="left")
        tk.Spinbox(f, from_=0, to=30000, increment=100, textvariable=self.v_vmax, width=5,
                   command=self._schedule_apply).pack(side="left")
        tk.Label(f, text="min").pack(side="left")
        tk.Spinbox(f, from_=0, to=30000, increment=100, textvariable=self.v_vmin, width=5,
                   command=self._schedule_apply).pack(side="left")
        row += 1

        # 触发电平
        lab("触发电平")
        f = tk.Frame(p)
        f.grid(row=row, column=1, sticky="w")
        tk.Spinbox(f, from_=0, to=30000, increment=100, textvariable=self.v_tri, width=6,
                   command=self._schedule_apply).pack(side="left")
        tk.Label(f, text="mV").pack(side="left")
        row += 1

        # 触发沿
        lab("触发沿")
        f = tk.Frame(p)
        f.grid(row=row, column=1, sticky="w")
        tk.Radiobutton(f, text="上升", variable=self.v_slope, value=1,
                       command=self._schedule_apply).pack(side="left")
        tk.Radiobutton(f, text="下降", variable=self.v_slope, value=0,
                       command=self._schedule_apply).pack(side="left")
        row += 1

        # 触发方式
        lab("触发方式")
        ttk.Combobox(p, textvariable=self.v_trmode, values=TRI_MODE_TXT, width=7,
                     state="readonly").grid(row=row, column=1, sticky="w")
        self.v_trmode.trace_add("write", lambda *a: self._schedule_apply())
        row += 1

        # 输出开关
        lab("输出开关")
        f = tk.Frame(p)
        f.grid(row=row, column=1, sticky="w")
        tk.Checkbutton(f, text="PWM", variable=self.v_outpwm,
                       command=self._schedule_apply).pack(side="left")
        tk.Checkbutton(f, text="SIN", variable=self.v_outsin,
                       command=self._schedule_apply).pack(side="left")
        tk.Checkbutton(f, text="UART", variable=self.v_outuart,
                       command=self._schedule_apply).pack(side="left")
        row += 1

        # 信号源
        lab("方波频率")
        cb = ttk.Combobox(p, textvariable=self.v_genfreq_txt, values=GEN_FREQ_TXT,
                          width=7, state="readonly")
        cb.grid(row=row, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_enum_change())
        row += 1

        lab("占空比")
        sp = tk.Spinbox(p, from_=1, to=99, textvariable=self.v_genduty, width=7,
                        command=self._schedule_apply)
        sp.grid(row=row, column=1, sticky="w")
        sp.bind("<KeyRelease>", lambda e: self._schedule_apply())
        row += 1

        lab("波形类型")
        cbw = ttk.Combobox(p, textvariable=self.v_wavetype_txt, values=WAVE_TYPE_TXT,
                           width=9, state="readonly")
        cbw.grid(row=row, column=1, sticky="w")
        lab("波形频率")
        cbf = ttk.Combobox(p, textvariable=self.v_wavefreq_txt, values=WAVE_FREQ_TXT,
                           width=10, state="readonly")
        cbf.grid(row=row, column=1, sticky="w")
        cbf.bind("<<ComboboxSelected>>", lambda e: self._schedule_apply())
        row += 1
        cbw.bind("<<ComboboxSelected>>", lambda e: self._on_enum_change())
        row += 1

        lab("设备语言")
        cbl = ttk.Combobox(p, textvariable=self.v_lang_txt, values=LANG_TXT,
                           width=7, state="readonly")
        cbl.grid(row=row, column=1, sticky="w")
        cbl.bind("<<ComboboxSelected>>", lambda e: self._on_enum_change())
        row += 1

        # --- 显示 ---
        d = tk.LabelFrame(panel, text="显示")
        d.pack(fill="x", padx=2, pady=1)
        d.columnconfigure(1, weight=1)
        tk.Label(d, text="纵向缩放").grid(row=0, column=0, sticky="w", padx=3)
        f = tk.Frame(d)
        f.grid(row=0, column=1, sticky="ew")
        ttk.Scale(f, from_=0.5, to=10.0, orient="horizontal", variable=self.zoom,
                  command=lambda v: self._redraw(force=True)).pack(side="left", fill="x", expand=True)
        tk.Checkbutton(f, text="自动适配", variable=self.autofit,
                       command=lambda: self._redraw(force=True)).pack(side="left")
        self.zoom_lbl = tk.Label(d, text="", anchor="w", font=("Consolas", 9))
        self.zoom_lbl.grid(row=1, column=0, columnspan=2, sticky="w", padx=3)
        tk.Frame(panel, height=6).pack()

        if not HAVE_SERIAL:
            self._hint("pyserial 未安装（pip install pyserial），可用 --demo 演示")

    # ---------------- 中英切换 ----------------
    def _tr(self, text):
        """把当前界面语言对应的字符串翻译成另一种"""
        if not isinstance(text, str):
            return text
        table = TR_C2E if self.lang == "en" else TR_E2C
        for k in sorted(table, key=len, reverse=True):
            if k in text:
                text = text.replace(k, table[k])
        return text

    def _translate_widgets(self, widget=None, to_en=None):
        if widget is None:
            widget = self.root
        if to_en is None:
            to_en = (self.lang == "en")
        table = TR_C2E if to_en else TR_E2C
        keys = sorted(table, key=len, reverse=True)
        for w in widget.winfo_children():
            try:
                cur = w.cget("text")
            except Exception:
                cur = None
            if cur:
                new = cur
                for k in keys:
                    if k in new:
                        new = new.replace(k, table[k])
                if new != cur:
                    try:
                        w.config(text=new)
                    except Exception:
                        pass
            self._translate_widgets(w, to_en)

    def _status(self, text):
        self.status.set(self._tr(text))

    def _msg(self, text):
        self.save_msg.set(self._tr(text))

    def _hint(self, text):
        self.hint.config(text=self._tr(text))

    def _info(self, text):
        self.info.config(text=self._tr(text))

    def _stat(self, text):
        self.stat_lbl.config(text=self._tr(text))

    def _zoom(self, text):
        self.zoom_lbl.config(text=self._tr(text))

    def _btnconnect(self, text):
        self.btn_connect.config(text=self._tr(text))

    def _btnpause(self, text):
        self.btn_pause.config(text=self._tr(text))

    # ---------------- 启动时自动识别示波器 ----------------
    def _autodetect_port(self):
        if not HAVE_SERIAL:
            return
        settings0 = self._collect()   # 主线程先取参数快照(子线程不能碰 Tk)

        def worker():
            found = None
            try:
                ports = [p.device for p in list_ports.comports()]
            except Exception:
                ports = []
            for dev in ports:
                if found:
                    break
                try:
                    ser = serial.Serial(dev, BAUD, timeout=0.25)
                except Exception:
                    continue
                try:
                    ser.reset_input_buffer()
                    ser.write(build_frame(T_INFO))
                    parser = FrameParser()
                    deadline = time.time() + 0.6
                    while time.time() < deadline and not found:
                        d = ser.read(256)
                        if not d:
                            continue
                        for t, pl in parser.feed(d):
                            if t in (T_INFO, T_SETTINGS) and len(pl) >= 8:
                                found = dev
                                break
                except Exception:
                    pass
                finally:
                    try:
                        ser.close()
                    except Exception:
                        pass
            self.rx_queue.put(("autodetect", found))
        threading.Thread(target=worker, daemon=True).start()

    def _on_autodetect(self, dev):
        try:
            self.ports = [p.device for p in list_ports.comports()]
        except Exception:
            pass
        if dev and dev not in self.ports:
            self.ports.append(dev)
        self.port_box["values"] = self.ports
        if dev:
            self.port_var.set(dev)
            self._hint(self._tr("已自动识别示波器: %s，点「连接」" % dev))
        else:
            self._hint(self._tr("自动识别失败，请手动选择串口"))

    def _refresh_ports(self):
        if HAVE_SERIAL:
            self.ports = [p.device for p in list_ports.comports()]
            self.port_box["values"] = self.ports
            if self.ports and not self.port_var.get():
                self.port_var.set(self.ports[0])

    # ---------------- 连接 ----------------
    def _toggle_connect(self):
        if self.demo:
            self._stop_demo()
            self._status("演示模式已停止")
            self._btnconnect("连接")
            return
        if self.link and self.link.is_alive():
            self.link.close()
            self.link = None
            self._btnconnect("连接")
            self._status("已断开")
            return
        if not HAVE_SERIAL:
            self._msg("需要 pyserial: pip install pyserial")
            return
        port = self.port_var.get().strip()
        if not port:
            self._msg("请选择串口")
            return
        try:
            baud = int(self.baud_var.get())
        except Exception:
            baud = BAUD
        try:
            self.link = Link(port, self.rx_queue, baud)
            self.link.open()
        except Exception as exc:
            self.link = None
            self._msg("打开失败: %s" % exc)
            return
        self._btnconnect("断开")
        self._status("已连接 %s @%d" % (port, baud))
        self._hint("")
        self.root.after(300, self._read_all)

    def _start_demo(self):
        self.demo = True
        self.demo_src = DemoSource(self.rx_queue)
        self.demo_src.start()
        self._status("演示模式 (无硬件)")
        self._btnconnect("停止演示")

    def _stop_demo(self):
        if self.demo_src:
            self.demo_src.stop()
            self.demo_src = None
        self.demo = False

    # ---------------- 参数下发（即时） ----------------
    def _on_scaleh(self, val):
        idx = int(round(float(val)))
        if idx < 0:
            idx = 0
        if idx >= len(SCALE_H_TXT):
            idx = len(SCALE_H_TXT) - 1
        self.v_scaleh.set(idx)
        self.scaleh_lbl.set(SCALE_H_TXT[idx])
        self._schedule_apply()

    def _collect(self):
        return dict(
            lsb=int(self.v_lsb.get()), plotmode=int(self.v_pmode.get()),
            scaleh=int(self.v_scaleh.get()), scalev_auto=int(self.v_auto.get()),
            rulervmax=int(self.v_vmax.get()), rulervmin=int(self.v_vmin.get()),
            trilevel=int(self.v_tri.get()), trimode=TRI_MODE_TXT.index(self.v_trmode.get()),
            trislope=int(self.v_slope.get()), wavescroll=int(self.v_wavefreq.get()),
            brightness=int(self.v_brt.get()),
            outpwm=int(self.v_outpwm.get()), outsin=int(self.v_outsin.get()),
            outuart=int(self.v_outuart.get()),
            genfreq=int(self.v_genfreq.get()), genduty=int(self.v_genduty.get()),
            wavetype=int(self.v_wavetype.get()), lang=int(self.v_lang.get()),
        )

    def _on_enum_change(self):
        """下拉框(字符串) -> IntVar, 然后下发参数"""
        try:
            self.v_genfreq.set(GEN_FREQ_TXT.index(self.v_genfreq_txt.get()))
        except Exception:
            self.v_genfreq.set(0)
        try:
            self.v_wavetype.set(WAVE_TYPE_TXT.index(self.v_wavetype_txt.get()))
        except Exception:
            self.v_wavetype.set(0)
        try:
            self.v_lang.set(LANG_TXT.index(self.v_lang_txt.get()))
        except Exception:
            self.v_lang.set(0)
        self._schedule_apply()

    def _schedule_apply(self):
        if self._updating:
            return
        if self._apply_job is not None:
            try:
                self.root.after_cancel(self._apply_job)
            except Exception:
                pass
        self._apply_job = self.root.after(120, self._send_set)

    def _send_set(self):
        self._apply_job = None
        if self.demo:
            return
        if not self.link:
            return
        self._send(build_frame(T_SET, settings_to_bytes(self._collect())))

    def _send(self, data):
        if self.demo:
            return True
        if not self.link:
            return False
        return self.link.send(data)

    def _read_all(self):
        self.pending_get = time.time()
        self._send(build_frame(T_GET))
        self._send(build_frame(T_INFO))

    def _save(self):
        self._msg("保存中...")
        self.pending_save = time.time()
        self._send(build_frame(T_SAVE))

    def _apply_settings_to_ui(self, s):
        self._updating = True
        try:
            self.v_lsb.set(s["lsb"])
            self.v_pmode.set(1 if s["plotmode"] else 0)
            self.v_scaleh.set(s["scaleh"] if 0 <= s["scaleh"] < len(SCALE_H_TXT) else 0)
            self.scaleh_var.set(float(self.v_scaleh.get()))
            self.scaleh_lbl.set(SCALE_H_TXT[self.v_scaleh.get()])
            self.v_auto.set(1 if s["scalev_auto"] else 0)
            self.v_vmax.set(s["rulervmax"])
            self.v_vmin.set(s["rulervmin"])
            self.v_tri.set(s["trilevel"])
            self.v_slope.set(1 if s["trislope"] else 0)
            self.v_trmode.set(TRI_MODE_TXT[s["trimode"]] if 0 <= s["trimode"] < 3 else "Auto")
            self.v_brt.set(s["brightness"])
            self.v_outpwm.set(1 if s["outpwm"] else 0)
            self.v_outsin.set(1 if s["outsin"] else 0)
            self.v_outuart.set(1 if s["outuart"] else 0)
            self.v_genfreq.set(s.get("genfreq", 0))
            self.v_genduty.set(s.get("genduty", 50))
            self.v_wavetype.set(s.get("wavetype", 0))
            self.v_wavefreq.set(max(0, min(5, int(s.get("wavescroll", 2)))))
            self.v_lang.set(s.get("lang", 0))
            try:
                self.v_genfreq_txt.set(GEN_FREQ_TXT[self.v_genfreq.get() % len(GEN_FREQ_TXT)])
                self.v_wavetype_txt.set(WAVE_TYPE_TXT[self.v_wavetype.get() % len(WAVE_TYPE_TXT)])
                self.v_wavefreq_txt.set(WAVE_FREQ_TXT[self.v_wavefreq.get() % len(WAVE_FREQ_TXT)])
                self.v_lang_txt.set(LANG_TXT[1 if self.v_lang.get() else 0])
            except Exception:
                pass
        except Exception:
            pass
        self._updating = False

    # ---------------- 暂停 / 保存 ----------------
    # ---------------- 波形滚动条(与 MCU 同步) ----------------
    def _on_scroll_slider(self, v):
        try:
            val = int(round(float(v)))
        except Exception:
            return
        if val < 0:
            val = 0
        self.scr_val.config(text=str(val))
        if getattr(self, "_scr_sync", False):
            return
        now = time.time()
        if now - getattr(self, "_scr_last_send", 0.0) < 0.10:
            return
        self._scr_last_send = now
        if self.link and not self.demo:
            self._send(build_frame(0x1B, bytes([val & 0xFF])))

    def _set_scroll_enabled(self, enabled):
        try:
            st = "normal" if enabled else "disabled"
            if str(self.scr_scale.cget("state")) != st:
                self.scr_scale.config(state=st)
        except Exception:
            pass

    # ---------------- 输出波偏移表(0x1D/0x1E) ----------------
    def _open_outcal(self):
        if getattr(self, "_outcal_win", None) is not None:
            try:
                self._outcal_win.lift()
                return
            except Exception:
                self._outcal_win = None
        win = tk.Toplevel(self.root)
        win.title(self._tr("输出波偏移表") + " (0.1us)")
        win.transient(self.root)
        self._outcal_win = win
        self._outcal_vars = []

        head = tk.Frame(win)
        head.pack(fill="x", padx=6, pady=4)
        tk.Label(head, text="#  方波 15 档 / 波形 6 档", anchor="w").pack(side="left")

        grid = tk.Frame(win)
        grid.pack(padx=6, pady=2)
        for i in range(21):
            name = ("SQ%d" % i) if i < 15 else ("WV%d" % (i - 15))
            tk.Label(grid, text="%2d %s" % (i, name), width=8, anchor="w").grid(row=i // 3, column=(i % 3) * 2, sticky="w")
            v = tk.IntVar(value=0)
            e = tk.Entry(grid, textvariable=v, width=7)
            e.grid(row=i // 3, column=(i % 3) * 2 + 1, padx=3, pady=1)
            self._outcal_vars.append(v)

        mrow = tk.Frame(win)
        mrow.pack(fill="x", padx=6, pady=(6, 0))
        tk.Label(mrow, text="延时模型:", anchor="w").pack(side="left")
        self._dtm_names = ["A1", "B1", "A2", "B2", "THR"]
        self._dtm_vars = []
        for nm in self._dtm_names:
            tk.Label(mrow, text=nm).pack(side="left", padx=(6, 1))
            v = tk.IntVar(value=0)
            tk.Entry(mrow, textvariable=v, width=7).pack(side="left")
            self._dtm_vars.append(v)
        mbar = tk.Frame(win)
        mbar.pack(fill="x", padx=6, pady=(2, 6))
        tk.Button(mbar, text=self._tr("读取模型"), command=self._dtm_read).pack(side="left", padx=3)
        tk.Button(mbar, text=self._tr("写入模型"), command=self._dtm_write).pack(side="left", padx=3)
        tk.Button(mbar, text=self._tr("基准校准(STM32)"),
                  command=lambda: self._run_tool("dtcal.py")).pack(side="left", padx=3)
        tk.Button(mbar, text=self._tr("烧后写回"),
                  command=lambda: self._run_tool("restore_all.py")).pack(side="left", padx=3)

        bar = tk.Frame(win)
        bar.pack(fill="x", padx=6, pady=6)
        tk.Button(bar, text=self._tr("读取"), command=self._outcal_read).pack(side="left", padx=3)
        tk.Button(bar, text=self._tr("写入 EEPROM"), command=self._outcal_write).pack(side="left", padx=3)
        b_sq = tk.Button(bar, text=self._tr("声卡校准(方波)"),
                         command=lambda: self._audio_calibrate("sq"))
        b_sq.pack(side="left", padx=3)
        _Tip(b_sq, (lambda: "接线：PWM 环 → 声卡 Line-in/Mic（100k+1k 分压到约 100mV，GND 共地）"
                    if self.lang == "cn" else
                    "Wiring: PWM loop -> sound-card in via 100k+1k divider, common GND"))
        b_wv = tk.Button(bar, text=self._tr("声卡校准(波形)"),
                         command=lambda: self._audio_calibrate("wv"))
        b_wv.pack(side="left", padx=3)
        _Tip(b_wv, (lambda: "接线：SIN 环 → 声卡 Line-in/Mic（100k+1k 分压到约 100mV，GND 共地）"
                    if self.lang == "cn" else
                    "Wiring: SIN loop -> sound-card in via 100k+1k divider, common GND"))
        b_close = tk.Button(bar, text=self._tr("关闭"), command=self._outcal_close)
        b_close.pack(side="right", padx=3)
        _Tip(b_close, (lambda: "关闭本窗口（不写设备）" if self.lang == "cn" else "Close this dialog (no write)"))

    def _outcal_close(self):
        try:
            self._outcal_win.destroy()
        except Exception:
            pass
        self._outcal_win = None

    def _dtm_read(self):
        if self.link and not self.demo:
            self._send(build_frame(int(T_DTM)))

    def _dtm_write(self):
        if not (self.link and not self.demo):
            return
        vals = [max(0, min(65535, int(v.get()))) for v in self._dtm_vars]
        pay = b"".join(struct.pack("<H", v) for v in vals)
        self._send(build_frame(int(T_DTMW), pay))
        self._msg("延时模型系数已写入 EEPROM")

    def _run_tool(self, name):
        """调用 py/ 下的工具脚本(异步, 输出到提示区)"""
        import subprocess
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
        if not os.path.exists(script):
            self._msg("找不到 " + name)
            return
        self._msg("正在运行 %s ..." % name)

        def worker():
            try:
                r = subprocess.run([sys.executable, script], capture_output=True,
                                   text=True, timeout=600)
                out = (r.stdout or "").strip().splitlines()
                tail = out[-1] if out else ("失败: " + (r.stderr or "")[:120])
                self._tmsg("%s 完成: %s" % (name, tail))
            except Exception as e:
                self._tmsg("%s 失败: %r" % (name, e))

        threading.Thread(target=worker, daemon=True).start()

    def _outcal_read(self):
        if self.link and not self.demo:
            self._send(build_frame(int(T_OUTO)))

    def _outcal_write(self):
        if not (self.link and not self.demo):
            return
        vals = [int(v.get()) for v in self._outcal_vars]
        pay = b"".join(struct.pack("<h", max(-32768, min(32767, x))) for x in vals)
        self._send(build_frame(int(T_OUTW), pay))
        self._msg("输出波偏移表已写入")

    # ---------------- 声卡频率校准(绝对基准) ----------------
    @staticmethod
    def _audio_measure(sec=1.2, fs=48000):
        """录音并估计基频: 上升沿过零 + 线性插值, 返回 Hz(测不到返回 0)"""
        import numpy as np
        import sounddevice as sd

        n = int(fs * sec)
        rec = sd.rec(n, samplerate=fs, channels=1, dtype="float32")
        sd.wait()
        x = np.asarray(rec, dtype=np.float64).reshape(-1)
        if x.size < fs // 4:
            return 0.0
        x = x - x.mean()
        peak = float(np.max(np.abs(x)))
        if peak < 1e-4:
            return 0.0
        x = x / peak
        hi, lo = 0.5, -0.5          # 迟滞阈值, 抑制噪声抖动
        armed = False
        cross = []
        for i in range(1, x.size):
            if not armed and x[i] < lo:
                armed = True
            elif armed and x[i] > hi:
                armed = False
                a, b = x[i - 1], x[i]      # 线性插值过零点
                if b != a:
                    cross.append(i - 1 + (-a) / (b - a))
        if len(cross) < 3:
            return 0.0
        span = cross[-1] - cross[0]
        if span <= 0:
            return 0.0
        return (len(cross) - 1) * fs / span

    def _tmsg(self, text):
        """子线程里安全地发提示(主线程 _tick 取)"""
        try:
            self.rx_queue.put(("msg", text))
        except Exception:
            pass

    def _audio_calibrate(self, group):
        """group: 'sq'(方波15档) / 'wv'(波形6档); 需 P1.1 或 SIN 已接声卡输入"""
        if not (self.link and not self.demo):
            self._tmsg(self._tr("请先连接设备"))
            return
        try:
            import sounddevice  # noqa: F401
            import numpy  # noqa: F401
        except Exception:
            self._tmsg("需要 sounddevice + numpy: pip install sounddevice numpy")
            return

        import threading
        settings0 = self._collect()   # 主线程取快照(子线程不能碰 Tk)

        def worker():
            try:
                base = self._read_out_off()
                if base is None:
                    self._tmsg(self._tr("读取偏移表失败"))
                    return
                nom = (SQ_NOM_US10 if group == "sq" else WV_NOM_US10)
                first = 0 if group == "sq" else 15
                cnt = len(nom)
                measured = 0
                cur = dict(settings0)
                for k in range(cnt):
                    st = dict(cur)
                    if group == "sq":
                        st["outpwm"] = 1
                        st["outsin"] = 0
                        st["genfreq"] = k
                    else:
                        st["outpwm"] = 0
                        st["outsin"] = 1
                        st["wavetype"] = 0
                        st["wavescroll"] = k
                    self._send(build_frame(T_SET, settings_to_bytes(st)))
                    time.sleep(0.35)
                    f_meas = self._audio_measure(0.8)
                    f_nom = SQ_FREQ_HZ[k] if group == "sq" else WV_FREQ_HZ[k]
                    if f_meas <= 0:
                        self._tmsg("%s #%d 没测到频率" % (group, k))
                        continue
                    if not (f_nom * 0.8 <= f_meas <= f_nom * 1.25):
                        self._tmsg("%s #%d 测量值 %.2fHz 偏离目标 %.2fHz 太多, 跳过"
                                  % (group, k, f_meas, f_nom))
                        continue
                    idx = first + k
                    cur_off = base[idx]
                    period_now = nom[k] + cur_off
                    need = int(round(period_now * (f_nom / f_meas)))
                    new_off = max(-3000, min(3000, need - nom[k]))
                    base[idx] = new_off
                    measured += 1
                    self._tmsg("校准 %s #%d: 实测 %.2fHz 目标 %.2fHz 偏移 %d"
                              % (group, k, f_meas, f_nom, new_off))
                if measured * 2 < cnt:
                    self._tmsg("只测到 %d/%d 档, 未写入(检查音频线/幅值)" % (measured, cnt))
                    return
                self._write_out_off(base)
                self._tmsg("声卡校准完成: %d/%d 档, 偏移表已写入 EEPROM" % (measured, cnt))
            except Exception as e:
                self._tmsg("声卡校准失败: %r" % (e,))

        threading.Thread(target=worker, daemon=True).start()

    # ---------------- 声卡当标准信号源, 校准时基(绝对) ----------------
    def _audio_out_cal(self, group):
        """声卡测频校准输出波(方波/波形), 等价于对话框里的两个按钮"""
        self._audio_calibrate(group)

    def _audio_tb_calibrate(self):
        if not (self.link and not self.demo):
            self._msg("请先连接设备")
            return
        try:
            import sounddevice  # noqa: F401
            import numpy  # noqa: F401
        except Exception:
            self._msg("需要 sounddevice + numpy: pip install sounddevice numpy")
            return
        port = self.port_var.get().strip()
        try:
            baud = int(self.baud_var.get() or 115200)
        except Exception:
            baud = 115200
        self._tmsg("声卡校时基: 开始(电脑耳机输出 -> 示波器 INPUT, 播放 1kHz)")
        threading.Thread(target=self._audio_tb_worker, args=(port, baud), daemon=True).start()

    def _audio_tb_worker(self, port, baud):
        import numpy as np
        import sounddevice as sd

        T_CAL_W, T_CAL_R = 0x16, 0x17
        f_true = 1000.0
        try:
            if self.link:
                self.link.close()
                self.link = None
            ser = serial.Serial(port, baud, timeout=0.05)
            parser = FrameParser()

            def read_frames(sec=0.5):
                out = []
                t0 = time.time()
                while time.time() - t0 < sec:
                    d = ser.read(512)
                    if d:
                        out += parser.feed(d)
                return out

            def req(typ, payload=b"", sec=0.8):
                ser.write(build_frame(typ, payload))
                time.sleep(0.05)
                return read_frames(sec)

            tbl = None
            for t, pl in req(T_CAL_R, sec=1.5):
                if t == T_CAL_R and len(pl) == 42:
                    tbl = [pl[i * 2] | (pl[i * 2 + 1] << 8) for i in range(21)]
            if tbl is None:
                self._tmsg("读不到时基表(0x17), 中止")
                ser.close()
                return

            cur = None
            for t, pl in req(0x12):
                if t == 0x03 and len(pl) >= SETTINGS_LEN:
                    cur = settings_from_bytes(pl)
            if cur is None:
                self._tmsg("读参数失败, 中止")
                ser.close()
                return
            cur["trimode"] = 0
            cur["scalev_auto"] = 1

            fs = 48000
            tone = (0.5 * np.sin(2 * np.pi * f_true * np.arange(int(fs * 1.5)) / fs)).astype("float32")

            ratios = []
            for idx in (15, 14):        # 500us/div, 1ms/div: 1kHz 分别约 4.4 / 8.8 个周期
                cur["scaleh"] = idx
                ser.write(build_frame(T_SET, settings_to_bytes(cur)))
                read_frames(1.2)
                sd.play(tone, fs)
                frames = read_frames(1.2)
                sd.stop()
                sd.wait()
                f_dso = 0.0
                for t, pl in frames:
                    if t == 0x01:
                        sp = parse_sample(pl)
                        if sp and sp.get("freq"):
                            f_dso = float(sp["freq"])
                self._tmsg("  时基档 %d: 设备测得 %.2fHz (真值 %.0fHz)" % (idx, f_dso, f_true))
                if f_dso > 0 and f_true * 0.5 < f_dso < f_true * 2.0:
                    ratios.append(f_dso / f_true)

            if not ratios:
                self._tmsg("没测到 1kHz 信号: 检查耳机线是否接到 INPUT / 音量, 未修改时基表")
                ser.close()
                return
            r = sum(ratios) / len(ratios)
            if abs(r - 1.0) > 0.05:
                self._tmsg("偏差 %.2f%% 过大, 中止(检查接线/音量)" % ((r - 1) * 100))
                ser.close()
                return
            new = [max(1, int(round(v * r))) for v in tbl]
            pay = b"".join(bytes([v & 0xFF, (v >> 8) & 0xFF]) for v in new)
            ok = 0
            for t, pl in req(T_CAL_W, pay, 2.0):
                if t == 0x02:
                    ok = pl[1] if len(pl) >= 2 else 0
            ser.write(build_frame(0x11))
            read_frames(1.5)

            # 复测
            cur["scaleh"] = 15
            ser.write(build_frame(T_SET, settings_to_bytes(cur)))
            read_frames(1.0)
            sd.play(tone, fs)
            frames = read_frames(1.2)
            sd.stop()
            sd.wait()
            f2 = 0.0
            for t, pl in frames:
                if t == 0x01:
                    sp = parse_sample(pl)
                    if sp and sp.get("freq"):
                        f2 = float(sp["freq"])
            self._tmsg("时基校准完成: 比例 %.4f, 写入 %s, 复测 %.2fHz(误差 %+.3f%%)"
                       % (r, "成功" if ok else "失败", f2, (f2 / f_true - 1) * 100 if f2 else 0))
            ser.close()
        except Exception as e:
            self._tmsg("声卡校时基失败: %r" % (e,))

    def _read_out_off(self):
        """同步读输出偏移表(阻塞等待 0x1D 回复)"""
        self._outcal_vals = None
        self._send(build_frame(int(T_OUTO)))
        t0 = time.time()
        while time.time() - t0 < 6.0:
            if getattr(self, "_outcal_vals", None) is not None:
                return list(self._outcal_vals)
            time.sleep(0.02)
        return None

    def _write_out_off(self, vals):
        pay = b"".join(struct.pack("<h", max(-32768, min(32767, int(v)))) for v in vals)
        self._send(build_frame(int(T_OUTW), pay))
        time.sleep(0.6)

    def _add_tips(self):
        """给主界面按钮挂悬停说明(中/英随界面语言)"""
        tips = [
            (self.btn_pause, ("暂停 / 继续：暂停时单片机和上位机同步停下，界面不冻结\n恢复后先保留旧波形，等这轮扫描完成再刷新",
                              "Pause / resume: pauses both the MCU and the plot input\nThe old trace is kept until the next sweep finishes")),
            (getattr(self, "btn_read", None), ("从设备读回全部参数（并显示固件版本）",
                                               "Read all settings from the device")),
            (getattr(self, "btn_save", None), ("把当前参数写入设备 EEPROM",
                                               "Save current settings to device EEPROM")),
            (getattr(self, "btn_wave", None), ("把当前波形导出为 CSV（时间 / 原始 ADC / 电压）",
                                               "Export current waveform to CSV")),
            (getattr(self, "btn_shot", None), ("把当前界面保存为 PNG 截图",
                                               "Save the current view as PNG")),
            (self.btn_view, ("切换 波形 / 频谱(FFT) 视图",
                             "Toggle waveform / FFT view")),
            (self.btn_cur, ("显示或清除两条测量光标（也可 Shift+左键放置、拖动、双击清除）",
                            "Show/clear the two cursors (or Shift+click to place, drag, double-click to clear)")),
            (self.btn_lang, ("切换上位机界面语言（中文 / English）",
                             "Switch the GUI language")),
            (self.btn_cal, ("时基自校：设备自己输出测试方波，逐档测量并回写 21 档时基表\n（自洽校准，约 1~2 分钟）",
                            "Time-base self calibration: the device generates its own reference square wave\nand rewrites the 21 ranges (self-consistent, ~1-2 min)")),
            (self.btn_outcal, ("打开输出波偏移表：21 个值 = 方波 15 档 + 波形 6 档\n可读取 / 写入 EEPROM，也可在这里启动声卡校准",
                               "Output frequency offset table: 21 values (15 square + 6 wave)\nRead/write EEPROM, or start audio calibration here")),
            (self.btn_tbcal, ("声卡校时基（绝对基准）\n"
                               "接线：3.5mm 音频线 电脑耳机口 → 示波器 INPUT\n"
                               "　红夹接 INPUT 的 Signal，黑夹接 GND\n"
                               "程序自动播放 1 kHz，按声卡晶振测出时基误差并缩放全部 21 档\n"
                               "校完后示波器频率读数就是绝对值，可用夹子线自测输出波",
                               "Audio time-base cal (absolute)\n"
                               "Wiring: 3.5mm cable, PC headphone out -> DSO INPUT\n"
                               "　red clip to Signal, black clip to GND\n"
                               "Plays 1 kHz automatically, scales all 21 ranges to the sound-card clock")),
            (self.btn_sqcal, ("声卡校方波输出\n"
                               "接线：PWM 环 → 声卡 Line-in/Mic，中间串分压\n"
                               "　100k + 1k（或 10k + 220Ω）降到约 100 mV，GND 必须共地\n"
                               "程序逐档测频并回写方波 15 档偏移",
                               "Audio cal of the square output\n"
                               "Wiring: PWM loop -> sound-card Line-in/Mic through a divider\n"
                               "　100k + 1k (or 10k + 220R) down to ~100 mV, GND common\n"
                               "Measures each of the 15 steps and writes the offsets")),
            (self.btn_wvcal, ("声卡校波形输出\n"
                               "接线：SIN 环 → 声卡 Line-in/Mic，中间串分压\n"
                               "　100k + 1k（或 10k + 220Ω）降到约 100 mV，GND 必须共地\n"
                               "程序逐档测频并回写波形 6 档偏移",
                               "Audio cal of the sine/tri/saw output\n"
                               "Wiring: SIN loop -> sound-card Line-in/Mic through a divider\n"
                               "　100k + 1k (or 10k + 220R) down to ~100 mV, GND common\n"
                               "Measures each of the 6 steps and writes the offsets")),
        ]
        for w, t in tips:
            if w is not None:
                _Tip(w, (lambda tt=t: tt[0] if self.lang == "cn" else tt[1]))

    def _toggle_pause(self):
        """暂停/继续: 让单片机一起停/走(0x1C), 上位机界面本身不冻结"""
        self.paused = not self.paused
        self.btn_pause.config(text=self._tr("继续" if self.paused else "暂停"))
        if self.link and not self.demo:
            self._send(build_frame(0x1C, bytes([0 if self.paused else 1])))
        self._set_scroll_enabled(self.paused)
        self._redraw(force=True)


    def _save_wave(self):
        sp = self.last
        if not sp or not self.samples:
            self._msg("还没有波形数据")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
                                            initialfile="minidso_wave.csv")
        if not path:
            return
        try:
            div = SCALE_H_SEC[sp["scaleh"]] if sp["scaleh"] < len(SCALE_H_SEC) else 0.1
            dt = div / 25.0
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["# Mini-DSO waveform"])
                w.writerow(["# scaleh=%s  div=%.6gs  dt=%.6gs  Vmax=%dmV Vmin=%dmV freq=%dHz"
                            % (SCALE_H_TXT[sp["scaleh"]], div, dt, sp["vmax"], sp["vmin"], sp["freq"])])
                w.writerow(["index", "time_s", "raw_adc", "voltage_mV"])
                for i, raw in enumerate(self.samples):
                    w.writerow([i, "%.9g" % (i * dt), raw, "%.3f" % raw_to_mv(sp, raw)])
            self._msg("波形已保存: %s" % os.path.basename(path))
        except Exception as exc:
            self._msg("保存失败: %s" % exc)

    def _save_shot(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG", "*.png"), ("All", "*.*")],
                                            initialfile="minidso_shot.png")
        if not path:
            return
        try:
            self.root.update()
            if HAVE_PIL:
                try:
                    sc = float(self.root.winfo_fpixels("1i")) / 96.0
                except Exception:
                    sc = 1.0
                x = int(round(self.canvas.winfo_rootx() * sc))
                y = int(round(self.canvas.winfo_rooty() * sc))
                w = max(1, int(round(self.canvas.winfo_width() * sc)))
                h = max(1, int(round(self.canvas.winfo_height() * sc)))
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
                img.save(path)
                self._msg("截图已保存: %s" % os.path.basename(path))
            else:
                ps = path + ".ps"
                self.canvas.postscript(file=ps)
                self._msg("未装 pillow，已保存为 %s" % os.path.basename(ps))
        except Exception as exc:
            self._msg("截图失败: %s" % exc)


    # ---------------- 语言 / 视图 ----------------
    def _toggle_lang(self):
        self.lang = "en" if self.lang == "cn" else "cn"
        self._translate_widgets(to_en=(self.lang == "en"))
        self.btn_lang.config(text=("中文" if self.lang == "en" else "English"))
        self._redraw(force=True)

    def _toggle_view(self):
        self.view_mode = 'fft' if self.view_mode == 'wave' else 'wave'
        self.btn_view.config(text=(("Wave" if self.lang == 'en' else "波形")
                                   if self.view_mode == 'fft' else
                                   ("FFT" if self.lang == 'en' else "频谱")))
        self._redraw(force=True)

    # ---------------- 测量统计 ----------------
    def _measure_stats(self, sp, mvs):
        s = {}
        if not mvs:
            return s
        s["vmax"] = max(mvs)
        s["vmin"] = min(mvs)
        s["vpp"] = s["vmax"] - s["vmin"]
        s["mean"] = sum(mvs) / len(mvs)
        s["rms"] = (sum(v * v for v in mvs) / len(mvs)) ** 0.5
        div = SCALE_H_SEC[sp["scaleh"]] if sp["scaleh"] < len(SCALE_H_SEC) else 0.1
        dt = div / 25.0
        per = measure_period(self.samples)
        if per:
            s["freq"] = 1.0 / (per * dt)
            s["period"] = per * dt
        else:
            s["freq"] = None
            s["period"] = None
        # 占空比: 高于中值的时间比例
        th = (s["vmax"] + s["vmin"]) / 2.0
        if s["vpp"] > 50:
            high = sum(1 for v in mvs if v > th)
            s["duty"] = 100.0 * high / len(mvs)
        else:
            s["duty"] = None
        # 上升时间: 10%->90%
        if s["vpp"] > 50:
            lo_th = s["vmin"] + 0.1 * s["vpp"]
            hi_th = s["vmin"] + 0.9 * s["vpp"]
            rise = None
            for i in range(1, len(mvs)):
                if mvs[i - 1] <= lo_th < mvs[i]:
                    j = i
                    while j < len(mvs) and mvs[j] < hi_th:
                        j += 1
                    if j < len(mvs):
                        rise = (j - i + 1) * dt
                    break
            s["rise"] = rise
        else:
            s["rise"] = None
        return s

    # ---------------- 光标 ----------------
    def _cursor_hit(self, x, x0, x1):
        if not self.samples:
            return None
        n = len(self.samples)
        vis = max(2, int(round(n / self.hzoom)))
        i0 = max(0, min(max(0, n - vis), int(round((n - vis) * self.hcenter))))
        for k in (0, 1):
            if self.cur[k] is None:
                continue
            cx = x0 + (x1 - x0) * (self.cur[k] - i0) / max(1, vis - 1)
            if abs(cx - x) <= 6:
                return k
        return None

    def _on_shift_click(self, ev):
        if not self.samples:
            return
        x0, _, x1, _ = self._draw_bounds()
        n = len(self.samples)
        vis = max(2, int(round(n / self.hzoom)))
        i0 = max(0, min(max(0, n - vis), int(round((n - vis) * self.hcenter))))
        idx = i0 + int(round((ev.x - x0) / max(1, (x1 - x0)) * (vis - 1)))
        idx = max(0, min(n - 1, idx))
        if self.cur[0] is None or (self.cur[0] is not None and self.cur[1] is not None):
            self.cur = [idx, None]
        else:
            self.cur[1] = idx
        self._redraw(force=True)

    def _toggle_cursors(self):
        """一键放置 / 清除两条光标(也可 Shift+左键单独放置)"""
        n = len(self.samples)
        if n < 8:
            return
        if self.cur[0] is None or self.cur[1] is None:
            self.cur = [n // 3, (2 * n) // 3]
        else:
            self.cur = [None, None]
        self._redraw(force=True)

    def _draw_cursors(self, c, x0, x1):
        if not self.samples:
            return
        n = len(self.samples)
        vis = max(2, int(round(n / self.hzoom)))
        i0 = max(0, min(max(0, n - vis), int(round((n - vis) * self.hcenter))))
        for k, col in ((0, "#ffd040"), (1, "#40d0ff")):
            if self.cur[k] is None:
                continue
            x = x0 + (x1 - x0) * (self.cur[k] - i0) / max(1, vis - 1)
            c.create_line(x, 10, x, c.winfo_height() - 30, fill=col, dash=(3, 2))
            c.create_text(x + 3, 20, text="C%d" % (k + 1), fill=col, anchor="w",
                          font=("Consolas", 8))

    # ---------------- 频谱 ----------------
    def _draw_fft(self, c, x0, y0, x1, y1):
        import math
        raw = self.samples
        N = 128
        buf = list(raw[:N]) + [0.0] * max(0, N - len(raw))
        buf = buf[:N]
        mean = sum(buf) / N
        # Hann 窗
        for i in range(N):
            buf[i] = (buf[i] - mean) * (0.5 - 0.5 * math.cos(2 * math.pi * i / N))
        # 迭代 FFT
        j = 0
        for i in range(1, N):
            bit = N >> 1
            while j & bit:
                j ^= bit
                bit >>= 1
            j |= bit
            if i < j:
                buf[i], buf[j] = buf[j], buf[i]
        re = buf
        im = [0.0] * N
        length = 2
        while length <= N:
            ang = -2 * math.pi / length
            wr, wi = math.cos(ang), math.sin(ang)
            for i in range(0, N, length):
                cur_r, cur_i = 1.0, 0.0
                half = length // 2
                for k in range(half):
                    ur, ui = re[i + k], im[i + k]
                    vr = re[i + k + half] * cur_r - im[i + k + half] * cur_i
                    vi = re[i + k + half] * cur_i + im[i + k + half] * cur_r
                    re[i + k], im[i + k] = ur + vr, ui + vi
                    re[i + k + half], im[i + k + half] = ur - vr, ui - vi
                    cur_r, cur_i = cur_r * wr - cur_i * wi, cur_r * wi + cur_i * wr
            length <<= 1
        mags = [math.hypot(re[i], im[i]) for i in range(N // 2)]
        if not mags:
            return
        top = max(mags[1:]) if len(mags) > 1 else 1.0
        top = max(top, 1e-9)
        sp = self.last or {}
        div = SCALE_H_SEC[sp.get("scaleh", 0)] if sp.get("scaleh", 0) < len(SCALE_H_SEC) else 0.1
        dt = div / 25.0
        fmax = 0.5 / dt
        for k in range(5):
            x = x0 + (x1 - x0) * k / 4
            c.create_line(x, y0, x, y1, fill="#203020")
            c.create_text(x, y1 + 8, text="%.3gHz" % (fmax * k / 4), fill="#9fb", anchor="n",
                          font=("Consolas", 8))
        for k in range(5):
            y = y0 + (y1 - y0) * k / 4
            c.create_line(x0, y, x1, y, fill="#203020")
            c.create_text(x1 + 6, y, text="%d%%" % (100 - 25 * k), fill="#9fb", anchor="w",
                          font=("Consolas", 8))
        pts = []
        for bi in range(1, len(mags)):
            x = x0 + (x1 - x0) * (bi - 1) / max(1, len(mags) - 2)
            y = y1 - (y1 - y0) * (mags[bi] / top) ** 0.5
            pts += [x, y]
        c.create_line(*pts, fill="#40ff60", width=1)
        c.create_text(x0 + 4, y0 + 8, text="FFT 128pts  base %.3g Hz" % (1.0 / (N * dt)),
                      fill="#e0e0e0", anchor="w")

    # ---------------- 一键校准 ----------------
    def _calibrate(self):
        if self.cal_busy:
            return
        if self.demo:
            self._msg("演示模式不能校准")
            return
        port = self.port_var.get().strip()
        if not port:
            self._msg("先选择串口")
            return
        self.cal_busy = True
        self.btn_cal.config(state="disabled")
        self._msg("校准中... (约 3~5 分钟)")
        try:
            baud = int(self.baud_var.get() or 115200)
        except Exception:
            baud = 115200
        threading.Thread(target=self._cal_worker, args=(port, baud), daemon=True).start()

    def _cal_worker(self, port, baud):
        """一键校准: 逐档输出测试方波 -> 测实际采样间隔 -> 回写校准表(21 档全覆盖)"""
        T_CAL_W, T_CAL_R, T_TEST = 0x16, 0x17, 0x15
        tbl = None
        try:
            if self.link:
                self.link.close()
                self.link = None
            ser = serial.Serial(port, baud, timeout=0.05)
            parser = FrameParser()

            def read_frames(sec=0.5):
                out = []
                t0 = time.time()
                while time.time() - t0 < sec:
                    d = ser.read(512)
                    if d:
                        out += parser.feed(d)
                return out

            def req(typ, payload=b"", sec=0.8):
                ser.write(build_frame(typ, payload))
                time.sleep(0.05)
                return read_frames(sec)

            # 读当前校准表
            for t, pl in req(T_CAL_R, sec=1.2):
                if t == T_CAL_R and len(pl) == 42:
                    tbl = [pl[i * 2] | (pl[i * 2 + 1] << 8) for i in range(21)]
            if tbl is None:
                raise RuntimeError("设备不支持校准命令(0x17)")
            cur = None
            for t, pl in req(0x12):
                if t == 0x03 and len(pl) >= SETTINGS_LEN:
                    cur = settings_from_bytes(pl)
            if cur is None:
                raise RuntimeError("读取参数失败")
            cur["trimode"] = 0          # 自动触发, 波形稳定
            cur["scalev_auto"] = 1
            cur["wavescroll"] = int(self.v_wavefreq.get())

            new = list(tbl)
            N = len(SCALE_H_TXT)        # 21
            for idx in range(N):
                dt_us = SCALE_H_SEC[idx] / 25.0 * 1e6      # 每采样点目标间隔(us)
                # 参考信号周期取 40 个采样点, 换算成测试方波分频
                target_period_us = 40.0 * dt_us
                f_want = 1e6 / target_period_us
                div = int(round(72115.0 / (2.0 * f_want)))
                div = max(1, min(30000, div))
                f_ref = 72115.0 / (2.0 * div)

                req(T_TEST, bytes([div & 0xFF, (div >> 8) & 0xFF]))
                cur["scaleh"] = idx
                ser.write(build_frame(T_SET, settings_to_bytes(cur)))
                # 等这档扫描 + 2 个参考周期
                settle = 220.0 * dt_us * 1e-6 * 1.4 + 0.5 + 2.0 / f_ref
                read_frames(min(40.0, settle))

                per = []
                t0 = time.time()
                while time.time() - t0 < 6.0 and len(per) < 5:
                    for tt, pp in read_frames(0.3):
                        if tt == T_SAMPLE:
                            sp = parse_sample(pp)
                            if sp:
                                x = measure_period(sp["raw"])
                                if x:
                                    per.append(x)
                if not per:
                    self.rx_queue.put(("cal_progress",
                                       "第 %d 档未测到周期，跳过" % (idx + 1)))
                    continue

                per = sorted(per)[len(per) // 2]
                meas = (1.0 / f_ref) / per * 1e6            # 实测每点间隔(us)
                # 增量换算: DelayUs(1us/单位) / DelayFine(约0.4us/单位)
                if idx >= 15 and idx != 19:
                    step_us = 0.4
                else:
                    step_us = 1.0
                delta = int(round((dt_us - meas) / step_us))
                new[idx] = max(0, min(65535, tbl[idx] + delta))
                self.rx_queue.put(("cal_progress",
                                   "校准 %d/%d: %s  实测 %.2fus 目标 %.2fus"
                                   % (idx + 1, N, SCALE_H_TXT[idx], meas, dt_us)))

            pl = b"".join(bytes([v & 0xFF, (v >> 8) & 0xFF]) for v in new)
            ack = req(T_CAL_W, pl, 2.0)
            ok = bool([1 for t, a in ack if t == T_ACK and len(a) >= 2 and a[1]])
            req(T_TEST, bytes([0, 0]))
            ser.close()
            self.rx_queue.put(("cal_done", (ok, new)))
        except Exception as exc:
            self.rx_queue.put(("cal_fail", str(exc)))

    # ---------------- 波特率扫描 ----------------
    # ---------------- 事件循环 ----------------
    def _tick(self):
        handled = 0
        while handled < 200:
            try:
                kind, data = self.rx_queue.get_nowait()
            except queue.Empty:
                break
            handled += 1
            if kind == "msg":
                self._msg(data)
            elif kind == "frame":
                self._on_frame(*data)
            elif kind == "error":
                self._status("串口错误: %s" % data)
                if self.link:
                    self.link.close()
                    self.link = None
                self._btnconnect("连接")
            elif kind == "cal_progress":
                self._msg(str(data))
            elif kind == "cal_done":
                ok, tbl = data
                self.cal_busy = False
                self.btn_cal.config(state="normal")
                self._msg("校准完成并已写入 EEPROM" if ok else "校准写入失败")
                self._hint("校准表: " + ",".join(str(v) for v in tbl))
                self.root.after(500, self._toggle_connect)  # 自动重连
            elif kind == "cal_fail":
                self.cal_busy = False
                self.btn_cal.config(state="normal")
                self._msg("校准失败: " + str(data))
            elif kind == "autodetect":
                self._on_autodetect(data)


        now = time.time()
        if self.pending_save and now - self.pending_save > 1.5:
            self.pending_save = 0.0
            self._msg("Save failed! (超时无应答)")
        if self.pending_get and now - self.pending_get > 1.5:
            self.pending_get = 0.0
            if self.link:
                if self.link.rx_bytes == 0:
                    self._hint("未收到任何数据：确认固件已烧录、TXD/RXD 交叉、共地、Output UART=ON")
                else:
                    self._hint("收到 %d 字节但没有有效帧：检查波特率/接线/TXD-RXD"
                                          % self.link.rx_bytes)

        now = time.time()
        # 只有在"已暂停"时才查滚动位置: 连续轮询会挤占采样帧(慢时基会看起来卡住)
        if self.paused and (now - getattr(self, "_scr_last_poll", 0.0) > 0.35):
            self._scr_last_poll = now
            self._poll_scroll()

        self._redraw()
        self._update_status()
        self.root.after(30, self._tick)

    def _poll_scroll(self):
        if self.link and not self.demo:
            self._send(build_frame(0x1A))

    def _update_status(self):
        if self.demo or not self.link:
            return
        rx = self.link.rx_bytes
        nf = self.link.rx_frames
        txt = "已连接 %s @%s   RX=%d B  帧=%d" % (self.link.port, self.baud_var.get(), rx, nf)
        if getattr(self, "fw_ver", ""):
            txt += "   固件 " + self.fw_ver
        if self.paused:
            txt += "   [已暂停]"
        self._status(txt)

    def _on_frame(self, type_, payload):
        if type_ == T_SAMPLE:
            sp = parse_sample(payload)
            if sp:
                self.samples = sp["raw"]
                self.last = sp
        elif type_ == T_ACK:
            if len(payload) >= 2 and self.pending_save:
                self.pending_save = 0.0
                self._msg("Save succeed" if payload[1] else "Save failed!")
                self._hint("")
        elif type_ == int(T_DTM):
            if len(payload) >= 10 and getattr(self, "_dtm_vars", None):
                v = struct.unpack("<5H", payload[:10])
                for k in range(5):
                    self._dtm_vars[k].set(int(v[k]))
        elif type_ == int(T_OUTO):
            if len(payload) >= 42:
                self._outcal_vals = list(struct.unpack("<21h", payload[:42]))
            if len(payload) >= 42 and getattr(self, "_outcal_vars", None):
                vals = struct.unpack("<21h", payload[:42])
                for k, v in enumerate(vals):
                    self._outcal_vars[k].set(int(v))
        elif type_ == 0x1A:
            if len(payload) >= 4:
                off = payload[0] - 256 if payload[0] > 127 else payload[0]
                mx = payload[3] if payload[3] > 0 else 120
                try:
                    self.scr_scale.config(to=mx)
                except Exception:
                    pass
                if off < 0:
                    off = 0
                if off > mx:
                    off = mx
                self._scr_sync = True
                try:
                    if not getattr(self, "_scr_drag", False):
                        self.scr_var.set(off)
                        self.scr_val.config(text=str(off))
                finally:
                    self._scr_sync = False
                self._set_scroll_enabled(payload[2] == 0)   # 暂停(running=0)才可拖
        elif type_ == T_INFO:
            if len(payload) >= 3:
                self.fw_ver = "v%d.%d.%d" % (payload[0], payload[1], payload[2])
        elif type_ == T_SETTINGS:
            if len(payload) >= SETTINGS_LEN:
                self._apply_settings_to_ui(settings_from_bytes(payload))
                self.pending_get = 0.0
                self._hint("")

    # ---------------- 绘图 ----------------
    # ---------------- 缩放/平移 ----------------
    def _on_wheel(self, ev):
        steps = 1 if ev.delta > 0 else -1
        factor = 1.25 ** steps
        w = max(1, self.canvas.winfo_width())
        x0, _, x1, _ = self._draw_bounds()
        if ev.state & 0x0004:          # Ctrl+滚轮 -> 纵向缩放
            self.autofit.set(0)
            z = float(self.zoom.get()) * factor
            self.zoom.set(max(0.5, min(10.0, z)))
        else:                           # 滚轮 -> 横向缩放(以光标为中心)
            rel = (ev.x - x0) / float(max(1, x1 - x0))
            rel = max(0.0, min(1.0, rel))
            old_zoom = self.hzoom
            new_zoom = max(1.0, min(50.0, self.hzoom * factor))
            if abs(new_zoom - old_zoom) > 1e-9:
                vis_old = 1.0 / old_zoom
                vis_new = 1.0 / new_zoom
                center = self.hcenter
                left = center - vis_old / 2.0
                anchor = left + rel * vis_old          # 光标下的相对位置
                new_left = anchor - rel * vis_new
                self.hcenter = max(0.0, min(1.0, new_left + vis_new / 2.0))
                self.hzoom = new_zoom
        self._redraw(force=True)

    def _on_drag_start(self, ev):
        x0, _, x1, _ = self._draw_bounds()
        k = self._cursor_hit(ev.x, x0, x1)
        if k is not None:
            self._cur_drag = k
            return
        self._drag_x = ev.x

    def _on_drag(self, ev):
        if self._cur_drag is not None and self.samples:
            x0, _, x1, _ = self._draw_bounds()
            n = len(self.samples)
            vis = max(2, int(round(n / self.hzoom)))
            i0 = max(0, min(max(0, n - vis), int(round((n - vis) * self.hcenter))))
            idx = i0 + int(round((ev.x - x0) / max(1, (x1 - x0)) * (vis - 1)))
            self.cur[self._cur_drag] = max(0, min(n - 1, idx))
            self._redraw(force=True)
            return
        if self._drag_x is None or self.hzoom <= 1.0:
            return
        x0, _, x1, _ = self._draw_bounds()
        dx = (ev.x - self._drag_x) / float(max(1, x1 - x0))
        self._drag_x = ev.x
        self.hcenter = max(0.0, min(1.0, self.hcenter - dx / self.hzoom))
        self._redraw(force=True)

    def _on_double(self, ev):
        self.hzoom = 1.0
        self.hcenter = 0.5
        self.autofit.set(1)
        self._redraw(force=True)
    def _draw_bounds(self):
        w = max(240, self.canvas.winfo_width())
        h = max(140, self.canvas.winfo_height())
        return 52, 10, w - 62, h - 30     # x0, y0, x1, y1 (右侧留出坐标标注)

    def _redraw(self, force=False):
        c = self.canvas
        w = c.winfo_width()
        h = c.winfo_height()
        sp = self.last
        key = (w, h, len(self.samples), tuple(self.samples[::10]), self.hzoom, round(self.hcenter,4),
               self.zoom.get(), self.autofit.get(), sp.get("rvmin"), sp.get("rvmax"),
               sp.get("pamin"), sp.get("pamax"))
        if not force and key == self.last_canvas:
            return
        self.last_canvas = key

        c.delete("all")
        x0, y0, x1, y1 = self._draw_bounds()

        if not sp or not self.samples:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="等待数据...", fill="#808080")
            return
        if self.view_mode == 'fft':
            self._draw_fft(c, x0, y0, x1, y1)
            return

        # 纵轴: 电压换算与固件一致；自动适配时按波形实际范围确定显示区间
        rvmin, rvmax = sp["rvmin"], sp["rvmax"]
        if rvmax <= rvmin:
            rvmax = rvmin + 1000
        rvspan = float(rvmax - rvmin)

        mvs = [raw_to_mv(sp, v) for v in self.samples]
        mvmin, mvmax = min(mvs), max(mvs)

        if self.autofit.get():
            data_span = mvmax - mvmin
            if data_span < 100:
                data_span = 100
            vspan = data_span * 1.2
            center = (mvmin + mvmax) / 2.0
            zoom = rvspan / vspan
        else:
            zoom = max(0.5, float(self.zoom.get()))
            vspan = rvspan / zoom
            center = (rvmin + rvmax) / 2.0
        lo = center - vspan / 2.0
        hi = center + vspan / 2.0
        self._zoom("显示 %s ~ %s   (%.2fx)" % (fmt_mv(lo), fmt_mv(hi), zoom))

        def y_of_mv(mv):
            return y1 - (mv - lo) / (hi - lo) * (y1 - y0)

        # 网格 + 右侧纵轴标注
        for k in range(5):
            y = y0 + (y1 - y0) * k / 4
            mv = hi - (hi - lo) * k / 4
            c.create_line(x0, y, x1, y, fill="#203020")
            c.create_text(x1 + 6, y, text=fmt_mv(mv), fill="#9fb", anchor="w",
                          font=("Consolas", 8))
        for k in range(5):
            x = x0 + (x1 - x0) * k / 4
            c.create_line(x, y0, x, y1, fill="#203020")
            c.create_line(x, y1, x, y1 - 4, fill="#607060")

        # 可视窗口(横向缩放)
        n = len(mvs)
        vis = max(2, int(round(n / self.hzoom)))
        i0 = int(round((n - vis) * self.hcenter))
        i0 = max(0, min(max(0, n - vis), i0))

        # 横轴时间标注 (每格 = 时基; 共 4 格)
        div = SCALE_H_SEC[sp["scaleh"]] if sp["scaleh"] < len(SCALE_H_SEC) else 0.1
        dt = div / 25.0
        for k in range(5):
            x = x0 + (x1 - x0) * k / 4
            t = (i0 + (vis - 1) * k / 4.0) * dt
            c.create_text(x, y1 + 8, text=fmt_time(t), fill="#9fb", anchor="n",
                          font=("Consolas", 8))
        if self.hzoom > 1.01:
            c.create_text(x1 - 4, y1 + 20, text="横向 x%.1f (滚轮缩放/双击复位)" % self.hzoom,
                          fill="#7a9", anchor="e", font=("Consolas", 8))

        # 波形 (按当前横向可视窗口绘制)
        i1 = i0 + vis
        pts = []
        for i in range(i0, i1):
            pts.append(x0 + (x1 - x0) * (i - i0) / max(1, vis - 1))
            pts.append(y_of_mv(mvs[i]))

        if sp["plotmode"]:
            c.create_line(*pts, fill="#40ff60", width=1)
        else:
            for i in range(0, len(pts), 2):
                c.create_rectangle(pts[i], pts[i + 1], pts[i] + 2, pts[i + 1] + 2,
                                   outline="#40ff60", fill="#40ff60")

        # 状态/读数
        status = ["Run" if sp["running"] else "Stop"]
        if sp["trifail"]:
            status.append("Fail")
        if sp["auto"]:
            status.append("Auto")
        status.append(SCALE_H_TXT[sp["scaleh"]] if sp["scaleh"] < len(SCALE_H_TXT) else "?")
        status.append(TRI_MODE_TXT[sp["trimode"]] if sp["trimode"] < 3 else "?")
        status.append("Rise" if sp["trislope"] else "Fall")
        c.create_text(x0 + 4, y0 + 8, text="  ".join(status), fill="#e0e0e0", anchor="w")
        c.create_text(x1 - 4, y0 + 8, text="%.0f Hz" % sp["freq"], fill="#e0e0e0", anchor="e")
        if self.paused:
            c.create_text((x0 + x1) / 2, y0 + 20, text="已暂停", fill="#ffcc00")

        rawmin, rawmax = min(self.samples), max(self.samples)
        # ---- 时基自检: 用固件自己 9.014kHz 方波作参考测采样周期 ----
        div = SCALE_H_SEC[sp["scaleh"]] if sp["scaleh"] < len(SCALE_H_SEC) else 0.1
        nom_samples = (1.0 / PWM_FREQ_NOMINAL) / (div / 25.0)
        per = measure_period(self.samples)
        if per:
            ratio = nom_samples / float(per)      # >1 说明采样间隔偏长(时基偏慢)
            tb = "周期=%d 样本  名义=%.1f  时基偏差 %+.1f%%" % (per, nom_samples, (ratio - 1) * 100.0)
        else:
            tb = "周期样本不足/波形不稳，换快一点的时基再测"
        self._info("采样点: %d  频率: %.1f Hz\nADC %d..%d -> %s..%s\nBGV=%dmV ADCbg=%d LSB=%d\n%s"
                              % (n, sp["freq"], rawmin, rawmax,
                                 fmt_mv(min(mvs)), fmt_mv(max(mvs)),
                                 sp.get("bgv", 0), sp.get("adcbg", 0), sp.get("lsb", 0), tb))

        if self.cur[0] is None or self.cur[1] is None:
            self.hexlabel.config(text=self._tr("光标: Shift+左键放置 / 拖动移动 / 双击清除（或点「光标」）"))
        else:
            self.hexlabel.config(text="")
        self._draw_cursors(c, x0, x1)
        st = self._measure_stats(sp, mvs)
        self.stat = st
        cur_txt = ""
        if self.cur[0] is not None and self.cur[1] is not None:
            dt = (SCALE_H_SEC[sp["scaleh"]] / 25.0) if sp["scaleh"] < len(SCALE_H_SEC) else 0.004
            dti = abs(self.cur[1] - self.cur[0]) * dt
            dv = abs(mvs[self.cur[1]] - mvs[self.cur[0]])
            cur_txt = "\nC1-C2: Δt=%s  ΔV=%s" % (fmt_time(dti), fmt_mv(dv))
        self._stat("Vpp=%s  Vmax=%s  Vmin=%s\nVrms=%s  Vavg=%s\nF=%s  Duty=%s  Tr=%s%s"
                             % (fmt_mv(st.get('vpp', 0)), fmt_mv(st.get('vmax', 0)), fmt_mv(st.get('vmin', 0)),
                                fmt_mv(st.get('rms', 0)), fmt_mv(st.get('mean', 0)),
                                ("%.1fHz" % st['freq']) if st.get('freq') else "--",
                                ("%.0f%%" % st['duty']) if st.get('duty') is not None else "--",
                                fmt_time(st['rise']) if st.get('rise') else "--", cur_txt))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mini-DSO 上位机")
    ap.add_argument("--demo", action="store_true", help="无硬件演示模式")
    ap.add_argument("--selftest", action="store_true", help="协议自检")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()

    if not HAVE_TK:
        print("未找到 tkinter，无法启动界面；可用 --selftest 做协议自检")
        return 1

    root = tk.Tk()
    app = App(root, demo=args.demo)
    root.mainloop()
    if app.link:
        app.link.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
