# Mini-DSO v1.8.1 — STC8A8K64D4 @ 45 MHz

**中文** | [English](#english-version)

---

## 中文版

### 简介

把 [CreativeLau/Mini-DSO](https://github.com/CreativeLau/Mini-DSO) v0.3 移植到
**56DZ 版 STC8A8K64D4 核心板**（MCU 内部 **IRC 45 MHz**、SSD1306 128×64 SPI OLED、EC11 旋钮），
并在此基础上做了进一步开发。

本版固件为 **v1.8.1**：MCU 内部 IRC 45 MHz；Timer0 250 µs 时基（旋钮 / 按键 / 电池计时）；
Timer1 中断约 72.1 kHz，驱动 P1.1 方波与 P1.0 波形输出；EEPROM 用户区 1 KB（2×512 B 扇区）。

### 特色

- **中英双语界面**：设置页 / 信息页 / 启动页均提供中文 ⇄ English，在设置页一键切换，语言存 EEPROM
- **可以使用电脑作为上位机**：`py/dso_gui.py` 提供实时波形、FFT、自动测量、双光标、
  时基一键校准、参数读写、EEPROM 保存、波形 CSV / 截图 PNG 导出；
  启动时**自动识别示波器串口**并自动读回全部参数；暂停按钮会**同时暂停单片机**；
  暂停时波形下方出现**与设备实时同步的滚动条**；界面 / 提示完整中英双语；
  无硬件时可用 `--demo` 演示。**软件就在仓库的 `py/` 目录**
- **21 档时基** 500 ms/div … 80 µs/div，逐档实测校准（EEPROM 可软件再校准）
- **双光标测量**：设备端独立光标页，直接读出 `dT` / `dV`（画在最底行）
- **可调信号源**：P1.1 方波 15 档频率（≈1 Hz~42 kHz）+ 占空比 1~99 %；
  P1.0 输出正弦 / 三角 / 锯齿（1-bit PDM，64 点/周期，**6 档频率 9~282 Hz 可调**），
  板载 **RP1(200K)+L1(1mH)+C3(22nF)** 把它滤波成正弦，送到 **SIN 测试环**；
  RP1 同时就是正弦的幅值调节
- **中文点阵字库**：12×12 像素风，由 `py/gen_cnfont.py` 自动生成
- **波形滚动只在暂停时可用**：暂停后按住旋钮把光标切到左下角标尺（选中即反色），
  旋转即左右滚动；运行中没有这个选项
- **串口协议完整**：采样流 + 参数读写 + EEPROM 保存 + 时基校准表 + 延时模型 + 每档采样间隔
  + 输出波偏移表 + 生成器系数 + 固件版本查询 + 波形滚动位置 + 运行/暂停
- 开机启动页 + 自检（EEPROM / 校准表 / 电池电压），烧录可软复位进 ISP

### 校准与系数（存 EEPROM；时基 / 输出波偏移表可在设备上直接改）

EEPROM 用户区 **1024 B**（2 × 512 B 扇区）。本版 `Save_Options()` / `Read_Options()` 的数据布局：

| 地址 (B) | 内容 |
|---|---|
| 0~21 | 参数块（22 B，与协议 0x03 / 0x10 相同） |
| 22~31 | 保留（0xFF） |
| 32~33 | `'C','L'` 标记 |
| 34~75 | 时基校准表 CalTable[21]（21×uint16，小端） |
| 76 | 校准表校验和 |
| 77~79 | `'M','S'` + 参数块校验和 |
| 82~123 | 输出波偏移 OutOff[21]（21×int16，小端，单位 0.1 µs） |
| 124~126 | `'O','C'` + 校验和 |
| 128~140 | 延时模型 A1/B1/A2/B2/THR（5×uint16）+ `'D','M'` + 校验和 |
| 142~158 | 生成器系数 TK + WS1~WS6（1+6×uint16）+ `'G','M'` + 校验和 |
| 176~262 | DtTbl[21]（21×uint32，小端，单位 0.01 µs）+ `'D','T'` + 校验和 |

以上共 263 B，位于第一个 512 B 扇区；第二个扇区本版固件未使用。

EEPROM 中的三张表：

| 位置 | 内容 |
|---|---|
| 设置 → 时基偏移表（26 项） | #0~#20：21 档采样延时（CalTable）；#21~#25：延时模型系数 A1/B1/A2/B2/THR |
| 设置 → 输出波偏移表（26 项） | #0~#14：方波 15 档周期偏移；#15~#20：波形 6 档步进偏移；#21：生成器 tick TK；#22~#25：波形步进周期 WS1~WS4 |
| EEPROM 实测表 DtTbl | 21 档真实采样间隔（0.01 µs），频率读数与时间轴的依据；设备页不显示，用 0x21/0x22 读写 |

当前标定值：TK = 117，WS = [12281, 5799, 3229, 1559, 774, 395]，
A1/B1/A2/B2/THR = 12955/1800/14258/1550/300。

> 上位机「输出波偏移」对话框与协议 `0x1D` / `0x1E` 仍然只读写前 21 项偏移
> （方波 15 档 + 波形 6 档）；TK 与全部 6 个 WS 系数通过 `0x23` / `0x24` 读写
> （设备页只列出 #22~#25，即 WS1~WS4）。

### 技术说明：公式

> 以下公式与 `src/chart.c`、`src/settings.c`、`user/main.c`、`src/adc_stc8.c` 的实现一致；
> 变量名沿用代码，除特别注明外均为整数运算（C 语言截断），单位已标注。

#### A. 电压换算

| 变量 | 含义 | 单位 / 默认值 |
|---|---|---|
| `ADC` | 12 位 ADC 读数 | 0~4095 |
| `BGV` | MCU 内部基准电压（`GetBGV_cpv()` 从 ROM 校准字 `0xFDF7` 读取，超出 900~1800 mV 时回退 1200） | mV，实测约 1185 |
| `ADCbg` | 内部基准通道（CH16）的 ADC 读数（丢 2 次后 16 次平均） | ADC 码 |
| `Lsb` | 输入分压比 ×100 | 默认 600，范围 50~750 |
| `mv` | 换算出的电压 | mV |

```
mV  = ADC * BGV * Lsb / ADCbg / 100      // c_ADC_mv()
ADC = mv * ADCbg * 100 / (BGV * Lsb)     // Convert_mv_ADC()
```

- 正算用于电压显示、光标 `dV`、电池电压；反算用于把纵轴标尺的 mV 端点换回 ADC，作为绘图上下限。
- `Lsb` = 分压比 ×100（例如分压比 6.00 → LSB = 600）。**这也是 LSB 有上限的原因**：
  中间乘积按 uint32 计算，12 位满量程 4095、按代码注释里的上界 BGV≈1349 mV 计算，
  `Lsb` 不能超过 `2^32 / (4095 × 1349) ≈ 777`，因此固件取 `LSB_MAX = 750`（`LSB_MIN = 50`）。

#### B. 时基 / 采样间隔模型

| 变量 | 含义 | 单位 |
|---|---|---|
| `CalTable[i]` | 第 i 档采样延时参数（#0~#14 为 µs；#15~#19 为 `DelayFine()` 的 0.25 µs 步进值；#20 档不用延时） | — |
| `DtTbl[i]` | 第 i 档实测每采样点间隔 | **0.01 µs**（uint32） |
| `DtA1/DtB1` | `CalTable >= DtThr` 时使用的模型系数 | — |
| `DtA2/DtB2` | `CalTable < DtThr` 时使用的模型系数 | — |
| `DtThr` | 模型分段阈值 | — |

EEPROM 中没有有效 DtTbl 时，`DtTbl_Defaults()` 按下式生成默认表：

```
nominal = CalTable[i] * A / 100 + B
(A, B) = (DtA1, DtB1)   if CalTable[i] >= DtThr
         (DtA2, DtB2)   otherwise
DtTbl[i] = nominal                       // 单位 0.01 µs
```

默认系数 `A1/B1/A2/B2/THR = 12955/1800/14258/1550/300`（存 EEPROM，可用 0x1F/0x20 或设备页 #21~#25 修改）。

- **快档特例**：#15~#20 的默认值不经过上式，直接取标称
  20 / 12 / 8 / 6 / 4 / 3.2 µs（0.01 µs 单位即 2000/1200/800/600/400/320）。
- **EEPROM 中的 21 档实测 DtTbl 优先于模型值**。写回实测表可用 `py/restore_all.py`
  （内置实测值，存在 `build/dtcal.json` 时优先用它），协议 `0x21` / `0x22` 可读写。
- 设备页显示：时基偏移表表头 `CAL n/25`，#0~#20 为 21 档延时，#21~#25 为 A1/B1/A2/B2/THR。
  修改模型系数只影响“下次由模型生成的默认 DtTbl”，不会自动改写已标定的 DtTbl。

#### C. 频率读数

`getWaveFreq()` 里有两种估计，先算周期平均法，再用触发沿计数法覆盖（有效时）。

**(1) 周期平均法（初值 / 兜底）**

```
WaveLength = tri_aft - tri_pre          // 一个整周期的样点数（getWaveLength()）
dt100      = max(DtTbl[ScaleH], 100)    // 0.01 µs，下限 100 防止除零/异常
WaveFreq   = 1e8 * wnum / (wsum * dt100)  // Hz
```

- 自动触发模式（`TriMode == 0`）且 `ScaleH > 4` 时取平均，窗口（`m_num` / `n_num`）：
  - `ScaleH == 5`（50 ms/div）：`m_num = 2, n_num = 1`
  - `ScaleH == 6/7`（30 / 20 ms/div）：`m_num = 4, n_num = 2`
  - 其余（<10 ms/div）：`m_num = 8, n_num = 3`
  - 累加到 `m_num` 次才更新（`wsum = ΣWaveLength`、`wnum = m_num`），不足则本次保持原值；
    暂停（`ADCRunning == 0`）时不做平均。
- 1e8 的由来：`dt100` 单位是 0.01 µs = 1e-8 s，所以 `f = wnum / (wsum × dt100 × 1e-8 s)`。
- 波长判断用的电平取“波幅中点”与“量程中点”中较小者，避免 ADC 偶发跳点造成频率乱跳。

**(2) 触发沿计数法（有效时覆盖上式）**

在 220 点缓冲区里统计越过触发电平（`TriLevel` 对应的 ADC 电平）的边沿：

```
n     = 穿越次数
first = 第一次穿越的样点下标
last  = 最后一次穿越的样点下标

f = (n - 1) * 50000000 / ((last - first) * DtTbl[ScaleH])    // Hz
```

- **0.5 系数**：按上下沿都计数，`(n-1)` 是半周期数，除以 2 得到整周期数，因此分子是 `5e7`
  而不是 `1e8`。
- 条件：`n >= 2` 且 `last > first`；不满足时保留周期平均法的结果。
- 显示：`c_WaveFreq_Str()` 格式化为 4 个字符（Hz / kHz / MHz），无有效读数显示 `****Hz`。

#### D. 方波发生器（P1.1）

设置项：`GenFreqIdx`（0~14）、`GenDuty`（1~99 %）、偏移 `OutOff[0..14]`。

```
p10      = GenPeriodUs10[idx] + OutOff[idx]   // 0.1 µs；OutOff 夹到 ±30000，p10 下限 100
GenPerQ  = p10 * 256 / GenTickCal             // Q8 周期；下限 512
GenHighQ = GenPerQ * GenDuty / 100            // Q8 高电平，自动夹到 < GenPerQ
```

Timer1 中断里：

```
GenPhase += 256;  if (GenPhase >= GenPerQ) GenPhase -= GenPerQ;
P1.1 = (GenPhase < GenHighQ);
```

- 周期 = `GenPerQ / 256` 个 Timer1 tick；标称频率 `f ≈ 1e7 / p10` Hz。
- `GenPeriodUs10[15]`（0.1 µs）对应的标称频率：

| idx | `GenPeriodUs10` | 标称频率 | 菜单显示 |
|---|---|---|---|
| 0 | 10000000 | 1 Hz | `1Hz` |
| 1 | 5000000 | 2 Hz | `2Hz` |
| 2 | 2000000 | 5 Hz | `5Hz` |
| 3 | 1000000 | 10 Hz | `10Hz` |
| 4 | 500000 | 20 Hz | `20Hz` |
| 5 | 200000 | 50 Hz | `50Hz` |
| 6 | 100000 | 100 Hz | `100Hz` |
| 7 | 50000 | 200 Hz | `200Hz` |
| 8 | 20000 | 500 Hz | `500Hz` |
| 9 | 10000 | 1 kHz | `1kHz` |
| 10 | 5000 | 2 kHz | `2kHz` |
| 11 | 2000 | 5 kHz | `5kHz` |
| 12 | 1000 | 10 kHz | `10kHz` |
| 13 | 555 | 18.0 kHz | `17kHz` |
| 14 | 238 | 42.0 kHz | `42kHz` |

- `GenTickCal`（TK）是实测标定的每 tick 长度，单位 0.1 µs：默认 `GEN_TICK_US10 = 120`
  （12.0 µs），当前标定值 **117**（存 EEPROM，可在输出波偏移表 #21 或 0x23/0x24 修改）。
- Timer1 为 12T 模式、重装值 52（`TH1 = 0xFF`、`TL1 = 0xCC`），中断约 **72.1 kHz**。
- `方波输出` 关闭时 P1.1 被明确拉低到 0 V。
- 0x15 可临时把 P1.1 改成 `TestDiv` 分频的测试方波（供上位机校时基），
  60 s 内没有新命令会自动恢复正常输出。

#### E. 波形输出（P1.0：正弦 / 三角 / 锯齿）

```
WaveStepQ[i] = (WaveStepCal[i] + OutOff[15 + i]) * 256 / GenTickCal   // Q8
```

- `WaveStepCal[6]` 为 6 档“每查表步进的标称周期”，单位 0.1 µs；`OutOff[15..20]` 为每档偏移
  （夹到 ±3000，合计下限 100）。
- Timer1 中断里 `WaveAcc += 256`，当 `WaveAcc >= WaveStepQ[WaveFreqIdx]` 时减掉它并推进 64 点查表
  （正弦 / 三角 / 锯齿，8 位幅度）；再用一个 256 累加器把幅度变成 **1-bit PDM** 输出到 P1.0，
  经板上低通滤波后得到模拟波形。
- 标称频率：

```
f = 1e7 / (64 * WaveStepCal[i])   Hz
```

  例：`17760` → 8.8 Hz，`555` → 282 Hz；6 档标称 8.8 / 17.6 / 35 / 70 / 141 / 282 Hz。
- 默认 `WaveStepCal = [17760, 8880, 4440, 2220, 1110, 555]`；当前标定值
  **WS = [12281, 5799, 3229, 1559, 774, 395]**，TK = 117。
- 板上 **RP1(200K) + L1(1mH) + C3(22nF)** 低通把 PDM 流平均成正弦/三角/锯齿，送到 `SIN` 测试环；
  RP1 兼作幅值调节。频率因此只能做到几百 Hz 以内。
- `波形输出` 关闭时 P1.0 被明确拉低到 0 V。

#### F. 采样 / 时基

- 每屏采样缓冲 `SAMPLE_NUM = 220` 点；屏幕横向显示 100 点，即 4 格 × 25 点/格。
- 每点间隔 = `DtTbl[ScaleH] × 0.01 µs`。
- 一轮完整扫描 = `220 × 每点间隔`。例：500 ms/div 档 `DtTbl ≈ 2127710`（0.01 µs）
  → 每点约 21.3 ms → 一轮约 **4.7 s**（所以恢复运行后要等这轮扫完波形才刷新）。
- 21 档时基：500 ms/div … 80 µs/div；最快档（80 µs/div）只在自动触发模式下可用。
- 单次 / 普通触发：先预采样 62 点（`PRE_BUF_NUM`），触发后再采 158 点（`AFT_BUF_NUM`）；
  自动触发直接连续采 220 点。

#### G. 电压量程 / 自动量程

- `VMax` / `VMin`：屏幕显示窗口（101 点）内的最大 / 最小 ADC，经 `c_ADC_mv()` 换成 mV。
- 自动量程（`ScaleV_Auto = 1`）时 `getRulerV()` 把 `VMax` / `VMin` 向外取整到 **500 mV 台阶**
  （按百位判断进位方向），再夹到 `0 ~ MAX_V(30000 mV)`，得到 `RulerVMax` / `RulerVMin`。
- 绘图上下限：`plotADCMax = Convert_mv_ADC(RulerVMax, ...)`，
  `plotADCMin = Convert_mv_ADC(RulerVMin, ...)`。
- `remap()` 把 ADC 钳到 `[plotADCMin, plotADCMax]` 后映射到屏幕纵坐标（先反相，电压越高越靠上）：

```
y = CHART_V_MIN + (plotADCMax - ADC) * (CHART_V_MAX - CHART_V_MIN)
                  / (plotADCMax - plotADCMin)
```

  其中 `CHART_V_MIN = 8`、`CHART_V_MAX = 52`（屏幕像素行）。
- 手动量程：旋转调 `RulerVMax`（1000 mV 附近用 100 mV 步进，更大时用 500 mV 步进，上限 30 V）；
  上限调到 ≤ 下限则恢复自动量程。

### 工具

```bat
python py\flash.py COM5 build\wusi_minidso.hex   # 烧录(自动带 EEPROM 分区, 烧完写回校准数据)
python py\dso_gui.py                            # 上位机(实时波形/FFT/光标/导出)
python py\restore_all.py COM5                   # 只写回 CalTable + DtTbl 并回读校验
python py\gen_cnfont.py                         # 重新生成中文字库 include/cnfont.h
```

### 来源与致谢

- 原作：**CreativeLau** — https://github.com/CreativeLau/Mini-DSO
- 适配到 56DZ 版：https://www.elektormagazine.de/labs/reverse-project-mini-oscilloscope
- 进一步开发：**WuSi & DeepSeek** — https://github.com/WuSiTech/mini-dso
- 博客介绍（项目过程、功能与踩坑记录）：https://wstek.win/posts/minidso-modify/

### 硬件

| 项目 | 说明 |
|---|---|
| MCU | STC8A8K64D4，内部 **IRC 45 MHz**（1T） |
| 显示 | SSD1306 128×64 OLED，**SPI** 接法（GND VCC D0 D1 RES DC CS） |
| 待测输入 | ADC 通道 1 = **P0.1**（高阻输入，外接分压网络） |
| 电池检测 | ADC 通道 14 = **P1.4**（分压系数 600） |
| 方波输出 | **P1.1**（推挽，15 档频率 + 占空比可调） |
| 波形输出 | **P1.0**（1-bit PDM，外部 RP1+L1+C3 低通） |
| 时基 | Timer0 **250 µs** 中断（旋钮四相解码 / 按键 / 电池计时） |
| 波形发生器时钟 | Timer1 中断约 **72.1 kHz**（12T，重装 52） |
| 旋钮 | EC11 编码器（A/B = P3.2 / P3.4，按键 = P3.3） |
| 串口 | P3.0 RXD / P3.1 TXD，**115200 8N1**（Timer2 波特率） |
| 指示灯 | P2.6 |
| 存储 | 内部 EEPROM 用户区 **1024 B**（2×512 B 扇区；下载选项 `program_eeprom_split=64512`） |

### 快速上手

1. 烧录 `build/wusi_minidso.hex`（见下方“烧录”）
2. 上电 → 启动页显示 LOGO 和自检结果 → 自动进主界面（默认选中「图像最大值」）
3. 把待测信号接到输入分压端（P0.1 通道）
4. 旋转旋钮调当前项，按住旋钮再旋转可在项目间轮换
5. 短按：暂停/继续；长按 0.5 秒：进设置

### 操作说明 — 设备

#### 主界面

屏幕布局：顶部状态区（`Auto` / `Run` / `Stop` / `Fail`、触发值 `T`、触发沿箭头、触发方式 `A/N/S`，
右上角为频率读数），中间波形区（26~126 列 × 8~52 行），左下角为滚动标尺，
底部显示电压范围（左）和时基（右）。

| 操作 | 作用 |
|---|---|
| **旋转** | 调整当前选中项的值 |
| **按住 + 旋转** | 切换要调的项目（不会进入设置），顺序见下 |
| **短按** | **Run ⇄ Stop** 立即切换，画面冻结在按下瞬间 |
| **长按 ≥0.5 s** | 进入设置页 |

- 运行中 5 项，循环顺序：
  **图像最大值（量程上限）→ 时基 → 触发电平 → 触发沿 → 触发方式**
- **暂停后**多出「滚动位置」一项，循环顺序：
  **图像最大值 → 滚动位置 → 时基 → 触发电平 → 触发沿 → 触发方式**；
  选中滚动位置时左下角整条标尺**反色**，旋转即左右滚动波形；恢复运行时自动退出该项。
- 上电默认选中「图像最大值」。
- 主页**不识别双击**：连按两下就是两次 Run/Stop 切换。

#### 设置页（16 项）

旋转 = 改当前项的值；**按住 + 旋转** = 在项目间移动；**长按** = 保存并退出设置。

| 序号 | 项目 | 说明 |
|---|---|---|
| 1 | 绘图模式 | 线（矢量）/ 点 |
| 2 | 亮度 | OLED 亮度 |
| 3 | 分压系数 | LSB（分压比 ×100） |
| 4 | 方波输出 | P1.1 开关 |
| 5 | 方波频率 | 15 档 |
| 6 | 占空比 | 1~99 % |
| 7 | 波形输出 | P1.0 开关 |
| 8 | 波形类型 | 正弦 / 三角 / 锯齿 |
| 9 | 波形频率 | 6 档 |
| 10 | 串口输出 | 采样流上传开关 |
| 11 | 语言 | 中文 / English |
| 12 | 光标测量 > | 旋转进入光标页 |
| 13 | 时基偏移表 > | 旋转进入时基偏移表页 |
| 14 | 输出波偏移表 > | 旋转进入输出波偏移表页 |
| 15 | 创作者信息 > | 旋转进入创作者信息页 |
| 16 | 电池电压 | 只读显示 |

- **长按**：保存到 EEPROM，屏幕提示 `保存成功 / 保存失败`，然后退出设置（长按是退出设置的**唯一**方式）。
- **双击**（设置页内有效，含各子页）：**放弃修改**——从 EEPROM 重新读取参数和校准表
  （界面语言保持当前选择），提示 `已取消修改 / Changes discarded`，然后回到**设置列表**；
  不会跳到主界面。
- **旋钮加速**：仅 4 个纯数值项（亮度 / 分压系数 / 方波频率 / 占空比）加速
  （慢转 1 步、≤120 ms 2 步、≤50 ms 3 步）；其他项一律 1 格 1 步。
- **语言**：切换后立即生效并存 EEPROM。
- **方波频率**：15 档，`1Hz/2/5/10/20/50/100/200/500/1k/2k/5k/10k/17k/42k Hz`。
- **波形类型**：正弦 / 三角 / 锯齿（P1.0 输出，需板上低通滤波）。
- **波形频率**：6 档，`9/18/35/70/141/282 Hz`。

#### 光标测量页

进入：设置页滚到「光标测量」，**再旋转一格**进入。进入后采样暂停，画面停在最后一帧上，
方便对照测量。

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
页面显示 LOGO、原作、开发、项目说明地址；本版固件在项目行显示版本号（`(v1.8.1)` / `PROJ:(v1.8.1)`）。
`按住 + 旋转` 选择条目，`旋转` 显示对应网址（长网址自动轮播），选到 `<Back` 旋转即返回；
**短按无作用，长按**退回设置列表。

#### 时基偏移表页

进入：设置页滚到「时基偏移表 >」，**再旋转一格**进入。表头显示 `CAL n/25`，
右侧显示当前条目的时基标签（#21~#25 显示 `A1` / `B1` / `A2` / `B2` / `THR`）；
列表一次显示 5 项（`#nn  校准值`，选中行白底黑字）。

| 操作 | 作用 |
|---|---|
| 按住 + 旋转 | 切换条目（0~25） |
| 旋转 | 微调数值（慢转 ±1，快速转 ±8） |
| 短按 | **无作用** |
| 长按 | **立即写 EEPROM 并提示保存成功**，然后回设置列表 |

- #0~#20：21 档采样延时 `CalTable`；
- #21~#25：延时模型系数 A1 / B1 / A2 / B2 / THR（默认 12955/1800/14258/1550/300）。
- 模型系数只影响以后由模型生成的默认 DtTbl；已标定的 DtTbl 不会自动重建。

#### 输出波偏移表页

进入：设置页滚到「输出波偏移表 >」，再旋转一格进入。用来校准两路输出波形的频率。
表头左侧 `OUT n/25`，**右上角显示当前条目的分组标记**：

- `#0~#14`：方波档，标记为 `SQ` + 频率（`SQ1Hz` `SQ2Hz` … `SQ17kHz` `SQ42kHz`）；
- `#15~#20`：波形档，标记为 `SIN` + 频率（`SIN9Hz` `SIN18Hz` … `SIN282Hz`）；
- `#21`：`TK`；
- `#22~#25`：`WS1` `WS2` `WS3` `WS4`。

列表行仍为 `#nn  数值`（5 项一屏，选中行白底黑字）。

| 操作 | 作用 |
|---|---|
| 按住 + 旋转 | 选择条目（0~25） |
| 旋转 | 调数值（#0~#20 与 WS 慢转 ±1、快转 ±8；TK 每格 ±1） |
| 长按 | 立即写 EEPROM 并提示保存成功，然后回设置列表 |

- `#0~#14`：P1.1 方波 15 档，偏移量单位 **0.1 µs**（加到该档周期上）
- `#15~#20`：P1.0 正弦/三角/锯齿 6 档，偏移量单位 **0.1 µs**（加到每个查表步进的周期上）
- `#21`：生成器 tick 标定值 TK（单位 0.1 µs，默认 120，当前 117）
- `#22~#25`：波形查表步进周期 WS1~WS4（单位 0.1 µs）；完整 6 档 WS 可用协议 0x23/0x24 读写

上位机可以用「输出波偏移」对话框读写前 21 项偏移（命令 `0x1D` / `0x1E`）；
TK 与 6 个 WS 系数通过 `0x23` / `0x24` 读写。

#### 信号源

1. 设置页打开 `方波输出`（P1.1）和/或 `波形输出`（P1.0）
2. 调 `方波频率`、`占空比`、`波形类型`、`波形频率`
3. 关闭时引脚被拉到 0 V

两路输出分别送到板上的两个测试环：

| 测试环 | 来自 | 信号 | 调节 |
|---|---|---|---|
| `PWM` | P1.1 | 方波（1 Hz~42 kHz，占空比 1~99 %） | RP2(500R) 调幅 |
| `SIN` | P1.0 | 正弦 / 三角 / 锯齿（6 档 9~282 Hz） | RP1(200K) 调幅 |

> 板上 SIN 网络是 RP1 + L1(1 mH) + C3(22 nF) 的低通滤波，所以波形频率只能做到几百 Hz 以内；
> 幅值用 RP1 调（电位器位置同时影响滤波截止频率，调到幅值够大且波形干净即可）。

### 操作说明 — 上位机（PC）

> 光标：Shift+左键放置 / 拖动移动 / 双击清除，也可以点界面上的「光标」按钮一键放两条。

`py/dso_gui.py` 需要 Python 3 + `pyserial`（画 PNG 需要 `pillow`；声卡校准需要 `sounddevice numpy`）：

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
   状态栏显示固件版本（本版 `v1.8.1`）
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
| 输出波偏移 | 对话框读写 21 项输出频率偏移（方波 15 档 + 波形 6 档，0x1D/0x1E）；TK/WS 不在该对话框内，走 0x23/0x24 |
| 声卡校时基 | 电脑耳机输出播放 1 kHz 到示波器 INPUT，用声卡晶振做**绝对基准**测出时基误差，按比例缩放全部 21 档时基表（需 pip install sounddevice numpy） |
| 声卡校准 | 用电脑声卡做**绝对频率基准**：把 PWM（方波）或 SIN（波形）环经分压接到声卡输入，点对应按钮自动测频并回写偏移表（需 pip install sounddevice numpy） |

### 编译

需要 **SDCC 4.6.0**（`sdcc`/`sdar`/`sdranlib` 在 PATH）。

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

> ⚠️ **必须带 `--stack-auto`**：8051 直接寻址 RAM 只有 128 B，不加会报
> `Could not get ... consecutive bytes in internal RAM for area DSEG`。

资源占用（v1.8.1）：ROM 47,105 / 64,512 B (73%)、XRAM 4,399 / 8,192 B、栈 217 B。

中文字库改了之后重新生成：`python py\gen_cnfont.py`（生成 GBK 编码的 `include/cnfont.h`，不要手改）。

### 烧录

- **STC-ISP**：芯片 STC8A8K64D4，IRC 45 MHz，打开 `build/wusi_minidso.hex`，
  点下载后**断电再上电**
- **命令行**：`python -m stcgal -P stc8d -p COM5 -o program_eeprom_split=64512 build\wusi_minidso.hex`（需冷启动）
- **运行中自动烧录**：`python py\flash.py COM5 build\wusi_minidso.hex`
  （固件收到 `0x14` 后软复位进 ISP；脚本会带 `program_eeprom_split=64512`，烧完自动调
  `restore_all.py` 写回 CalTable + DtTbl）

> 烧录会整片擦除 EEPROM：设置和校准表回到默认值。
>
> **EEPROM 用户区 = 1 KB**：默认下载选项 `program_eeprom_split=65024` 只留 0.5 KB；
> 本项目用 **`program_eeprom_split=64512`**（65536−64512 = 1024 B = 2 × 512 B 扇区）。
> 当前固件的数据布局占第一个 512 B 扇区（共 263 B），第二个扇区未使用。

### 串口协议

```
A5 5A TYPE LENH LENL PAYLOAD[LEN] SUM
SUM = (TYPE + LENH + LENL + ΣPAYLOAD) & 0xFF
```

| TYPE | 方向 | 含义 |
|---|---|---|
| 0x01 | DSO→PC | 采样帧（28 B 头 + 100×uint16 原始 ADC） |
| 0x02 | DSO→PC | 应答：`[0]=0 成功 / 1 失败`，`[1]=附加状态` |
| 0x03 | DSO→PC | 参数块（22 B） |
| 0x10 | PC→DSO | 下发参数（22 B，立即生效） |
| 0x11 | PC→DSO | 保存到 EEPROM |
| 0x12 | PC→DSO | 读取参数（回 0x03） |
| 0x13 | PC→DSO | 软复位回用户程序（不擦 EEPROM，用于验证掉电保存） |
| 0x14 | PC→DSO | 软复位进 ISP（自动烧录用） |
| 0x15 | PC→DSO | 设置 P1.1 测试方波分频（2×uint8；`0` 恢复正常输出，60 s 无命令自动恢复） |
| 0x16 / 0x17 | PC↔DSO | 写 / 读时基校准表（21×uint16，42 B） |
| 0x18 | PC→DSO | 读 IAP 地址 16 字节（诊断用，`[0..1]=地址`） |
| 0x19 | DSO→PC | 固件信息：`[0..2]=主/次/修订版本`（本版 `1,8,1`）、`[3]=参数块长度(22)`、`[4]=采样头长度(28)`、`[5]=能力字节`、`[6]=默认 tick(120)` |
| 0x1A | DSO→PC | 波形滚动位置：`[0]offset(int8) [1]TriPos [2]running [3]最大偏移` |
| 0x1B | PC→DSO | 设置滚动位置：`[0]=offset(int8)` |
| 0x1C | PC→DSO | 运行/暂停：`[0]=1 运行 / 0 暂停` |
| 0x1D / 0x1E | PC→DSO | 读 / 写输出波偏移表（21×int16，EEPROM 82..123） |
| 0x1F / 0x20 | PC→DSO | 读 / 写延时模型系数 A1,B1,A2,B2,THR（5×uint16） |
| 0x21 / 0x22 | PC→DSO | 读 / 写每档真实采样间隔 DtTbl（21×uint32，单位 0.01 µs，EEPROM 176..259） |
| 0x23 / 0x24 | PC→DSO | 读 / 写生成器系数：TK + 6×WS（14 B = 1+6 uint16） |
| 0x30 | PC→DSO | IAP / EEPROM 诊断命令（开发用，正常上位机不使用） |

参数块（22 B）：`Lsb(u16) PlotMode ScaleH ScaleV_Auto RulerVMax(u16) RulerVMin(u16)
TriLevel(u16) TriMode TriSlope WaveFreqIdx Brightness OutPWM OutSIN OutUART
GenFreqIdx GenDuty WaveType Lang`

> DtTbl 是频率读数与时间轴的查表值：烧录 / 擦除后无效时固件按延时模型生成默认表，
> 建议烧后用 `py/restore_all.py` 写回实测表（内置实测值，或 `build/dtcal.json`）；
> 也可以用协议 0x21 / 0x22 单独读写。

### 目录结构

```
mini-dso/
├─ src/            固件源码
├─ include/        头文件（cnfont.h 中文字模、bmp.h LOGO、keys.h …）
├─ user/main.c     主程序 + 中断 + 主循环
├─ py/             上位机与工具（dso_gui.py / flash.py / restore_all.py / gen_cnfont.py）
├─ build/          wusi_minidso.hex（编译输出，另有 .map / .mem / .lk）
├─ build.ps1       一键编译
└─ README.md
```

### 已知事项

- 时基表按实测校准，绝对时间与外部基准可能仍有几个百分点偏差
- 最快的 80 µs/div 档只在自动触发模式下可用（单次/普通触发的中间计算来不及）
- 快档 #15~#20 的采样间隔受 ADC 转换开销限制（100 µs/div 档约 8.9 µs/点、150 µs/div 档约 6.6 µs/点）；
  频率读数已按 DtTbl 修正，但**屏幕时基标签与真实时间轴仍有偏差**
- 频率读数使用触发沿计数法（周期平均法作初值/兜底），整数样点与电平量化仍会带来少量残差
- 方波 / 波形频率由标定系数 TK 和每档偏移（EEPROM）决定，标称值近似；
  TK 默认 120（12.0 µs/tick），当前标定 117
- BGV 实测约 1185 mV；ROM 校准字无效时回退 1200 mV
- IRAM 已满，新增全局变量请放 `__xdata`
- 所有 C 源文件是 **GBK** 编码；`README.md` 为 UTF-8
- 设置页双击 = 放弃修改并回设置列表（不会跳主界面）；主页不响应双击；长按是退出设置的唯一方式
- 波形滚动只在**暂停**时可用（运行中旋转永远调参数）
- 旧的全局 `WaveScroll` 模式已停用（读参数时强制清 0，只为兼容保留）
- 不启用看门狗：长时基采样一轮约 4.7 s，软件无法与卡死区分，会误复位
- 暂停后恢复运行不会再清屏：先保留旧波形，等这轮扫描完成再刷新（500 ms/div 档约 4.7 s）

### 许可

原始项目 MIT（见 `src/` 文件头）；本移植与增强同样以 MIT 发布。

---

<a id="english-version"></a>

## English version

### What it is

Port of [CreativeLau/Mini-DSO](https://github.com/CreativeLau/Mini-DSO) v0.3 to the
**56DZ STC8A8K64D4 board** (MCU internal **IRC 45 MHz**, SSD1306 128×64 SPI OLED, EC11 encoder),
plus further development.

This release is **v1.8.1**: internal IRC 45 MHz; Timer0 250 µs tick (encoder / keys / battery);
Timer1 ISR ≈72.1 kHz driving the P1.1 square wave and the P1.0 wave output;
EEPROM user area 1 KB (2 × 512 B sectors).

### Features

- **Bilingual UI** (Chinese ⇄ English) for the settings / info / splash screens; switched from the
  settings page, language stored in EEPROM
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
  P1.0 sine / triangle / sawtooth (1-bit PDM, 64 points/cycle, **6 frequency bands 9–282 Hz**)
  filtered by the on-board **RP1 (200K) + L1 (1 mH) + C3 (22 nF)** network into the
  **SIN** test loop; RP1 doubles as the sine amplitude control
- 12×12 pixel Chinese font, generated by `py/gen_cnfont.py`
- Full UART protocol: sample stream, settings R/W, EEPROM save, calibration table,
  delay model, per-range sample intervals, output offsets, generator coefficients,
  version query, scroll position read/write, run/pause

### Calibration coefficients (EEPROM; time-base and output-offset tables are editable on device)

EEPROM user area **1024 B** (2 × 512 B sectors). Layout written by `Save_Options()` / `Read_Options()`:

| Address (B) | Content |
|---|---|
| 0~21 | settings block (22 B, same as protocol 0x03 / 0x10) |
| 22~31 | reserved (0xFF) |
| 32~33 | `'C','L'` magic |
| 34~75 | CalTable[21] (21×uint16 LE) |
| 76 | calibration checksum |
| 77~79 | `'M','S'` + settings checksum |
| 82~123 | OutOff[21] (21×int16 LE, unit 0.1 µs) |
| 124~126 | `'O','C'` + checksum |
| 128~140 | delay model A1/B1/A2/B2/THR (5×uint16) + `'D','M'` + checksum |
| 142~158 | generator coefficients TK + WS1~WS6 (1+6×uint16) + `'G','M'` + checksum |
| 176~262 | DtTbl[21] (21×uint32 LE, unit 0.01 µs) + `'D','T'` + checksum |

263 bytes total, all inside the first 512 B sector; the second sector is unused by this firmware.

On-device tables and the measured DtTbl:

| Location | Content |
|---|---|
| Settings → Time offset (26 entries) | #0~#20: 21 per-range sample delays (CalTable); #21~#25: delay model A1/B1/A2/B2/THR |
| Settings → Wave offset (26 entries) | #0~#14: square-wave 15-band period offsets; #15~#20: wave 6-band step offsets; #21: generator tick TK; #22~#25: wave step period WS1~WS4 |
| EEPROM DtTbl | 21 measured sample intervals (0.01 µs), basis of the frequency readout and time axis; not shown on device, use 0x21/0x22 |

Current calibration: TK = 117, WS = [12281, 5799, 3229, 1559, 774, 395],
A1/B1/A2/B2/THR = 12955/1800/14258/1550/300.

> The PC host “Wave offset” dialog and protocol `0x1D` / `0x1E` still read/write only the first
> 21 offsets (15 square + 6 wave); TK and all 6 WS coefficients are read/written with
> `0x23` / `0x24` (the device page only shows #22~#25 = WS1~WS4).

### Technical notes: formulas

> The formulas below follow `src/chart.c`, `src/settings.c`, `user/main.c` and `src/adc_stc8.c`.
> Variable names are the code's, all arithmetic is integer (C truncation) unless noted.

#### A. Voltage conversion

| Variable | Meaning | Unit / default |
|---|---|---|
| `ADC` | 12-bit ADC reading | 0–4095 |
| `BGV` | internal band-gap reference (`GetBGV_cpv()`, from ROM word `0xFDF7`; falls back to 1200 outside 900–1800) | mV, measured ≈1185 |
| `ADCbg` | ADC reading of the band-gap channel (CH16; 2 reads dropped, then average of 16) | ADC counts |
| `Lsb` | input divider ratio ×100 | default 600, range 50–750 |
| `mv` | converted voltage | mV |

```
mV  = ADC * BGV * Lsb / ADCbg / 100      // c_ADC_mv()
ADC = mv * ADCbg * 100 / (BGV * Lsb)     // Convert_mv_ADC()
```

- The forward formula is used for voltage display, cursor `dV` and battery voltage; the reverse one
  converts the vertical ruler ends (mV) back to ADC for the plot mapping.
- `Lsb` = divider ratio ×100 (ratio 6.00 → 600). **This is why LSB has an upper limit**: the
  intermediate product uses uint32 and must fit `2^32`; with a 12-bit full scale of 4095 and the
  upper-bound BGV ≈ 1349 mV quoted in the code comments, `Lsb` cannot exceed
  `2^32 / (4095 × 1349) ≈ 777`, hence `LSB_MAX = 750` (`LSB_MIN = 50`).

#### B. Time-base / sample-interval model

| Variable | Meaning | Unit |
|---|---|---|
| `CalTable[i]` | delay parameter of band i (#0~#14 in µs; #15~#19 in 0.25 µs `DelayFine()` steps; band #20 uses no delay) | — |
| `DtTbl[i]` | measured per-sample interval of band i | **0.01 µs** (uint32) |
| `DtA1/DtB1` | model coefficients used when `CalTable >= DtThr` | — |
| `DtA2/DtB2` | model coefficients used when `CalTable < DtThr` | — |
| `DtThr` | model split threshold | — |

When the EEPROM has no valid DtTbl, `DtTbl_Defaults()` builds it as:

```
nominal = CalTable[i] * A / 100 + B
(A, B) = (DtA1, DtB1)   if CalTable[i] >= DtThr
         (DtA2, DtB2)   otherwise
DtTbl[i] = nominal                       // unit 0.01 µs
```

Default coefficients `A1/B1/A2/B2/THR = 12955/1800/14258/1550/300`
(stored in EEPROM; editable via 0x1F/0x20 or device page #21~#25).

- **Fast-band exception**: #15~#20 defaults do not use the formula; they are fixed nominal
  20 / 12 / 8 / 6 / 4 / 3.2 µs (0.01 µs units: 2000/1200/800/600/400/320).
- **The 21 measured DtTbl values stored in EEPROM override the model.** They can be written with
  `py/restore_all.py` (built-in measured values, or `build/dtcal.json` when present) or via
  protocol `0x21` / `0x22`.
- On device: the time-offset page header is `CAL n/25`; #0~#20 are the 21 delays, #21~#25 are
  A1/B1/A2/B2/THR. Editing the coefficients only affects the next model-generated default DtTbl;
  an already calibrated DtTbl is not rebuilt automatically.

#### C. Frequency readout

`getWaveFreq()` computes two estimates: a period-average value first, then a trigger-edge
crossing estimate that overrides it when valid.

**(1) Period-average estimator (initial / fallback)**

```
WaveLength = tri_aft - tri_pre          // samples per whole period (getWaveLength())
dt100      = max(DtTbl[ScaleH], 100)    // 0.01 µs; floor 100 avoids div-by-zero / nonsense
WaveFreq   = 1e8 * wnum / (wsum * dt100)  // Hz
```

- Averaging applies in auto trigger mode (`TriMode == 0`) with `ScaleH > 4`
  (`m_num` / `n_num`):
  - `ScaleH == 5` (50 ms/div): `m_num = 2, n_num = 1`
  - `ScaleH == 6/7` (30 / 20 ms/div): `m_num = 4, n_num = 2`
  - otherwise (<10 ms/div): `m_num = 8, n_num = 3`
  - it updates only after `m_num` accumulations (`wsum = ΣWaveLength`, `wnum = m_num`),
    otherwise the previous value is kept; paused (`ADCRunning == 0`) → no averaging.
- The 1e8 factor: `dt100` is 0.01 µs = 1e-8 s.
- The crossing level for the wavelength search is the smaller of the waveform midpoint and the
  range midpoint, so isolated ADC glitches do not make the frequency jump.

**(2) Crossing estimator (overrides when valid)**

Over the 220-sample buffer, count crossings of the trigger level (`TriLevel`, as an ADC level):

```
n     = number of crossings
first = index of the first crossing
last  = index of the last crossing

f = (n - 1) * 50000000 / ((last - first) * DtTbl[ScaleH])    // Hz
```

- **The 0.5 factor**: both edges are counted, so `(n-1)` is the number of half-periods; dividing
  by 2 gives whole periods, hence `5e7` instead of `1e8`.
- Valid when `n >= 2` and `last > first`; otherwise the period-average value is kept.
- Display: `c_WaveFreq_Str()` formats 4 characters (Hz / kHz / MHz); no reading shows `****Hz`.

#### D. Square-wave generator (P1.1)

Settings: `GenFreqIdx` (0–14), `GenDuty` (1–99 %), offsets `OutOff[0..14]`.

```
p10      = GenPeriodUs10[idx] + OutOff[idx]   // 0.1 µs; OutOff clamped ±30000, p10 floor 100
GenPerQ  = p10 * 256 / GenTickCal             // Q8 period; floor 512
GenHighQ = GenPerQ * GenDuty / 100            // Q8 high time, clamped < GenPerQ
```

In the Timer1 ISR:

```
GenPhase += 256;  if (GenPhase >= GenPerQ) GenPhase -= GenPerQ;
P1.1 = (GenPhase < GenHighQ);
```

- Period = `GenPerQ / 256` Timer1 ticks; nominal frequency `f ≈ 1e7 / p10` Hz.
- `GenPeriodUs10[15]` (0.1 µs) and the nominal frequencies:

| idx | `GenPeriodUs10` | nominal | menu |
|---|---|---|---|
| 0 | 10000000 | 1 Hz | `1Hz` |
| 1 | 5000000 | 2 Hz | `2Hz` |
| 2 | 2000000 | 5 Hz | `5Hz` |
| 3 | 1000000 | 10 Hz | `10Hz` |
| 4 | 500000 | 20 Hz | `20Hz` |
| 5 | 200000 | 50 Hz | `50Hz` |
| 6 | 100000 | 100 Hz | `100Hz` |
| 7 | 50000 | 200 Hz | `200Hz` |
| 8 | 20000 | 500 Hz | `500Hz` |
| 9 | 10000 | 1 kHz | `1kHz` |
| 10 | 5000 | 2 kHz | `2kHz` |
| 11 | 2000 | 5 kHz | `5kHz` |
| 12 | 1000 | 10 kHz | `10kHz` |
| 13 | 555 | 18.0 kHz | `17kHz` |
| 14 | 238 | 42.0 kHz | `42kHz` |

- `GenTickCal` (TK) is the calibrated length of one tick, unit 0.1 µs: default
  `GEN_TICK_US10 = 120` (12.0 µs), current calibrated value **117** (EEPROM; editable on device
  page #21 or via 0x23/0x24).
- Timer1 runs in 12T mode with reload 52 (`TH1 = 0xFF`, `TL1 = 0xCC`) → ISR ≈ **72.1 kHz**.
- With `PWM out` off, P1.1 is driven low (0 V).
- `0x15` temporarily turns P1.1 into a `TestDiv`-divided test square (used for time-base
  calibration); it reverts to the normal output 60 s after the last command.

#### E. Wave output (P1.0: sine / triangle / sawtooth)

```
WaveStepQ[i] = (WaveStepCal[i] + OutOff[15 + i]) * 256 / GenTickCal   // Q8
```

- `WaveStepCal[6]` is the nominal period of one table step per band, unit 0.1 µs;
  `OutOff[15..20]` are per-band offsets (clamped ±3000, total floor 100).
- In the Timer1 ISR `WaveAcc += 256`; when `WaveAcc >= WaveStepQ[WaveFreqIdx]` it advances the
  64-entry table (sine / triangle / sawtooth, 8-bit amplitude); a 256 accumulator then turns the
  amplitude into a **1-bit PDM** stream on P1.0, averaged by the on-board low-pass filter.
- Nominal frequency:

```
f = 1e7 / (64 * WaveStepCal[i])   Hz
```

  e.g. `17760` → 8.8 Hz, `555` → 282 Hz; the 6 bands are nominally 8.8 / 17.6 / 35 / 70 / 141 / 282 Hz.
- Default `WaveStepCal = [17760, 8880, 4440, 2220, 1110, 555]`; current calibrated
  **WS = [12281, 5799, 3229, 1559, 774, 395]**, TK = 117.
- The on-board **RP1 (200K) + L1 (1 mH) + C3 (22 nF)** low-pass averages the PDM stream into a
  sine/triangle/sawtooth for the `SIN` test loop; RP1 also sets the amplitude. That is why the
  frequency only goes up to a few hundred Hz.
- With `Wave out` off, P1.0 is driven low (0 V).

#### F. Sampling / time base

- Sample buffer `SAMPLE_NUM = 220` points; the screen shows 100 points = 4 divisions × 25 points.
- Sample interval = `DtTbl[ScaleH] × 0.01 µs`.
- One sweep = `220 × interval`. For example, 500 ms/div: `DtTbl ≈ 2127710` (0.01 µs)
  → ≈21.3 ms per point → ≈**4.7 s** per sweep (why a resumed trace refreshes only after the sweep).
- 21 time-base bands: 500 ms/div … 80 µs/div; the fastest band (80 µs/div) is only available in
  auto trigger mode.
- Single / normal trigger: 62 pre-trigger samples (`PRE_BUF_NUM`), 158 post-trigger samples
  (`AFT_BUF_NUM`); auto trigger just samples 220 points continuously.

#### G. Voltage range / auto range

- `VMax` / `VMin`: max/min ADC over the displayed 101-point window, converted to mV with `c_ADC_mv()`.
- In auto range (`ScaleV_Auto = 1`), `getRulerV()` rounds `VMax` / `VMin` outward to **500 mV steps**
  (direction chosen from the hundreds digit), then clamps to `0 … MAX_V (30000 mV)` to produce
  `RulerVMax` / `RulerVMin`.
- Plot limits: `plotADCMax = Convert_mv_ADC(RulerVMax, ...)`,
  `plotADCMin = Convert_mv_ADC(RulerVMin, ...)`.
- `remap()` clamps the ADC value to `[plotADCMin, plotADCMax]` and maps it to the screen row
  (inverted, higher voltage at the top):

```
y = CHART_V_MIN + (plotADCMax - ADC) * (CHART_V_MAX - CHART_V_MIN)
                  / (plotADCMax - plotADCMin)
```

  with `CHART_V_MIN = 8`, `CHART_V_MAX = 52` (screen pixel rows).
- Manual range: rotating changes `RulerVMax` (100 mV steps up to 1000 mV, then 500 mV steps,
  max 30 V); if the max becomes ≤ the min, auto range is re-enabled.

### Tools

```bat
python py\flash.py COM5 build\wusi_minidso.hex   # flash (sets EEPROM split, then restores calibration)
python py\dso_gui.py                            # PC host (live waveform / FFT / cursors / export)
python py\restore_all.py COM5                   # write back CalTable + DtTbl and verify
python py\gen_cnfont.py                         # regenerate the Chinese font (include/cnfont.h)
```

### Credits

- Original: **CreativeLau** — https://github.com/CreativeLau/Mini-DSO
- 56DZ adaptation: https://www.elektormagazine.de/labs/reverse-project-mini-oscilloscope
- Further development: **WuSi & DeepSeek** — https://github.com/WuSiTech/mini-dso
- Blog post (Chinese, project story & lessons learned): https://wstek.win/posts/minidso-modify/

### Hardware

| Item | Detail |
|---|---|
| MCU | STC8A8K64D4, internal **IRC 45 MHz** (1T) |
| Display | SSD1306 128×64 OLED, **SPI** wiring (GND VCC D0 D1 RES DC CS) |
| Signal input | ADC channel 1 = **P0.1** (high impedance, external divider) |
| Battery sense | ADC channel 14 = **P1.4** (LSB 600) |
| Square output | **P1.1** (push-pull, 15 frequencies, duty 1–99 %) |
| Wave output | **P1.0** (1-bit PDM, external RP1+L1+C3 low-pass) |
| Time base | Timer0 **250 µs** tick (encoder quadrature decode / keys / battery) |
| Generator clock | Timer1 ISR ≈ **72.1 kHz** (12T, reload 52) |
| Encoder | EC11 (A/B = P3.2 / P3.4, button = P3.3) |
| UART | P3.0 RXD / P3.1 TXD, **115200 8N1** (Timer2 baud) |
| Indicator | P2.6 |
| Storage | internal EEPROM user area **1024 B** (2×512 B sectors; download option `program_eeprom_split=64512`) |

### Quick start

1. Flash `build/wusi_minidso.hex` (see “Flash” below)
2. Power on → splash screen with self-test → main screen (default selected item: range max)
3. Feed the signal into the input divider (P0.1 channel)
4. Rotate to adjust the selected item; press+rotate to cycle through items
5. Short press: pause/run; long press 0.5 s: settings

### Controls (device)

#### Main screen

Top status area (`Auto` / `Run` / `Stop` / `Fail`, trigger level `T`, slope arrow, trigger mode
`A/N/S`, frequency at the top right), waveform area (columns 26–126 × rows 8–52), bottom-left
scroll ruler, bottom line with voltage range (left) and time base (right).

| Action | Function |
|---|---|
| Rotate | Adjust the currently selected item |
| Press + rotate | Cycle the selected item (never enters settings), see order below |
| Short press | Run ⇄ Stop immediately, trace frozen at the press moment |
| Long press (≥0.5 s) | Enter settings |

- While running, 5 items in this order:
  **range max → time base → trigger level → trigger slope → trigger mode**
- Once **paused**, a 6th item appears; order:
  **range max → scroll position → time base → trigger level → trigger slope → trigger mode**.
  With scroll position selected the whole bottom-left ruler inverts and rotation scrolls the trace;
  resuming run leaves that item automatically.
- Range max is selected by default after boot.
- The main screen does **not** recognize double-click: two presses are two Run/Stop toggles.

#### Settings page (16 items)

Rotate = change the value, **press+rotate = move between items**, **long press = save and exit settings**.

| # | Item | Notes |
|---|---|---|
| 1 | Plot Mode | vector (lines) / dots |
| 2 | Brightness | OLED brightness |
| 3 | LSB | divider ratio ×100 |
| 4 | PWM Out | P1.1 on/off |
| 5 | PWM Freq | 15 bands |
| 6 | PWM Duty | 1–99 % |
| 7 | Wave Out | P1.0 on/off |
| 8 | Wave Type | sine / triangle / sawtooth |
| 9 | Wave freq | 6 bands |
| 10 | UART Out | sample streaming on/off |
| 11 | Language | Chinese / English |
| 12 | Cursor > | rotate to open the cursor page |
| 13 | Time offset > | rotate to open the time-offset page |
| 14 | Wave offset > | rotate to open the output-offset page |
| 15 | Dev-er Info > | rotate to open the creator info page |
| 16 | Batt Voltage | read-only |

- **Long press**: save to EEPROM, show `Save Success` / `Save Failed`, then exit settings
  (long press is the **only** way to leave settings).
- **Double-click** (inside settings, including all sub-pages): **discard changes** — reload
  settings and calibration from EEPROM (the UI language is kept), show
  `已取消修改 / Changes discarded`, then return to the **settings list**. It never jumps to the
  main screen.
- **Encoder acceleration** applies only to the 4 numeric items (Brightness, LSB, PWM Freq,
  PWM Duty): 1 step slow, 2 steps ≤120 ms, 3 steps ≤50 ms.
- **Language** switches immediately and is stored in EEPROM.
- **PWM Freq**: 15 bands, `1Hz/2/5/10/20/50/100/200/500/1k/2k/5k/10k/17k/42k Hz`.
- **Wave Type**: sine / triangle / sawtooth (P1.0, through the on-board low-pass).
- **Wave freq**: 6 bands, `9/18/35/70/141/282 Hz`.

#### Cursor page

Open from settings: select “Cursor >” and rotate once more. Sampling stops while the page is open,
so the trace is frozen on the last frame.

| Action | Function |
|---|---|
| Rotate | Move the **currently selected** cursor (range 0–99, i.e. inside the 100-column chart; full redraw each step, no residue) |
| Press + rotate | Switch selection between A and B (selected one is solid, the other dashed) |
| Short press | **No effect** (ignored inside the cursor page) |
| Long press | Back to the settings list |

The bottom line shows `dT:xxx us/ms  dV:x.xx V` (replacing the voltage-range/time-base info).
`dT` = time difference, `dV` = voltage difference between the two cursors.

#### Creator info page

Open from settings: select “Dev-er Info >” and rotate once more. Shows the LOGO, original author,
developer and project address; this firmware shows the version on the project row
(`(v1.8.1)` / `PROJ:(v1.8.1)`).
Press+rotate selects an entry, rotate shows the corresponding URL (marquee for long URLs); selecting
`<Back` and rotating returns; short press does nothing, long press returns to the settings list.

#### Time-offset page

Open from settings: select “Time offset >” and rotate once more. The header shows `CAL n/25` and,
on the right, the label of the selected entry (`A1` / `B1` / `A2` / `B2` / `THR` for #21~#25);
5 rows are visible (`#nn  value`, selected row inverted).

| Action | Function |
|---|---|
| Press + rotate | Choose the entry (0–25) |
| Rotate | Adjust the value (slow ±1, fast ±8) |
| Short press | **No effect** |
| Long press | **Write EEPROM immediately (save message)** and go back to the settings list |

- #0~#20: the 21 per-range sample delays `CalTable`;
- #21~#25: delay-model coefficients A1 / B1 / A2 / B2 / THR
  (defaults 12955/1800/14258/1550/300).
- The model coefficients only affect the next model-generated default DtTbl; a calibrated DtTbl is
  not rebuilt automatically.

#### Output-offset page

Open from settings: select “Wave offset >” and rotate once more. It calibrates both output
waveforms. The header shows `OUT n/25` on the left and the **group marker of the selected entry**
at the top right:

- `#0~#14`: square-wave bands, `SQ` + frequency (`SQ1Hz` `SQ2Hz` … `SQ17kHz` `SQ42kHz`);
- `#15~#20`: wave bands, `SIN` + frequency (`SIN9Hz` `SIN18Hz` … `SIN282Hz`);
- `#21`: `TK`;
- `#22~#25`: `WS1` `WS2` `WS3` `WS4`.

Rows are unchanged: `#nn  value` (5 rows per screen, selected row inverted).

| Action | Function |
|---|---|
| Press + rotate | Select the entry (0–25) |
| Rotate | Adjust the value (slow ±1, fast ±8 for #0~#20 and WS; TK changes by ±1 per step) |
| Long press | Write EEPROM immediately (save message) and go back to the settings list |

- `#0~#14`: P1.1 square wave, 15 bands, offset unit **0.1 µs** (added to the band period)
- `#15~#20`: P1.0 sine/triangle/sawtooth, 6 bands, offset unit **0.1 µs** (added to each table-step period)
- `#21`: generator tick calibration TK (unit 0.1 µs, default 120, current 117)
- `#22~#25`: wave table-step periods WS1~WS4 (unit 0.1 µs); all 6 WS values are available via 0x23/0x24

The PC host “Wave offset” dialog reads/writes the first 21 offsets (`0x1D` / `0x1E`);
TK and the 6 WS coefficients are read/written with `0x23` / `0x24`.

#### Signal source

1. Enable `PWM Out` (P1.1) and/or `Wave Out` (P1.0) in settings
2. Set `PWM Freq`, `PWM Duty`, `Wave Type`, `Wave freq`
3. When disabled, the pin is driven to 0 V

The two outputs go to the two on-board test loops:

| Loop | From | Signal | Adjust |
|---|---|---|---|
| `PWM` | P1.1 | square wave (1 Hz–42 kHz, duty 1–99 %) | RP2 (500R) amplitude |
| `SIN` | P1.0 | sine / triangle / sawtooth (6 bands 9–282 Hz) | RP1 (200K) amplitude |

> The on-board SIN network is an RP1 + L1 (1 mH) + C3 (22 nF) low-pass, so the wave frequency can
> only go up to a few hundred Hz. RP1 also sets the amplitude (its position affects the filter
> cutoff too; tune for the largest clean waveform).

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
   (`v1.8.1`) appears in the status bar
4. Parameter changes on the right panel are applied immediately
5. “Save to EEPROM” writes them to the device; “Read” fetches them back
6. “One-click calibrate” measures all 21 time bases and writes the calibration table
7. **Pause also pauses the MCU** (0x1C) while the GUI keeps refreshing; a horizontal
   **scroll slider** under the waveform then scrolls the device (bidirectional sync)

Waveform view: mouse wheel = zoom, Ctrl+wheel = vertical, drag = pan.
Measurements: Vpp/Vmax/Vmin/Vrms/Vavg/frequency/period/duty/rise time.
Cursors: Shift+click to place, drag to move, double-click to reset (Δt/ΔV),
or press the “Cursor” button to drop both at once.
Also: FFT view, pause, CSV/PNG export, full UI language switch, output-offset dialog
(21 offsets, 0x1D/0x1E), sound-card time-base calibration (needs `sounddevice numpy`).

### Build

SDCC 4.6.0 required:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

`--stack-auto` is mandatory (only 128 B of directly addressable IRAM).
Current usage (v1.8.1): ROM 47,105 / 64,512 B (73%), XRAM 4,399 / 8,192 B, stack 217 B.

Regenerate the Chinese font after edits: `python py\gen_cnfont.py` (writes the GBK-encoded
`include/cnfont.h`; do not hand-edit it).

### Flash

- STC-ISP: chip STC8A8K64D4, IRC 45 MHz, `build/wusi_minidso.hex`, power-cycle to download
- `python -m stcgal -P stc8d -p COM5 -o program_eeprom_split=64512 build\wusi_minidso.hex`
- `python py\flash.py COM5 build\wusi_minidso.hex` — sends `0x14` so the firmware jumps to ISP itself,
  passes `program_eeprom_split=64512`, then restores CalTable + DtTbl via `restore_all.py`

Flashing erases the whole EEPROM (settings and calibration table).
**EEPROM user area = 1 KB**: the default `program_eeprom_split=65024` leaves only 0.5 KB;
this project uses **`program_eeprom_split=64512`** (65536 − 64512 = 1024 B = 2 × 512 B sectors).
The current data layout occupies the first 512 B sector (263 B); the second sector is unused.

### Protocol

```
A5 5A TYPE LENH LENL PAYLOAD[LEN] SUM
SUM = (TYPE + LENH + LENL + ΣPAYLOAD) & 0xFF
```

| TYPE | Direction | Meaning |
|---|---|---|
| 0x01 | DSO→PC | sample frame (28 B header + 100×uint16 raw ADC) |
| 0x02 | DSO→PC | ACK: `[0]=0 ok / 1 fail`, `[1]=extra status` |
| 0x03 | DSO→PC | settings block (22 B) |
| 0x10 | PC→DSO | set settings (22 B, applied immediately) |
| 0x11 | PC→DSO | save to EEPROM |
| 0x12 | PC→DSO | get settings (replies 0x03) |
| 0x13 | PC→DSO | soft reset to user code (EEPROM kept; boot-save check) |
| 0x14 | PC→DSO | soft reset to ISP (for automatic flashing) |
| 0x15 | PC→DSO | set P1.1 test-square divider (2×uint8; `0` restores normal output, auto-restore after 60 s) |
| 0x16 / 0x17 | PC↔DSO | write / read calibration table (21×uint16, 42 B) |
| 0x18 | PC→DSO | read 16 bytes at raw IAP address (diagnostics, `[0..1]=address`) |
| 0x19 | DSO→PC | firmware info: `[0..2]=major/minor/patch` (`1,8,1` for this release), `[3]=settings length (22)`, `[4]=sample header length (28)`, `[5]=capability byte`, `[6]=default tick (120)` |
| 0x1A | DSO→PC | scroll position: `[0]offset(int8) [1]TriPos [2]running [3]max offset` |
| 0x1B | PC→DSO | set scroll position: `[0]=offset(int8)` |
| 0x1C | PC→DSO | run/pause: `[0]=1 run / 0 pause` |
| 0x1D / 0x1E | PC→DSO | read / write output offset table (21×int16, EEPROM 82..123) |
| 0x1F / 0x20 | PC→DSO | read / write delay-model coefficients A1,B1,A2,B2,THR (5×uint16) |
| 0x21 / 0x22 | PC→DSO | read / write DtTbl (21×uint32, unit 0.01 µs, EEPROM 176..259) |
| 0x23 / 0x24 | PC→DSO | read / write generator coefficients TK + 6×WS (14 B = 1+6 uint16) |
| 0x30 | PC→DSO | IAP/EEPROM diagnostic command (development only; not used by the PC host) |

Settings block (22 B): `Lsb(u16) PlotMode ScaleH ScaleV_Auto RulerVMax(u16) RulerVMin(u16)
TriLevel(u16) TriMode TriSlope WaveFreqIdx Brightness OutPWM OutSIN OutUART
GenFreqIdx GenDuty WaveType Lang`

> DtTbl is the table used by the frequency readout and the time axis. After flashing/erase it is
> invalid and the firmware rebuilds it from the delay model; write the measured table with
> `py/restore_all.py` (built-in values, or `build/dtcal.json`) or via 0x21 / 0x22.

### Directory layout

```
mini-dso/
├─ src/            firmware sources
├─ include/        headers (cnfont.h Chinese font, bmp.h logo, keys.h …)
├─ user/main.c     main program + interrupts + main loop
├─ py/             PC host and tools (dso_gui.py / flash.py / restore_all.py / gen_cnfont.py)
├─ build/          wusi_minidso.hex (build output; plus .map / .mem / .lk)
├─ build.ps1       one-click build
└─ README.md
```

### Known issues

- The time-base is calibrated against the device itself; absolute accuracy may still be off by a few percent
- The fastest 80 µs/div band is only available in auto trigger mode (single/normal trigger can't finish the calculations in time)
- Fast bands #15~#20 are limited by ADC conversion overhead (100 µs/div ≈ 8.9 µs/point,
  150 µs/div ≈ 6.6 µs/point); frequency readout is corrected by DtTbl, but **screen time-base labels
  still differ from the real time axis**
- Frequency readout uses the trigger-edge crossing estimator (period averaging as initial/fallback);
  integer sample positions and level quantization still leave a small residual
- Square/wave frequencies derive from the calibrated TK and per-band offsets (EEPROM) and are approximate;
  TK defaults to 120 (12.0 µs/tick), currently calibrated to 117
- BGV measured ≈1185 mV; falls back to 1200 mV when the ROM calibration word is invalid
- IRAM is full — put new globals in `__xdata`
- C sources are **GBK** encoded; `README.md` is UTF-8
- Inside settings a double-click discards changes and returns to the settings list (never to the
  main screen); the main screen ignores double-click; long press is the only way to leave settings
- Waveform scrolling is paused-only (running always adjusts parameters)
- The old global `WaveScroll` mode is disabled (forced to 0 when reading settings, kept for compatibility)
- Watchdog intentionally disabled (a slow sweep of ≈4.7 s looks like a hang)
- Resuming from pause keeps the old trace until the new sweep finishes (≈4.7 s at 500 ms/div)

### License

MIT, as the original project.
