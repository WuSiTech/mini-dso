# Mini-DSO v1.7 — STC8A8K64D4 @ 45 MHz

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
  启动时**自动识别示波器串口**并自动读回全部参数；暂停按钮会**同时暂停单片机**；
  暂停时波形下方出现**与设备实时同步的滚动条**；界面/提示完整中英双语；
  无硬件时可用 `--demo` 演示。**软件就在仓库的 `py/` 目录**
- **21 档时基** 500 ms/div … 80 µs/div，逐档实测校准（EEPROM 可软件再校准）
- **双光标测量**：设备端独立光标页，直接读出 `dT` / `dV`（画在最底行）
- **可调信号源**：P1.1 方波 15 档频率（≈1 Hz~42 kHz）+ 占空比 1~99 %；
  P1.0 输出正弦 / 三角 / 锯齿（1-bit PDM，64 点/周期，**6 档频率 9~282 Hz 可调**），板载 **RP1(200K)+L1(1mH)+C3(22nF)**
  把它滤波成正弦，送到 **SIN 测试环**；RP1 同时就是正弦的幅值调节
- **中文点阵字库**：12×12 像素风，由 `py/gen_cnfont.py` 自动生成
- **波形滚动只在暂停时可用**：暂停后按住旋钮把光标切到左下角标尺（选中即反色），
  旋转即左右滚动；运行中没有这个选项，上电/读参数后旧的全局滚动模式已停用
- **串口协议完整**：采样流 + 参数读写 + EEPROM 保存 + 时基校准表 + 固件版本查询
  + 波形滚动位置读写（0x1A/0x1B）+ 运行/暂停（0x1C）
- 开机启动页 + 自检（EEPROM / 校准表 / 电池电压），烧录可软复位进 ISP

### 来源与致谢

- 原作：**CreativeLau** — https://github.com/CreativeLau/Mini-DSO
- 适配到 56DZ 版：https://www.elektormagazine.de/labs/reverse-project-mini-oscilloscope
- 进一步开发：**WuSi & DeepSeek** — https://github.com/WuSiTech/mini-dso
- 博客介绍（项目过程、功能与踩坑记录）：https://wstek.win/posts/minidso-modify/

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
| **按住 + 旋转** | 切换要调的项目（不会进入设置）；**暂停时**循环里多出第 6 项"滚动位置" |
| **短按** | **Run ⇄ Stop** 立即切换，画面冻结在按下瞬间 |
| **长按 ≥0.5 s** | 进入设置页 |

- 运行中可选 5 项：时基 / 量程 / 触发电平 / 触发沿 / 触发方式
- **暂停后**多出第 6 项 **滚动位置**：光标移到它上面时左下角标尺**整条反色**，
  此时旋转 = 左右滚动波形；切到其它项就恢复各自调参
- 双击功能已移除（只用于设置页的"取消修改"，见下）

#### 设置页（16 项）

旋转 = 改当前项的值；**按住 + 旋转** = 在项目间移动；**长按** = 保存并退出。

```
绘图模式      亮度        分压系数
方波输出      方波频率    占空比
波形输出      波形类型    波形频率
串口输出      语言        光标测量 >
光标测量 >  时基偏移表 >
输出波偏移表 >  创作者信息 >
电池电压
```

- **长按**：保存到 EEPROM，屏幕提示 `保存成功 / 保存失败`
- **短按两下**（仅设置页有效）：**取消修改**，从 EEPROM 回滚全部参数和校准表，
  提示 `已取消修改`，然后自动返回上一级（子页面→设置列表；设置列表→主界面）
- 主页**不会**响应双击（避免和 Run/Stop 冲突）

- **旋钮加速**：仅 4 个纯数值项（亮度 / 分压系数 / 方波频率 / 占空比）加速
  （慢转 1 步、≤120 ms 2 步、≤50 ms 3 步）；其他项一律 1 格 1 步
- **语言**：切换后立即生效并存 EEPROM
- **方波频率**：15 档，`1Hz/2/5/10/20/50/100/200/500/1k/2k/5k/10k/17k/42k Hz`
- **波形类型**：正弦 / 三角 / 锯齿（P1.0 输出，需外接 RC 才好看）

#### 光标测量页

进入：设置页滚到「光标测量」，**再旋转一格**进入。
进入后采样暂停，画面停在最后一帧上，方便对照测量。

| 操作 | 作用 |
|---|---|
| 旋转 | 左右移动**当前选中的**光标（范围 0~99，即图表 100 列内；每次移动整屏重绘，不留残影） |
| 按住 + 旋转 | 切换选中的是 A 还是 B（选中那条是实线，另一条虚线） |
| 短按 | **无作用**（光标页里不响应短按） |
| 长按 | 返回设置列表 |

