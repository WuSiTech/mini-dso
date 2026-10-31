# Mini-DSO v1.4 — STC8A8K64D4 @ 45 MHz

**中文** | [English](#english-version)

---

## 中文版

### 简介

把 [CreativeLau/Mini-DSO](https://github.com/CreativeLau/Mini-DSO) v0.3 移植到
**56DZ 版 STC8A8K64D4 核心板**（45 MHz 内部 IRC、SSD1306 128×64 SPI OLED、EC11 旋钮），
并在此基础上做了进一步开发。

### 特色

- **中英双语界面**：设置页/信息页/启动页一键切换中文 ⇄ English，语言存 EEPROM
- **可以使用电脑作为上位机**：`py/dso_gui.py` 提供实时波形、FFT、自动测量、双光标、
  时基一键校准、参数读写、EEPROM 保存、波形 CSV / 截图 PNG 导出；
  无硬件时可用 `--demo` 演示。**软件就在仓库的 `py/` 目录**
- **21 档时基** 500 ms/div … 80 µs/div，逐档实测校准（EEPROM 可软件再校准）
- **双光标测量**：设备端独立光标页，直接读出 `dT` / `dV`（画在最底行）
- **可调信号源**：P1.1 方波 15 档频率（≈1 Hz~42 kHz）+ 占空比 1~99 %；
  P1.0 可输出正弦 / 三角 / 锯齿（经外部 RC）
- **中文点阵字库**：12×12 像素风，由 `py/gen_cnfont.py` 自动生成
- **串口协议完整**：采样流 + 参数读写 + EEPROM 保存 + 时基校准表 + 固件版本查询
- 开机启动页 + 自检（EEPROM / 校准表 / 电池电压），烧录可软复位进 ISP

### 来源与致谢

- 原作：**CreativeLau** — https://github.com/CreativeLau/Mini-DSO
- 适配到 56DZ 版：https://www.elektormagazine.de/labs/reverse-project-mini-oscilloscope
- 进一步开发：**WuSi & DeepSeek** — https://github.com/WuSiTech/mini-dso

### 硬件

| 项目 | 说明 |
|---|---|
| MCU | STC8A8K64D4，内部 IRC **45 MHz**（1T） |
| 显示 | SSD1306 128×64 OLED，**SPI** 接法（GND VCC D0 D1 RES DC CS） |
| 输入 | ADC CH0 = **P0.1**，ADC CH1 = **P1.4** |
| 方波输出 | **P1.1**（推挽，频率 / 占空比可调） |
| 波形输出 | **P1.0**（PCA 8-bit PWM + 外部 RC 低通） |
| 旋钮 | EC11 编码器（Timer0 250 µs 正交采样） |
| 串口 | P3.0 RXD / P3.1 TXD，**115200 8N1** |
| 指示灯 | P2.6 |
| 存储 | 内部 EEPROM 512 B（设置 + 校准表） |

### 快速上手

1. 烧录 `build/minidso_uart.hex`（见下方"烧录"）
2. 上电 → 启动页显示 LOGO 和自检结果 → 自动进主界面
3. 把待测信号接到输入分压端（P0.1 通道）
4. 旋转旋钮调时基/量程，按住旋钮再旋转可切换要调的项目
5. 短按：暂停/继续；长按 0.5 秒：进设置

### 操作说明 — 设备

#### 主界面

屏幕布局：顶部状态行（`Run/Stop`、时基、触发电平、触发方式、频率），
中间波形区（26~126 列），底部显示电压范围/时基。

| 操作 | 作用 |
|---|---|
| **旋转** | 调整当前选中项的值（时基 / 量程 / 触发电平 / 触发沿 / 触发方式） |
| **按住 + 旋转** | 切换要调的项目（不会进入设置） |
| **短按** | **Run ⇄ Stop** 立即切换，画面冻结在按下瞬间 |
| **长按 ≥0.5 s** | 进入设置页 |

#### 设置页（13 项）

旋转 = 改当前项的值；**按住 + 旋转** = 在项目间移动；**长按** = 保存并退出。

```
绘图模式      亮度        分压系数
方波输出      方波频率    占空比
波形输出      波形类型    串口输出
语言          光标测量 >
创作者信息 >  电池电压
```

- **旋钮加速**：仅 4 个纯数值项（亮度 / 分压系数 / 方波频率 / 占空比）加速
  （慢转 1 步、≤120 ms 2 步、≤50 ms 3 步）；其他项一律 1 格 1 步
- **语言**：切换后立即生效并存 EEPROM
- **方波频率**：15 档，`1Hz/2/5/10/20/50/100/200/500/1k/2k/5k/10k/17k/42k Hz`
- **波形类型**：正弦 / 三角 / 锯齿（P1.0 输出，需外接 RC 才好看）

#### 光标测量页

进入：设置页滚到「光标测量」，**再旋转一格**进入。

| 操作 | 作用 |
|---|---|
| 旋转 | 左右移动当前光标（限制在图表 100 列内） |
| 按住 + 旋转 | 切换选中 A / B（选中的是实线，另一个虚线） |
| 短按 / 长按 | 返回设置页 |

屏幕**最底一行**显示 `dT:xxx us/ms  dV:x.xx V`（取代原来的电压范围/时基信息）。

#### 创作者信息页

进入：设置页滚到「创作者信息」，再旋转一格进入。
页面显示 LOGO、原作、开发、项目地址；`按住 + 旋转` 选择条目，
`旋转` 显示对应网址（长网址自动轮播），选到 `<Back` 旋转即返回；长按直接退回。

#### 信号源

1. 设置页打开 `方波输出`（P1.1）和/或 `波形输出`（P1.0）
2. 调 `方波频率`、`占空比`、`波形类型`
3. 关闭时引脚被拉到 0 V

### 操作说明 — 上位机（PC）

> 光标：Shift+左键放置 / 拖动移动 / 双击清除，也可以点界面上的「光标」按钮一键放两条。

`py/dso_gui.py` 需要 Python 3 + `pyserial`（画 PNG 需要 `pillow`）：

```bat
pip install pyserial pillow
python py\dso_gui.py            :: 连真机
python py\dso_gui.py --demo     :: 无硬件演示
python py\dso_gui.py --selftest :: 协议自检
```

**步骤**：

1. 设备设置里确认 `串口输出 = ON`（默认开），USB 串口接电脑
2. 打开软件 → 选端口 → 点「连接」（选不到端口就点「刷新」）
3. 波形自动刷新；右侧参数面板改任何值**即时生效**（不等按钮）
4. 点「保存到 EEPROM」把当前参数写进设备
5. 点「读取」可随时把设备参数读回来
6. 「一键校准」会驱动设备输出测试方波、自动测量 21 档时基并写回校准表

**界面功能**：

| 区域 / 按钮 | 说明 |
|---|---|
| 波形区 | 实时波形（矢量/点阵）；滚轮缩放、Ctrl+滚轮纵向、拖动平移 |
| 测量 | Vpp / Vmax / Vmin / Vrms / Vavg / 频率 / 周期 / 占空比 / 上升时间 |
| 光标 | Shift+左键放置、拖动、双击复位，显示 Δt / ΔV |
| 参数面板 | 绘图模式、亮度(BRT)、LSB、时基、量程、触发电平/沿/方式、输出开关、方波频率、占空比、波形类型、设备语言 |
| 频谱 | 切到 FFT 视图（128 点 Hann 窗） |
| 暂停 | 停止刷新画面（串口继续收） |
| 保存波形 (CSV) | 时间 / 原始 ADC / 电压(mV) |
| 保存截图 (PNG) | 当前画面 |
| 语言 | 上位机界面中英切换 |
| 一键校准 | 自动校 21 档时基 |

### 编译

需要 **SDCC 4.6.0**（`sdcc`/`sdar`/`sdranlib` 在 PATH）。

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

> ⚠️ **必须带 `--stack-auto`**：8051 直接寻址 RAM 只有 128 B，不加会报
> `Could not get ... consecutive bytes in internal RAM for area DSEG`。

资源占用（v1.2.0）：ROM 36,738 / 64,512 (57%)、XRAM 3,551 / 8,192、栈 218 B。

中文字库改了之后重新生成：`python py\gen_cnfont.py`（不要手改 `include/cnfont.h`）。

### 烧录

- **STC-ISP**：芯片 STC8A8K64D4，IRC 45 MHz，打开 `build/minidso_uart.hex`，
  点下载后**断电再上电**
- **命令行**：`python -m stcgal -P stc8d -p COM5 build/minidso_uart.hex`（需冷启动）
- **运行中自动烧录**：`python py\flash.py COM5 build\minidso_uart.hex`
  （固件收到 `0x14` 后软复位进 ISP）

> 烧录会整片擦除 EEPROM：设置和校准表回到默认值。

### 串口协议

```
A5 5A TYPE LENH LENL PAYLOAD[LEN] SUM
SUM = (TYPE + LENH + LENL + ΣPAYLOAD) & 0xFF
```

| TYPE | 方向 | 含义 |
|---|---|---|
| 0x01 | DSO→PC | 采样帧（28 B 头 + N×uint16） |
| 0x02 | DSO→PC | 应答 |
| 0x03 | DSO→PC | 参数块（22 B） |
| 0x10 | PC→DSO | 下发参数（立即生效） |
| 0x11 | PC→DSO | 保存到 EEPROM |
| 0x12 | PC→DSO | 读取参数 |
| 0x14 | PC→DSO | 软复位进 ISP |
| 0x15 | PC→DSO | 输出测试方波 |
| 0x16 / 0x17 | PC→DSO | 写 / 读时基校准表（21×uint16） |
| 0x19 | DSO→PC | 固件信息（版本/长度/能力/tick） |

参数块（22 B）：`Lsb(u16) PlotMode ScaleH ScaleV_Auto RulerVMax(u16) RulerVMin(u16)
TriLevel(u16) TriMode TriSlope WaveScroll Brightness OutPWM OutSIN OutUART
GenFreqIdx GenDuty WaveType Lang`

### 目录结构

```
mini-dso/
├─ src/            固件源码
├─ include/        头文件（cnfont.h 中文字模、bmp.h LOGO、keys.h …）
├─ user/main.c     主程序 + 中断 + 主循环
├─ build/          minidso.hex（原版）/ minidso_uart.hex（当前 v1.2.0）
├─ py/             上位机与工具（dso_gui.py / flash.py / test_tb.py / gen_cnfont.py）
├─ build.ps1       一键编译
└─ README.md
```

### 已知事项

- 时基表按实测校准，绝对时间与外部基准可能有几个百分点偏差
- 方波频率由 `GEN_TICK_US10 = 120`（12.0 µs/tick）推算，标称值近似
- BGV 实测 1185 mV（代码回退 1200 mV）
- IRAM 已满，新增全局变量请放 `__xdata`
- 所有 C 源文件是 **GBK** 编码
- 双击功能已移除（和"短按 Run/Stop"冲突）
- 不启用看门狗：长时基采样一轮 4.4 s，软件无法与卡死区分，会误复位

### 许可

原始项目 MIT（见 `src/` 文件头）；本移植与增强同样以 MIT 发布。

---

## English version

### What it is

Port of [CreativeLau/Mini-DSO](https://github.com/CreativeLau/Mini-DSO) v0.3 to the
**56DZ STC8A8K64D4 board** (45 MHz internal IRC, SSD1306 128×64 SPI OLED, EC11 encoder),
plus further development.

### Features

- **Bilingual UI** (Chinese ⇄ English), language stored in EEPROM
- **PC host software included**: `py/dso_gui.py` gives live waveform, FFT, automatic
  measurements, dual cursors, one-click time-base calibration, parameter read/write,
  EEPROM save, CSV/PNG export, `--demo` mode without hardware
- **21 time-base ranges** (500 ms/div … 80 µs/div), individually calibrated
- **On-device dual-cursor page** showing `dT` / `dV` on the bottom line
- **Signal generator**: P1.1 square wave, 15 frequencies (≈1 Hz–42 kHz), duty 1–99 %;
  P1.0 sine / triangle / sawtooth (needs RC filter)
- 12×12 pixel Chinese font, generated by `py/gen_cnfont.py`
- Full UART protocol: sample stream, settings R/W, EEPROM save, calibration table, version query

### Credits

- Original: **CreativeLau** — https://github.com/CreativeLau/Mini-DSO
- 56DZ adaptation: https://www.elektormagazine.de/labs/reverse-project-mini-oscilloscope
- Further development: **WuSi & DeepSeek** — https://github.com/WuSiTech/mini-dso

### Controls (device)

| Action | Function |
|---|---|
| Rotate | Adjust the currently selected item (time base / range / trigger level / slope / trigger mode) |
| Press + rotate | Select which item to adjust (does not enter settings) |
| Short press | Run ⇄ Stop immediately |
| Long press (≥0.5 s) | Enter / exit settings |

Settings page: rotate = change value, **press+rotate = move between items**,
long press = save and exit. 13 items:
`Plot mode, Brightness, LSB, PWM out, PWM freq, Duty, Wave out, Wave type, UART out,
Language, Cursor >, Dev-er Info >, Batt voltage`.
Encoder acceleration applies only to the four numeric items (brightness, LSB,
PWM frequency, duty): 1 step slow, 2 steps ≤120 ms, 3 steps ≤50 ms.

Cursor page: enter from settings (select “Cursor”, rotate once more).
Rotate = move cursor, press+rotate = switch A/B, short/long press = back.
`dT` / `dV` are shown in the bottom line.

Creator info page: select “Dev-er Info” then rotate to open; press+rotate selects
Original / Developer / Project URL / `<Back`; rotate shows the corresponding URL
(marquee for long URLs); long press returns.

### Controls (PC host, `py/dso_gui.py`)

```bat
pip install pyserial pillow
python py\dso_gui.py            :: real device
python py\dso_gui.py --demo     :: demo without hardware
python py\dso_gui.py --selftest :: protocol self-test
```

1. Set `UART out = ON` on the device and connect its USB serial port
2. Choose the port and press “Connect”
3. Parameter changes on the right panel are applied immediately
4. “Save to EEPROM” writes them to the device; “Read” fetches them back
5. “One-click calibrate” measures all 21 time bases and writes the calibration table

Waveform view: mouse wheel = zoom, Ctrl+wheel = vertical, drag = pan.
Measurements: Vpp/Vmax/Vmin/Vrms/Vavg/frequency/period/duty/rise time.
Cursors: Shift+click to place, drag to move, double-click to reset (Δt/ΔV).
Also: FFT view, pause, CSV/PNG export, UI language switch.

### Build

SDCC 4.6.0 required:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

`--stack-auto` is mandatory (only 128 B of directly addressable IRAM).
Current usage: ROM 36,738 / 64,512 B, XRAM 3,551 / 8,192 B, stack 218 B.

### Flash

- STC-ISP: chip STC8A8K64D4, IRC 45 MHz, `build/minidso_uart.hex`, power-cycle to download
- `python -m stcgal -P stc8d -p COM5 build/minidso_uart.hex`
- `python py\flash.py COM5 build\minidso_uart.hex` (firmware jumps to ISP by itself)

Flashing erases the whole EEPROM (settings and calibration table).

### Protocol

```
A5 5A TYPE LENH LENL PAYLOAD[LEN] SUM
SUM = (TYPE + LENH + LENL + ΣPAYLOAD) & 0xFF
```

`0x01` sample frame (28 B header + N×uint16), `0x02` ACK, `0x03` settings block (22 B),
`0x10` set, `0x11` save, `0x12` get, `0x14` reboot to ISP, `0x15` test square,
`0x16`/`0x17` write/read calibration table, `0x19` firmware info.

### Known issues

- Time-base is calibrated against the device itself; absolute accuracy may be off by a few percent
- Square-wave frequencies derive from `GEN_TICK_US10 = 120` (12.0 µs/tick) and are approximate
- IRAM is full — put new globals in `__xdata`
- C sources are **GBK** encoded
- Double-click was removed (conflicts with single-press Run/Stop)
- Watchdog intentionally disabled (long sweeps look like a hang)

### License

MIT, as the original project.
