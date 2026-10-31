# Mini-DSO v1.2 — STC8A8K64D4 @ 45 MHz 移植与增强版

把 [CreativeLau/Mini-DSO](https://github.com/CreativeLau/Mini-DSO) v0.3 移植到
**56dz.com 的 STC8A8K64D4 核心板**（45 MHz 内部 IRC），并在原版基础上加了
中英双语界面、可调信号源、串口数据流 + 电脑上位机、EEPROM 时基校准、双光标测量等功能。

- 原作者：Creative Lau（硬件设计 / 原始固件）
- 45 MHz 移植与增强：WuSi & DeepSeek

---

## 1. 硬件

| 项目 | 说明 |
|---|---|
| MCU | STC8A8K64D4，内部 IRC **45 MHz**（1T） |
| 显示 | SSD1306 128×64 OLED，**SPI** 接法（GND VCC D0 D1 RES DC CS） |
| 输入 | ADC CH0 = **P0.1**，ADC CH1 = **P1.4** |
| 方波输出 | **P1.1**（推挽，频率 / 占空比可调） |
| 波形输出 | **P1.0**（PCA 8-bit PWM + 外部 RC 低通，正弦/三角/锯齿） |
| 旋钮 | EC11 编码器（Timer0 250 µs 正交采样，4 跳变/步） |
| 串口 | P3.0 RXD / P3.1 TXD，**115200 8N1** |
| 指示灯 | P2.6 |
| 存储 | 内部 EEPROM 512 B（设置 + 时基校准表） |

> 自测小技巧：把 P1.1 接到输入分压端，就能用示波器测自己的方波输出。

---

## 2. 固件功能

### 采样与显示
- **21 档时基**：500 ms/div … 80 µs/div（每档单独实测校准）
- 触发：自动 / 正常 / 单次，上升沿 / 下降沿，触发电平可调
- 垂直：自动量程 + 手动量程，分压系数 LSB 可调（默认 600）
- 绘图：矢量 / 点阵两种模式
- 测量：频率、最大/最小电压、电池电压
- 暂停：短按即停，画面冻结在按下瞬间

### 按键（EC11）

| 操作 | 行为 |
|---|---|
| 短按（≥10 ms 防抖） | 主界面：**Run ⇄ Stop** 立即切换（已去掉双击） |
| 按住 **≥500 ms** 不动 | 进入 / 退出设置 |
| 按住 + 旋转 | 只调当前参数，**不会**跳设置 |
| 旋转 | 主界面调速/量程/触发；设置页选项间移动 |
| 滚动波形模式 | 已不在按键里，改由上位机参数设置 |

### 设置页（13 项，长按进入）

中文 12×12 点阵、一屏 5 行；英文一屏 8 行。进入/退出都会整屏重绘。

```
绘图模式   亮度      分压系数
方波输出   方波频率   占空比
波形输出   波形类型   串口输出
语言       光标测量 >
创作者信息 >  电池电压
```

- **旋钮加速**：只有 4 个纯数值项（亮度 / 分压系数 / 方波频率 / 占空比）才加速：
  慢转 1 步、≤120 ms 2 步、≤50 ms 3 步；其余项目全部 1 格 1 步
- **语言**：中文 ⇄ English 即时切换，存 EEPROM
- **光标测量**：选中后再旋转进入光标页
- **创作者信息**：选中后再旋转进入版权页

### 光标测量页

- 两条竖直光标（选中的实线、另一个虚线），限制在图表 100 列内
- **长按旋转**切换 A/B，**直接旋转**左右移动；移动时整屏重绘，不留残影
- **最底一行**显示 `dT:xxx us/ms` 和 `dV:x.xx V`（取代原来的电压范围/时基信息）
- 长按或短按返回设置

### 创作者信息页

- Mini-DSO LOGO + 原作 / 开发 / 项目地址（可选中，旋转显示网址，超长自动轮播）
- 底部 `<Back`，旋转即返回；长按直接退回设置

### 信号源
- **方波（P1.1）**：15 档频率（约 1 Hz ~ 42 kHz）+ 占空比 1~99 %
- **波形（P1.0）**：正弦 / 三角 / 锯齿，经外部 RC 得到模拟波形
- 两个输出独立开关，关闭时引脚拉低到 0 V
- 周期由单一常量 `GEN_TICK_US10`（120 = 12.0 µs/tick）实时算出，无写死的经验表

### 其它
- 开机启动页：Mini-DSO LOGO + `C.L./W.S.&D.S`，底部自检行 `EEP:OK CAL:OK x.xxV`
- 设置 / 校准表存 EEPROM；保存时显示 `保存成功 / 保存失败`
- **不启用看门狗**：500 ms/档 一轮采样要 4.4 s，触发等待等状态软件无法与卡死区分，
  启用会误复位，因此保持关闭（真卡死断电重启即可）

---

## 3. 编译

需要 **SDCC 4.6.0**（`sdcc` / `sdar` / `sdranlib` 在 PATH 里）。

**推荐用仓库脚本**：

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

它会编译 `src/*.c` + `user/main.c`、打包库、链接，输出 `build/minidso_uart.hex`。

> ⚠️ **必须带 `--stack-auto`**：8051 直接寻址 RAM 只有 128 B，不加这个参数会报
> `Could not get ... consecutive bytes in internal RAM for area DSEG`。

手工等价命令：

```bat
set FLAGS=-mmcs51 --model-large --opt-code-size --std-c23 --stack-auto
for %f in (src\*.c) do sdcc %FLAGS% -Iinclude -c %f
sdcc %FLAGS% -Iinclude -c user\main.c
sdar -rcs minidso.lib *.rel
sdranlib minidso.lib
sdcc %FLAGS% --iram-size 256 --xram-size 8192 --code-size 64512 --out-fmt-ihx main.rel minidso.lib -o build\minidso_uart.hex
```

当前固件占用（v1.2.0）：

| 资源 | 已用 / 总量 |
|---|---|
| ROM | 36,738 / 64,512 B（约 57 %） |
| XRAM | 3,551 / 8,192 B |
| 栈 | 218 B（链接器按静态调用深度算出） |
| IRAM | 直接寻址 RAM 已满，新增全局变量请放 `__xdata` |

### 中文字模

`include/cnfont.h` 是**自动生成**的（12×12 字模 + 中文串表）。加字方法：
编辑 `py/gen_cnfont.py` 的 `STRINGS`，然后

```bat
python py\gen_cnfont.py
```

---

## 4. 烧录

### STC-ISP（图形界面）
1. 芯片型号 **STC8A8K64D4**，IRC 选 **45 MHz**
2. 打开 `build/minidso_uart.hex`
3. 点"下载/编程"后给板子**断电再上电**

### 命令行
```bat
python -m stcgal -P stc8d -p COM5 build/minidso_uart.hex
```
同样需要冷启动（stcgal 会提示 `Waiting for MCU, please cycle power`）。

### 运行中自动烧录
```bat
python py\flash.py COM5 build\minidso_uart.hex
```
`py/flash.py` 先发 `0x14` 让固件软复位进 ISP，再调 stcgal，无需手动拔电。

> ⚠️ 烧录会整片擦除 EEPROM：设置和校准表回到默认值（默认值已校准，可直接用）。

---

## 5. 上位机（Python GUI）

`py/dso_gui.py` — Tkinter 实时示波器界面：

- 实时波形（矢量/点阵）、FFT 频谱
- **测量**：Vpp / Vmax / Vmin / Vrms / Vavg / 频率 / 周期 / 占空比 / 上升时间
- **光标**：Shift+左键放置、拖动、双击复位，显示 Δt / ΔV
- 滚轮缩放、拖动平移、时基滑块、纵向缩放
- 参数面板：时基/量程/触发/绘图模式/LSB/亮度/方波输出/波形输出/串口输出/语言等
- **保存到 EEPROM**（固件真正写 EEPROM）
- **一键时基校准**：读校准表 → 测 21 档实际间隔 → 写回
- 保存波形 CSV / 截图 PNG、暂停/继续、中英文界面、`--demo`、`--selftest`

### 安装 / 运行
```bat
pip install pyserial pillow
python py\dso_gui.py                 :: 连真机
python py\dso_gui.py --demo          :: 无硬件演示
python py\dso_gui.py --selftest      :: 协议自检
```
串口 115200 8N1；示波器设置里 `串口输出` 必须 ON（默认 ON）。

### 开发工具
| 文件 | 作用 |
|---|---|
| `py/gen_cnfont.py` | 生成 `include/cnfont.h` |
| `py/test_tb.py` | 自动测量 21 档时基误差 |
| `py/flash.py` | 通过串口让 DSO 进 ISP 并自动烧录 |

---

## 6. 串口协议

```
A5 5A TYPE LENH LENL PAYLOAD[LEN] SUM
SUM = (TYPE + LENH + LENL + ΣPAYLOAD) & 0xFF
```

| TYPE | 方向 | 含义 |
|---|---|---|
| `0x01` | DSO→PC | 采样帧：28 字节头 + N×uint16 原始 ADC（小端） |
| `0x02` | DSO→PC | 应答：[0] 结果（0 成功 / 1 失败） |
| `0x03` | DSO→PC | 参数块（22 字节） |
| `0x10` | PC→DSO | 下发参数（立即生效，不写 EEPROM） |
| `0x11` | PC→DSO | 保存参数到 EEPROM |
| `0x12` | PC→DSO | 读取参数 |
| `0x14` | PC→DSO | 软复位进 ISP（烧录用） |
| `0x15` | PC→DSO | 输出测试方波（分频值） |
| `0x16` | PC→DSO | 写时基校准表（21×uint16） |
| `0x17` | PC→DSO | 读时基校准表 |
| `0x19` | DSO→PC | 固件信息：版本 / 参数块长度 / 帧头长度 / 能力位 / tick |

**采样帧头（28 B）**

```
flags(u8) ScaleH(u8) PlotMode(u8) TriMode(u8) TriSlope(u8) N(u8)
VMax(u16) VMin(u16) WaveFreq(u32)
RulerVMin(u16) RulerVMax(u16) PlotADCMin(u16) PlotADCMax(u16)
BGV(u16) ADCbg(u16) LSB(u16)
```
`flags`：bit0 运行中、bit1 触发失败、bit2 自动量程

**参数块（22 B，与 EEPROM 顺序一致）**

```
Lsb(u16) PlotMode(u8) ScaleH(u8) ScaleV_Auto(u8)
RulerVMax(u16) RulerVMin(u16) TriLevel(u16)
TriMode(u8) TriSlope(u8) WaveScroll(u8) Brightness(u8)
OutPWM(u8) OutSIN(u8) OutUART(u8)
GenFreqIdx(u8) GenDuty(u8) WaveType(u8) Lang(u8)
```

---

## 7. 目录结构

```
mini-dso/
├─ src/            固件源码（adc / chart / delay / eeprom / global / keys / settings / ssd1306 / uart）
├─ include/        头文件（cnfont.h 中文字模、bmp.h LOGO、keys.h …）
├─ user/main.c     主程序、中断、主循环
├─ build/
│  ├─ minidso.hex          原版 hex（勿改）
│  └─ minidso_uart.hex     当前固件 v1.2.0
├─ py/             上位机与开发工具
├─ build.ps1       一键编译
└─ README.md
```

---

## 8. 已知事项

- **时基**：21 档延时表按实测校准（`src/adc_stc8.c` 的 `DefaultDelayTable`），
  EEPROM 里另存一份可软件校准的 `CalTable`；绝对时间与外部基准可能有几个百分点偏差。
- **方波频率**：由 `GEN_TICK_US10 = 120`（12.0 µs/tick）推算，标称频率是近似值。
- **电池电压**：芯片 BGV 实测 1185 mV，代码失效回退 1200 mV。
- **RAM 紧张**：IRAM 已满、XRAM 用掉约 43 %、栈 218 B；新增全局变量请放 `__xdata`。
- **烧录会擦 EEPROM**（设置 + 校准表）。
- 所有 C 源文件为 **GBK** 编码，用 UTF-8 编辑器打开中文注释会乱码。
- `include/cnfont.h` 是生成文件，改 `py/gen_cnfont.py` 后重新生成，不要手改。
- 双击功能已移除（与"短按 Run/Stop"冲突）。

---

## 9. 许可

原始项目采用 MIT License（见 `src/` 各文件头部版权声明）。
本移植与增强部分同样以 MIT 发布，欢迎自由使用 / 修改。
