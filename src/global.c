#include "global.h"

__xdata uint16 Lsb;                                                //输入采样端分压系数x100 / Input voltage dividing coefficient x 100
__xdata uint16 VBat;                                               //电池电压 / Voltage of battery
__xdata uint8 WaveLength;                                          //波长 / Wave length
__xdata uint32 WaveFreq;                                           //波频率 / Wave frequency
__xdata int16 TriLevel;                                            //用户设定触发值，mV / Trigger Level in mV
__xdata uint8 TriPos;                                              //触发位置 / Trigger Position
__xdata int8 TriPosOffset;                                         //触发位置偏移量 / Trigger Position Offset
__xdata int16 RulerVMin, RulerVMax;                                //纵轴电压最大最小值 / Min and Max voltage on vertical ruler
__xdata uint16 VMax, VMin;                                         //屏幕波形的最大和最小电压mV，上限65535mV
//cpv uint16 *BGV;                                               //内部BG参考电压
__xdata uint16 ADCbg;                                              //内部BG参考ADC
__xdata uint16 TriggerADC;                                         //触发值ADC
__xdata uint16 WaveLengthSumNum;                                   //平均波形长度求和次数
__xdata uint32 WaveLengthSum;                                      //平局波形长度求和
__xdata int8 ScaleH_tmp;                                           //临时记录采样完成的时间区间
__xdata uint8 OLED_Brightness;                                     //OLED亮度1-254
bit OLED_BrightnessChanged;                                //OLED修改标志位
bit DisplayUpdate;                                         //更新屏幕信息标志位
bit EC11PressAndRotate;                                    //EC11编码器按下同时旋转标志位
bit ClearDisplay;                                          //清空屏幕标志位
bit ClearWave;                                             //清空波形标志位
bit ADCRunning;                                            //ADC采样标志位
bit ADCInterrupt;                                          //ADC采样中断标志位
bit UpdateVbat;                                            //更新电池电压信息标志位
bit OptionChanged;                                         //设置被修改标志位
bit InSettings;                                            //进入设置界面标志位
bit PlotMode;                                              //绘图模式 0:Vect 1:Dots
bit TriSlope;                                              //触发方向，1：上升触发，0：下降触发
bit TriFail;                                               //触发失败标志位
bit WaveScroll;                                            //波形滚动标志位
bit WaveUpdate;                                            //更新波形标志位
bit ScaleV_Auto;                                           //自动量程标志位
bit ADCComplete;                                           //ADC完成采样，为单次采样服务
bit OutPWM;                                                //cpv - OUTPUT PWM (P1.1 方波) 开关
bit OutSIN;                                                //cpv - OUTPUT SIN (P1.0 正弦) 开关
bit OutUART;                                               //cpv - Output UART (串口上传) 开关
bit SettingsDirty;
__xdata uint16 TestDiv = 0;
__xdata uint16 TestTimeout = 0;
bit ShowOriUrl = 0;       //cpv - 设置页 ORI 行显示 github 链接(轮播, 不存EEPROM)
bit ShowDevUrl = 0;
bit ShowProjUrl = 0;   /* 信息页: 显示项目地址 */       //cpv - 设置页 DEV 行显示 wstek.win(轮播)
__xdata uint8 MarqueeOffset = 0;  //cpv - 轮播偏移
__xdata uint16 SettingTicks = 0;
__xdata volatile uint16 CalTable[21];
__xdata uint8 GenFreqIdx = 0;   /* 默认 1Hz? 上电由 Read_Options 覆盖 */
__xdata uint8 GenDuty = 50;
__xdata uint8 WaveType = 0;
__xdata uint8 Lang = 0;   /* 0=English 1=中文 */
bit InfoPage = 0;
bit CursorPage = 0;
__xdata uint8 CurA = 40, CurB = 110;
bit CalPage = 0;
bit ShowSaveMsg = 0;
bit ShowCancelMsg = 0;
uint8 CalSel = 0;
bit CurSel = 0;
bit EepromValid = 0;
bit PostEepromOk = 0, PostCalOk = 0, PostBgvOk = 0;
__xdata uint8 InfoSel = 0;
__xdata uint16 GenPeriod = 4;
__xdata uint16 GenHigh = 2;
__xdata uint8 GenPre = 1;
 /* 时基校准表: 0-14 为 DelayUs 的 us 值, 15-19 为 0.25us 单位 */  //cpv - 250us 计数(设置页轮播用)   //cpv - 测试方波模式超时计数(10s 后自动恢复正常输出)                                          //cpv - 参数被修改(通知上位机)
__xdata int8 ScaleH = 4;                                           //时间区间，0-20对应500ms-70us
__xdata int8 OptionInSettings;                                     //设置界面的选项序号, 0:TriS, 1:PlotMode, 2:LSB
__xdata int8 OptionInChart;                                        //主界面的选项序号, 0:ScaleH, 1:ScaleV, 2:TriLevel, 3:TriSlope, 4:TriMode
__xdata int8 TriMode;                                              //触发方式，2:单次 1：普通，0：自动
                                                           //自动模式:连续采样，用户手动停止
                                                           //普通：触发后停止采样，并自动等待下次触发
                                                           //单次：触发后停止采样，用户手动开始等待下次触发
__xdata uint16 ADCbuf[SAMPLE_NUM];                                 //缓存原始采样数据
//cpv replaced uint8 code *PlotModeTxt[] = {"Vect", "Dots"};              //绘图模式文字
//cpv not used uint8 code *TriModeTxt[] = {"Auto  ", "Normal", "Single"}; //触发方式文字
/*cpv replaced by function 
__xdata uint8 code *ScaleHTxt[] =                                  //水平标尺文字
    {
        "500ms", //0
        "200ms", //1
        "100ms", //2
        "50ms",  //3
        "20ms",  //4
        "10ms",  //5
        "5ms",   //6
        "2ms",   //7
        "1ms",   //8
        "500us", //9
        "200us", //10
        "100us"  //11
};*/