屏幕**最底一行**显示 `dT:xxx us/ms  dV:x.xx V`（取代原来的电压范围/时基信息）。
`dT` = 两条光标的时间差，`dV` = 两条光标处的电压差。

#### 创作者信息页

进入：设置页滚到「创作者信息」，再旋转一格进入。
页面显示 LOGO、原作、开发、项目地址；`按住 + 旋转` 选择条目，
`旋转` 显示对应网址（长网址自动轮播），选到 `<Back` 旋转即返回；**短按无作用，长按**退回设置列表。

#### 时基偏移表页

进入：设置页滚到「时基偏移表 >」，**再旋转一格**进入。显示 `CAL 档位/20 + 对应时基`，
列表一次显示 5 档（`#档号  校准值`，选中行白底黑字）。

| 操作 | 作用 |
|---|---|
| 按住 + 旋转 | 切换要调的档位（0~20） |
| 旋转 | 微调该档校准值（慢转 ±1，快速转 ±8） |
| 短按 | **无作用** |
| 长按 | **立即写 EEPROM 并提示保存成功**，然后回设置列表 |

这就是上位机「时基校准」写的那张表（21 档延时/偏移量），设备上也能直接看和改。

#### 输出波偏移表页

进入：设置页滚到「输出波偏移表 >」，再旋转一格进入。用来校准两路输出波形的频率：

- `#0~#14`：P1.1 方波 15 档，偏移量单位 **0.1 µs**（加到该档周期上）
- `#15~#20`：P1.0 正弦/三角/锯齿 6 档，偏移量单位 **0.1 µs**（加到每个查表步进的周期上）

| 操作 | 作用 |
|---|---|
| 按住 + 旋转 | 选择条目（0~20） |
| 旋转 | 调偏移（慢转 ±1，快转 ±8） |
| 长按 | 立即写 EEPROM 并提示保存成功，然后回列表 |

上位机可以用「输出波偏移」对话框读写这张表（命令 `0x1D` / `0x1E`）。

#### 信号源

1. 设置页打开 `方波输出`（P1.1）和/或 `波形输出`（P1.0）
2. 调 `方波频率`、`占空比`、`波形类型`
3. 关闭时引脚被拉到 0 V

两路输出分别送到板上的两个测试环：

| 测试环 | 来自 | 信号 | 调节 |
|---|---|---|---|
| `PWM` | P1.1 | 方波（频率 / 占空比可调） | RP2(500R) 调幅 |
| `SIN` | P1.0 | 正弦 / 三角 / 锯齿（约 80 Hz） | RP1(200K) 调幅 |

> 板上 SIN 网络是 RP1 + L1(1 mH) + C3(22 nF) 的低通滤波，所以正弦频率必须很低；
> 早期版本按 1.1 kHz 生成，被这个网络滤到只剩几 mV，看起来像"没有输出"。
> 现在改为软件 PWM（16 个载波时钟、即 4.5 kHz 载波，64 点/周期，并用 16 周期抖动把占空比提升到 8 位，约 70~80 Hz），经滤波后 SIN 上能看到正弦，
> 幅值用 RP1 调（电位器位置同时影响滤波截止频率，调到幅值够大且波形干净即可）。

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
2. 打开软件：会**自动扫描串口并识别示波器**（发 0x19 探测），识别到就自动选好 COM
3. 点「连接」→ 自动读回全部参数（时基/量程/触发/亮度/方波频率/波形类型/语言…），
   状态栏显示固件版本
4. 参数面板改任何值**即时生效**（不等按钮）
5. 点「保存到 EEPROM」把当前参数写进设备；「读取」可随时读回
6. 「一键校准」会驱动设备输出测试方波、自动测量全部 21 档时基并写回校准表
7. **暂停**：同时暂停单片机（0x1C），上位机界面不冻结；此时波形下方**滚动条**可拖，
   位置与设备左下角标尺双向同步

**界面功能**：

| 区域 / 按钮 | 说明 |
|---|---|
| 波形区 | 实时波形（矢量/点阵）；滚轮缩放、Ctrl+滚轮纵向、拖动平移 |
| 测量 | Vpp / Vmax / Vmin / Vrms / Vavg / 频率 / 周期 / 占空比 / 上升时间 |
| 光标 | Shift+左键放置、拖动、双击复位，显示 Δt / ΔV |
| 参数面板 | 绘图模式、亮度(BRT)、分压系数 LSB、时基、电压量程、触发电平/沿/方式、输出开关、方波频率、占空比、波形类型、设备语言 |
| 频谱 | 切到 FFT 视图（128 点 Hann 窗） |
| 暂停 | 暂停**单片机**采样（0x1C），界面照常刷新、最后一帧保留 |
| 滚动条 | 暂停时可用：拖动左右滚动波形，与设备标尺位置实时同步 |
| 保存波形 (CSV) | 时间 / 原始 ADC / 电压(mV) |
| 保存截图 (PNG) | 当前画面 |
| 语言 | 上位机界面中英切换 |
| 时基校准 | 自动校全部 21 档时基（慢档低频率参考、快档 9 kHz 参考） |
| 输出波偏移 | 打开对话框读写 21 个输出频率偏移值（方波 15 档 + 波形 6 档） |
| 声卡校准 | 用电脑声卡做**绝对频率基准**：把 PWM（方波）或 SIN（波形）环经分压接到声卡输入，点对应按钮自动测频并回写偏移表（需 pip install sounddevice numpy） |

