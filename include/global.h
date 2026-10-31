/* All global variables defined here*/
#ifndef GLOBAL_H
#define GLOBAL_H


#include "STC8A8K64S4A12.H" // cpv


#define SAMPLE_NUM 220      //采样缓存点数，显示波形需101个点，查找触发点从第51个点到第SAMPLE_NUM-50个点，
#define PRE_BUF_NUM 62      //单次触发和普通触发的预缓存点数大于等于52
#define AFT_BUF_NUM 158     //单次触发和普通触发的触发后缓存点数等于SAMPLE_NUM-PRE_BUF_NUM

extern __xdata uint16 VBat;
extern __xdata uint16 Lsb;
extern __xdata int16 TriLevel;
extern __xdata uint8 TriPos;
extern __xdata int8 TriPosOffset;
extern __xdata uint8 WaveLength;
extern __xdata uint32 WaveFreq;
extern __xdata int16 RulerVMin, RulerVMax;
extern __xdata uint16 VMax, VMin;
//cpv extern uint16 *BGV;
extern __xdata uint16 ADCbg;
extern __xdata uint16 TriggerADC;
extern __xdata uint16 WaveLengthSumNum;
extern __xdata uint32 WaveLengthSum;
extern __xdata int8 ScaleH_tmp;
extern __xdata uint8 OLED_Brightness;
extern bit OLED_BrightnessChanged;
extern bit EC11PressAndRotate;
extern bit DisplayUpdate;
extern bit ClearDisplay;
extern bit ClearWave;
extern bit ADCRunning;
extern bit ADCInterrupt;
extern bit UpdateVbat;
extern bit TriFail;
extern bit PlotMode;
extern bit OptionChanged;
extern bit TriSlope;
extern bit InSettings;
extern bit WaveScroll;
extern bit WaveUpdate;
extern bit ScaleV_Auto;
extern bit ADCComplete;
extern bit OutPWM;   //cpv - OUTPUT PWM 开关
extern bit OutSIN;   //cpv - OUTPUT SIN 开关
extern bit OutUART;  //cpv - Output UART 开关
extern bit SettingsDirty;
extern __xdata uint16 TestDiv;
extern __xdata uint16 TestTimeout;
extern bit ShowOriUrl;
extern bit ShowDevUrl;
extern bit ShowProjUrl;
extern __xdata uint8 MarqueeOffset;
extern __xdata uint16 SettingTicks;
extern __xdata volatile uint16 CalTable[21];
extern __xdata uint8 GenFreqIdx;      // 方波频率档位
extern __xdata uint8 GenDuty;         // 方波占空比 %
extern __xdata uint8 WaveType;
extern __xdata uint8 Lang;
extern bit InfoPage;
extern bit CursorPage;
extern bit CalPage;
extern bit ShowSaveMsg;    /* 设置页: 显示保存成功 */
extern bit ShowCancelMsg;  /* 设置页: 显示已取消修改 */
extern uint8 CancelExit;   /* 0=无 1=回设置列表 2=回主界面 */      /* calibration table page */
extern uint8 CalSel;     /* current cal index 0..20 */
/* ---- 新增(CPV 优化) ---- */
extern __xdata uint8 CurA, CurB;      /* 光标 A/B 位置(0..159) */
extern bit CurSel;            /* 0=选中 A, 1=选中 B */
extern bit EepromValid;       /* EEPROM 校验通过 */
extern bit PostEepromOk, PostCalOk, PostBgvOk;   /* 开机自检结果 */
#define GEN_TICK_US10 120   /* 信号源 1 tick = 12.0us (实测) */

#define FW_VER_MAJOR 1
#define FW_VER_MINOR 5
#define FW_VER_PATCH 0
#define FW_VERSION ((FW_VER_MAJOR << 8) | (FW_VER_MINOR << 4) | FW_VER_PATCH)

extern __xdata uint8 InfoSel;   /* 信息页选中项: 0作者 1开发 2返回 */   /* 1: 正在显示创作者信息页 */        // P1.0 波形类型: 0正弦 1三角 2锯齿
extern __xdata uint16 GenPeriod;      // 方波周期(Timer1 tick)
extern __xdata uint16 GenHigh;        // 方波高电平 tick
extern __xdata uint8 GenPre;          // 方波预分频
   //cpv - P1.1 测试方波分频(0=正常9.01kHz输出，校时基用) //cpv - 示波器端参数被修改，需要通知上位机
extern __xdata int8 OptionInSettings;
extern __xdata int8 OptionInChart;
extern __xdata int8 ScaleH;
extern __xdata int8 TriMode;
extern __xdata uint16 ADCbuf[SAMPLE_NUM];
//cpv replaced extern uint8 code *PlotModeTxt[];
//cpv not used extern uint8 code *TriModeTxt[];
//cpv replaced by function extern uint8 code *ScaleHTxt[];
#endif