### 编译

需要 **SDCC 4.6.0**（`sdcc`/`sdar`/`sdranlib` 在 PATH）。

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

> ⚠️ **必须带 `--stack-auto`**：8051 直接寻址 RAM 只有 128 B，不加会报
> `Could not get ... consecutive bytes in internal RAM for area DSEG`。

资源占用（v1.4.1）：ROM 38,693 / 64,512 (60%)、XRAM 3,558 / 8,192、栈 217 B。

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
| 0x1A | DSO→PC | 波形滚动位置：`[0]offset(int8) [1]TriPos [2]running [3]最大偏移` |
| 0x1B | PC→DSO | 设置滚动位置：`[0]=offset(int8)` |
| 0x1C | PC→DSO | 运行/暂停：`[0]=1 运行 / 0 暂停` |

参数块（22 B）：`Lsb(u16) PlotMode ScaleH ScaleV_Auto RulerVMax(u16) RulerVMin(u16)
TriLevel(u16) TriMode TriSlope WaveScroll Brightness OutPWM OutSIN OutUART
GenFreqIdx GenDuty WaveType Lang`

### 目录结构

```
mini-dso/
├─ src/            固件源码
├─ include/        头文件（cnfont.h 中文字模、bmp.h LOGO、keys.h …）
├─ user/main.c     主程序 + 中断 + 主循环
├─ build/          minidso.hex（原版）/ minidso_uart.hex（当前 v1.4.1）
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
- 双击功能已移除；**设置页里的"连按两下"= 取消修改**，主页不响应双击
- 波形滚动只在**暂停**时可用（运行中旋转永远调参数）
- 旧的全局 `WaveScroll` 模式已停用（参数块里该字节固定为 0，只为协议兼容保留）
- 不启用看门狗：长时基采样一轮 4.4 s，软件无法与卡死区分，会误复位
- 暂停后恢复运行不会再清屏：先保留旧波形，等这轮扫描完成再刷新（慢时基约 4.4 s）

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
  EEPROM save, CSV/PNG export, `--demo` mode without hardware.
  It auto-detects the scope's COM port on startup, reads all settings, keeps the UI in
  sync, and its Pause button pauses the MCU too. **The software lives in `py/`**
- **21 time-base ranges** (500 ms/div … 80 µs/div), individually calibrated
- **On-device dual-cursor page** showing `dT` / `dV` on the bottom line
- **Waveform scroll is paused-only**: while paused, press+rotate to the bottom-left
  ruler (it inverts when selected) and rotate to scroll; while running it is unavailable
- **Signal generator**: P1.1 square wave, 15 frequencies (≈1 Hz–42 kHz), duty 1–99 %;
  P1.0 sine / triangle / sawtooth (software PWM, ~80 Hz) filtered by the on-board
  **RP1 (200K) + L1 (1 mH) + C3 (22 nF)** network into the **SIN** test loop;
  RP1 doubles as the sine amplitude control
- 12×12 pixel Chinese font, generated by `py/gen_cnfont.py`
- Full UART protocol: sample stream, settings R/W, EEPROM save, calibration table,
  version query, scroll position read/write (0x1A/0x1B), run/pause (0x1C)

### Credits

- Original: **CreativeLau** — https://github.com/CreativeLau/Mini-DSO
- 56DZ adaptation: https://www.elektormagazine.de/labs/reverse-project-mini-oscilloscope
- Further development: **WuSi & DeepSeek** — https://github.com/WuSiTech/mini-dso
- Blog post (Chinese, project story & lessons learned): https://wstek.win/posts/minidso-modify/

### Controls (device)

| Action | Function |
|---|---|
| Rotate | Adjust the currently selected item (time base / range / trigger level / slope / trigger mode) |
| Press + rotate | Select which item to adjust (does not enter settings) |
| Short press | Run ⇄ Stop immediately |
| Long press (≥0.5 s) | Enter / exit settings |

While running there are 5 selectable items; **once paused** a 6th one appears –
*scroll position*: press+rotate onto it (the bottom-left ruler inverts), then rotate to
scroll the waveform left/right. Other items keep adjusting their own parameter.
Double-click on the main screen was removed.

Settings page: rotate = change value, **press+rotate = move between items**,
long press = **save to EEPROM and show `Save Success`**,
**double-click = discard changes** (reloads settings + calibration from EEPROM, shows
`Changes discarded`, then returns one level up). Double-click only works inside settings.
15 items:
`Plot mode, Brightness, LSB, PWM out, PWM freq, Duty, Wave out, Wave type, UART out,
Language, Cursor >, Dev-er Info >, Cal table >, Batt voltage`.
Encoder acceleration applies only to the four numeric items (brightness, LSB,
PWM frequency, duty): 1 step slow, 2 steps ≤120 ms, 3 steps ≤50 ms.

Cursor page: enter from settings (select “Cursor”, rotate once more).
Sampling stops while the page is open, so the trace is frozen on the last frame.

| Action | Function |
|---|---|
| Rotate | Move the **currently selected** cursor (range 0~99, i.e. inside the 100-column chart; full redraw each step, no residue) |
| Press + rotate | Switch selection between A and B (selected one is solid, the other dashed) |
| Short press | **No effect** (ignored inside the cursor page) |
| Long press | Back to the settings list |

The bottom line shows `dT` (time difference) and `dV` (voltage difference).

Creator info page: select “Dev-er Info” then rotate to open; press+rotate selects
Original / Developer / Project URL / `<Back`; rotate shows the corresponding URL
(marquee for long URLs); short press does nothing, long press returns.

Calibration table page: select “Cal table” then rotate to open. Shows `CAL n/20` plus the
matching time base and 5 entries (`#index  value`, selected row inverted).
Press+rotate = choose index, rotate = adjust value (slow ±1, fast ±8),
short press = **no effect**,
long press = **write EEPROM immediately (save message)** and go back to the settings list.

### Controls (PC host, `py/dso_gui.py`)

```bat
pip install pyserial pillow
python py\dso_gui.py            :: real device
python py\dso_gui.py --demo     :: demo without hardware
python py\dso_gui.py --selftest :: protocol self-test
```

1. Set `UART out = ON` on the device and connect its USB serial port
2. Start the software – it **auto-detects the scope** (probes 0x19) and preselects the COM port
3. Press “Connect” – all parameters are read back automatically and the firmware version
   appears in the status bar
4. Parameter changes on the right panel are applied immediately
5. “Save to EEPROM” writes them to the device; “Read” fetches them back
6. “One-click calibrate” measures all 21 time bases and writes the calibration table
7. **Pause also pauses the MCU** (0x1C) while the GUI keeps refreshing; a horizontal
   **scroll slider** under the waveform then scrolls the device (bidirectional sync)

Waveform view: mouse wheel = zoom, Ctrl+wheel = vertical, drag = pan.
Measurements: Vpp/Vmax/Vmin/Vrms/Vavg/frequency/period/duty/rise time.
Cursors: Shift+click to place, drag to move, double-click to reset (Δt/ΔV),
or press the “Cursor” button to drop both at once.
Also: FFT view, pause, CSV/PNG export, full UI language switch.

### Build

SDCC 4.6.0 required:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

`--stack-auto` is mandatory (only 128 B of directly addressable IRAM).
Current usage (v1.4.1): ROM 38,693 / 64,512 B, XRAM 3,558 / 8,192 B, stack 217 B.

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
`0x16`/`0x17` write/read calibration table, `0x19` firmware info,
`0x1A` scroll position read (`[0]offset [1]TriPos [2]running [3]max offset`),
`0x1B` scroll position set (`[0]=offset`), `0x1C` run/pause (`[0]=1 run / 0 pause`).

### Known issues

- Time-base is calibrated against the device itself; absolute accuracy may be off by a few percent
- Square-wave frequencies derive from `GEN_TICK_US10 = 120` (12.0 µs/tick) and are approximate
- IRAM is full — put new globals in `__xdata`
- C sources are **GBK** encoded
- The wave output (P1.0) uses a software PWM inside the Timer1 ISR: on this chip the
  PCA/CCEX0 output does not appear on P1.0, and the on-board SIN filter is a slow
  (RP1 200K + 22 nF) low-pass, so the sine is ~80 Hz rather than kHz
- Double-click was removed from the main screen; inside settings a double-click means
  *discard changes*
- Waveform scrolling is paused-only (running always adjusts parameters)
- The old global `WaveScroll` mode is disabled (the settings byte stays 0 for protocol compatibility)
- Watchdog intentionally disabled (long sweeps look like a hang)
- Resuming from pause keeps the old trace until the new sweep finishes (≈4.4 s at 500 ms/div)

### License

MIT, as the original project.
