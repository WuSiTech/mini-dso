/*
    Mini DSO with STC MCU

    GitHub: https://github.com/CreativeLau/Mini-DSO
    
    Copyright (c) 2020 Creative Lau (creativelaulab@gmail.com)

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

     
    Version: V0.3
    MCU Type: STC8A8K64D4 @45MHz
    YouTube Tutorial(First Version): https://youtu.be/c6gBv6Jcz7w
    YouTube Tutorial(V0.3): https://youtu.be/-8PadlS7c4c
    Instructable(First Version): https://www.instructables.com/id/Make-Your-Own-OscilloscopeMini-DSO-With-STC-MCU-Ea/
    Instructable(V0.3): 
    Any question please contact CreativeLauLab@gmail.com
    YouTube Channel: https://www.youtube.com/c/CreativeLau

    Note:
    How to Operation:
        Main Interface - Parameter Mode:
            Single Click Encoder: Run/Stop sampling
            Double Click Encoder: Enter Wave Scroll Mode
            Long Press Encoder: Enter Settings Interface
            Rotate Encoder: Adjust parameters
            Rotate Encoder While Pressing: Switch between options
            
        Main Interface - Wave Scroll Mode: 
            Single Click Encoder: Run/Stop sampling
            Double Click Encoder: Enter Parameter Mode
            Long Press Encoder: Enter Settings Interface
            Rotate Encoder: Scroll waveform horizontally (only available when sampling stopped)
            Rotate Encoder While Pressing: Scroll waveform vertically (only available when sampling stopped)
            
        Settings Interface:
            Single Click Encoder: N/A
            Double Click Encoder: N/A
            Long Press Encoder: Return to Main Interface
            Rotate Encoder: Adjust parameters
            Rotate Encoder While Pressing: Switch between options

    Parameters in Main Interface:
        Seconds Per Division: "500ms", "300ms", "200ms", "150ms", "100ms", "50ms","30ms", "20ms", "15ms", "10ms", "5ms", "3ms", "2ms", "1.5ms", "1ms", "500us", "300us", "200us", "150us", "100us", "70us"(70us only available in Auto Trigger Mode)
        Voltage Range: Maximum voltage is 30V. Rotate Encoder clockwise continuous to enter auto range. Rotate Encoder anticlockwise to enter manual range. 
        Trigger Level: Set trigger voltage level. The trigger position will be put at the center of chart. 
                       You should set a correct Trigger Level in Single and Normal Trigger Mode in order to capture the waveform.
        Trigger Slope: Trigger on Rising or Falling Edge. 
                       You should set a correct Trigger Slop in Single and Normal Trigger Mode in order to capture the waveform.
        Trigger Mode:
            Auto:   Sweep continuous, indicator always on. Single click the encoder to stop or run sampling. 
                    If triggered, the waveform will be shown on the display and the trigger position will be put at the center of chart. 
                    Otherwise, the waveform will scroll irregular, and 'Fail' will be shown on the display.
            Normal: When complete pre-sampling, you can input signal. If triggered, waveform shown on the display and waiting for new trigger. 
                    If no new trigger, the waveform will be kept.
            Single: When complete pre-sampling, you can input signal. If triggered, waveform shown on display and stop sampling. 
                    User need to single click Encoder to start next sampling.
            For Normal Mode and Single Mode, be sure the trigger level has been adjusted correctly, otherwise no waveform will be shown on the display.

    Status in Main Interface:
        'Run': Sampling Running.
        'Stop': Sampling Stopped.
        'Fail': The Trigger Level beyond the waveform in Auto Trigger Mode.
        'Auto': Auto Voltage Range.
                    
    Parameters in Settings Interface:
        PMode(Plot Mode): Show waveform in Vector or Dots.
        LSB(Sampling Coefficient): 100 times of voltage dividing coefficient. e.g. the resistor for voltage dividing is 10k and 2k, calculate the voltage dividing coefficient (10+2)/2=6. Get the LSB=6x100=600.
        BRT(Brightness): Adjust OLED Brightness

    Saving Settings: When exit settings interface, all parameters in settings and main interface will be saved in EEPROM.

    Indicator:
    Generally, the indicator on means the sampling is running. 
    The more important use is in Single and Normal Trigger Mode, before get into the trigger stage, pre-sampling is required. 
    The indicator will not on during pre-sampling stage. We should not input signal until the indicator comes on. 
    The longer time scale selected, the longer waiting time of pre-sampling.

    2020-04-30 Update
    1. Add Single Sweep and Normal Sweep function. Set trigger value to catch the waveform mutation.
    2. According to datasheet, set ADC port to high-impedance.

    2020-05-3 Update
    1. Show frequency of waveform.
    2. Scroll waveform horizontally/vertically with EC11 Encoder.
    3. Zoom waveform vertically with EC11 Encoder.
    4. The trigger level could be customized.

    简易示波器
    版本：V0.3
    作者：老刘爱捣鼓
    单片机型：STC8A8K64D4 @45MHz
    任何问题请联系CreativeLauLab@gmail.com
    老刘爱捣鼓（全网同名）期待您的关注！
    B站教程（初版）：https://www.bilibili.com/video/BV1ai4y1t79R
    B站教程（V0.3）：https://www.bilibili.com/video/BV1ai4y1t79R
    油管频道: https://www.youtube.com/c/CreativeLau

    操作说明：
        主界面-选项设置模式：
            单击编码器：切换开始/暂停采样
            双击编码器：切换波形水平滚动模式/选项设置模式
            长按编码器：进入设置界面
            旋转编码器：修改当前参数
            按下同时旋转编码器：在参数间切换
            
        主界面-波形水平滚动模式：
            单击编码器：切换开始/暂停采样
            双击编码器：切换波形水平滚动模式/选项设置模式
            长按编码器：进入设置界面
            旋转编码器：水平滚动波形（在暂停采样状态下有效）
            按下同时旋转编码器：垂直滚动波形（仅在暂停采样状态下有效）
            
        设置界面：
            单击编码器：无效
            双击编码器：无效
            长按编码器：返回主界面
            旋转编码器：修改当前选项
            按下同时旋转编码器：切换选项

    主界面参数：
        横轴时间区间："500ms", "300ms", "200ms", "150ms", "100ms", "50ms","30ms", "20ms", "15ms", "10ms", "5ms", "3ms", "2ms", "1.5ms", "1ms", "500us", "300us", "200us", "150us", "100us", "70us"(70us仅在自动触发模式下可用)
        纵轴电压区间：设定电压量程上限，最大30V，顺时针旋转编码器将电压上限设置为0则进入自动量程，逆时针旋转进入手动量程
        触发值：设定触发电压值，触发位置被放在屏幕中心
        触发方向：上下箭头，分别代表上升沿触发和下降沿触发
        触发方式：
            Auto(自动触发)  ：连续采样，指示灯始终点亮，通过单击编码器控制启停；触发成功时，触发点位于屏幕中心，触发失败则波形无规律滚动，屏幕左侧显示Fail标志
            Normal(普通触发)：等待预采样，待指示灯亮起表示预采样结束，这时可以输入信号；
                              触发成功后，显示波形，并继续等待下次触发；
                              如果有新的触发成功，则自动显示新的波形，如没有新的触发成功则屏幕波形保持并一直等待下次触发；
                              需注意设置正确的触发值，否则一直处于等待触发状态，屏幕不会显示波形
            Single(单次触发)：等待预采样，待指示灯亮起表示预采样结束，这时可以输入信号；
                              触发成功后，显示波形，并停止采样，需用户单击编码器开始下次采样	
                              需注意设置正确的触发值，否则一直处于等待触发状态，屏幕不会显示波形
            
    主界面状态显示：	
        Run：正在采样
        Stop：停止采样
        Fail：自动模式下，触发值超出波形范围引起触发失败
        Auto：自动量程
            
    设置界面选项：
        PMode(绘图模式)：
            Vector：波形以矢量显示
            Dots  ：波形以点阵显示
        LSB(采样系数)：分压系数的100倍，比如用10k加2k的电阻进行分压，分压系数为(10+2/2)=6，LSB理论取值为6x100=600，根据实际电阻精度进行微调	
        BRT：OLED亮度

    保存设置：长按编码器退出设置界面时，设置界面和主界面的所有参数被保存到EEPROM

    2020-04-30更新
    1. 增加单次触发和普通触发功能，可自定义触发点用来捕捉波形变化
    2. 按照规格书要求将ADC采样端口设置为高阻输入
    2020-5-3更新
    1. 增加波形频率显示
    2. 使用编码器水平/垂直滚动波形
    3. 使用编码器垂直缩放波形
    4. 用户可设定触发电平
*/

//cpv #include <reg51.h>
#include "STC8A8K64S4A12.H" // cpv
#include "global.h"
#include "keys.h"
#include "delay.h"
#include "adc_stc8.h"
#include "config_stc.h"
#include "settings.h"
#include "chart.h"
#include "ssd1306.h"
#include "uart.h" // cpv

// #include "uart.h"
// #include "stdio.h"

#define VBAT_UPDATE_FREQ 4000 //电池电压更新频率: 4000 * 250us = 1s
#define VBAT_LSB 600        //电池电压采样分压系数*100
#define INT_0 0             //外部中断0序号，编码器旋转
#define INT_1 2             //外部中断1序号，编码器按下
#define TIMER_0 1           //定时器0中断序号
#define TIMER_1 3  /* cpv - Timer1 interrupt vector */
void PWM_Init(void); // cpv
//cpv unsigned char __sdcc_external_startup(void)
//cpv {
//cpv 	return 1;
//cpv }

void init()
{
    InSettings = 0;         //初始化开机界面
    OptionInSettings = 0;   //初始化设置界面的选项编号
    OptionInChart = 0;      //初始化主界面的选项标号
    WaveScroll = 0;         //清零波形滚动标志
    OptionChanged = 0;      //清零设置修改标志
    ADCRunning = 1;         //置位采样标志
    ADCInterrupt = 0;       //清零ADC中断标志
    ADCComplete = 0;        //清零ADC完成标志
    WaveUpdate = 0;         //清零波形更新标志
    ClearWave = 0;          //清零清除波形标志
    ClearDisplay = 1;       //置位清空屏幕标志
    EC11PressAndRotate = 0; //清零编码器旋转标志
    UpdateVbat = 0;         //清零采样电池电压标志
    ADCComplete = 0;        //清零ADC完成采样标志
    WaveFreq = 0;           //清零波形频率
    TriPos = 50;            //初始化触发点位置
    TriPosOffset = 0;       //初始化触发点偏移量
    TriFail = 0;            //清零触发失败标志
    VMax = 0;               //清零波形电压最大值
    VMin = 0;               //清零波形电压最小值
    WaveLengthSumNum = 0;   //清零波形长度求和次数
    WaveLengthSum = 0;      //清零波形长度求和

    /* 波形滚动模式下正在采样则禁用外部中断0（编码器旋转）
       Disable external interrupt 0(Encoder rotation) in waveform scroll mode when sampling*/
#pragma save /* cpv */
#pragma disable_warning 126 /* cpv - unreachable code */
#pragma disable_warning 110 /* cpv - conditional flow changed by optimizer: so said EVELYN the modified DOG */
	// cpv - unreachable code: ADCRunning=1 and WaveScroll=0 (see above)
    if (ADCRunning && WaveScroll)
        EX0 = 0;
#pragma restore /* cpv */

    /* 获取内部参考电压值
       Get internal reference voltage */
    //cpv BGV = GetBGV();
}

void runWhenInSettrings()
{
    ClearDisplay = 1;
    while (InSettings)
    {
        Key_Poll();          /* 设置界面里按键动作要靠这里执行(长按退出等) */

        UART_Poll(); // cpv - 设置界面也处理串口命令
        if (SettingsDirty)
        {
            SettingsDirty = 0;
            UART_SendSettings(); //cpv - 编码器改了参数，主动通知上位机
        }

        /* 更新电池电压信息
           Update voltage infor of battery */
        if (UpdateVbat)
        {
            UpdateVbat = 0;
            VBat = GetVoltage(ADC_BAT, VBAT_LSB);
        }

        /* 更新屏幕亮度
           Update OLED Brightness */
        if (OLED_BrightnessChanged)
        {
            OLED_BrightnessChanged = 0;
            OLED_Write_Command(0x81);
            OLED_Write_Command(OLED_Brightness * 10);
        }

        /* ORI/DEV 网址轮播: 每 250ms 移动一个字符 */
        if (ShowOriUrl || ShowDevUrl || ShowProjUrl)
        {
            static uint16 lastTick = 0;
            if ((uint16)(SettingTicks - lastTick) >= 1000)
            {
                lastTick = SettingTicks;
                MarqueeOffset++;
                DisplayUpdate = 1;
            }
        }

        /* 更新参数
           Update parameters */
        if (ShowSaveMsg || ShowCancelMsg)
        {
            uint8 st = ShowSaveMsg ? 1 : 2;
            ShowSaveMsg = 0;
            ShowCancelMsg = 0;
            PlotSaveStatus(st);
            OLED_Display();
            Delay1000ms();

            if (st == 2 && CancelExit == 2)
                InSettings = 0;      /* 在设置列表里取消 -> 直接回主界面 */
            CancelExit = 0;

            ClearDisplay = 1;
            DisplayUpdate = 1;
        }

        if (DisplayUpdate)
        {
            DisplayUpdate = 0;
            if (CursorPage)
            {
                ClearDisplay = 1;   /* 每帧整屏重画, 光标移动不留残影 */
                PlotChart();
                PlotWave();
            }
            else
                PlotSettings();
            OLED_Display();
        }
    }

    /* 保存设置
       Save Settings */
    EA = 0;
    if (OptionChanged)
    {
        OptionChanged = 0;
        ClearDisplay = 0;
        /* 保存设置并显示保存状态
           Save settings and display saving status*/
        PlotSaveStatus(Save_Options() ? 1 : 0);
        OLED_Display();
        Delay1000ms();
    }

    /* 退出settings后刷新屏幕
       Redraw display after exit settings */
    ClearDisplay = 1;
    PlotChart();
    OLED_Display();
    IE0 = 0;
    IE1 = 0;
    EA = 1;
}

/*
    ADCRuning=1
    |	WaveUpdate=1
    |	|	ClearWave=1
    |	|	ClearWave=0
    |	WaveUpdate=0
    ADCRuning=0
        DisplayUpdate=1
            WaveUpdate=1
            |	ClearWave=1
            |	ClearWave=0
            WaveUpdate=0
*/
void runWhenADCInterrupt()
{
    ADCInterrupt = 0;

    /* ADC采样运行
       ADC Sampling Running */
    if (ADCRunning)
    {
        EX0 = 0;

        if (WaveUpdate)
        {
            WaveUpdate = 0;
            ClearDisplay = 1;

            /* 清空波形缓存
               Clear waveform in buffer*/
            if (ClearWave)
            {
                ClearWave = 0;
                memset(ADCbuf, 0x00, SAMPLE_NUM * 2);
                WaveFreq = 0;
                TriFail = 0;
                VMax = 0;
                VMin = 0;
                PlotChart();
            }
            /* 显示缓存中的波形
               Display waveform in buffer*/
            else
            {
                AnalyseData();
                PlotChart();
                PlotWave();
            }
        }
        else
        {
            ClearDisplay = 0;
            PlotChart();
        }
        OLED_Display();

        /* ADCRuning和WaveScroll同时置位时，不开启外部中断0（编码器旋转）
           Not to enable external interrupt 0(Encoder Rotation) when both of ADCRunning and WaveScroll set. */
        if (!WaveScroll)
        {
            IE0 = 0;
            EX0 = 1;
        }
    }

    /* ADC采样停止
       ADC Sampling Stopped */
    else
    {
        while (!ADCRunning && !InSettings)
        {
            Key_Poll();   /* paused state: still service the key */

            UART_Poll(); // cpv - 停止状态也处理串口命令
            if (DisplayUpdate)
            {
                EX0 = 0;
                DisplayUpdate = 0;
                if (WaveUpdate)
                {
                    WaveUpdate = 0;
                    /* 分析缓存中完成采样的采样数据
                       Analyse completed sampling data in buffer */
                    AnalyseData();
                    ClearDisplay = 1;

                    /* 清空屏幕，绘制波形
                       Clear display and draw waveform */
                    if (ScaleH == ScaleH_tmp)
                    {
                        /* 采样点数有限，不支持横向缩放波形，只有时间区间与完成采样的时间区间相同才绘制波形
                           Since the sampling points limitation, scaling waveform along horizontal is not support.
                           Show waveform only when time scale is same as that when sampling completed */
                        PlotChart();
                        PlotWave();
                    }

                    /* 清空屏幕，不绘制波形
                       Clear display and no waveform */
                    else
                    {
                        WaveFreq = 0; //清零WaveFreq，绘制界面时，频率位置会显示****Hz
                        PlotChart();
                    }
                }
                /* 只更新屏幕上的参数，波形不变
                   Update parameters on display only, keep waveform */
                else
                {
                    ClearDisplay = 0;
                    PlotChart();
                }

                OLED_Display();
                UART_SendSamples(); // cpv - 上传采样数据
                IE0 = 0;
                EX0 = 1;
            }
        }
    }
}

void runWhenADCComplete()
{
    /*  ADC采样完成 - 单次触发
        ADC Sampling Complete - Single Trigger Mode */
    if (TriMode == 2)
    {
        EX0 = 0;
        ADCInterrupt = 1;
        DisplayUpdate = 0;
        WaveUpdate = 0;
        ADCRunning = 0; //清零ADC运行标志，停止采样
        AnalyseData();
        ClearDisplay = 1;
        PlotChart();
        PlotWave();
        OLED_Display();
        UART_SendSamples(); // cpv - 上传采样数据
        IE0 = 0;
        EX0 = 1;
    }

    /*  ADC采样完成 - 自动触发或普通触发
        ADC Sampling Complete - Auto or Normal Trigger Mode */
    else
    {
        //EX0 = 0;
        ClearDisplay = 1; //置位清空屏幕标志
        AnalyseData();    //分析采样数据
        PlotChart();      //绘制主界面
        PlotWave();       //绘制波形
        OLED_Display();
        UART_SendSamples(); // cpv - 上传采样数据
        //IE0 = 0;
        //EX0 = 1;
    }
}


/* 程序入口
   Program Entry */
void main()
{
    /* 将ADC端口P0.4，P0.6设置为高阻
       Set ADC port P0.4, P0.6 as high-impedance */
    //cpv P0M1 |= 0x50;
    //cpv P0M0 &= ~0x50;
    //cpv Set ADC port P0.1, P1.4 as high-impedance */
    P0M1 |= 0x02;  //cpv P0.1 = 0
    P0M0 &= ~0x02;  //cpv P0.1 = 1
    P1M1 |= 0x10;  //cpv P1.4 = 0
    P1M0 &= ~0x10;  //cpv P1.4 = 1

    /* 设置PWM输出端口P1.0、P1.1为推挽输出，增强驱动能力
       Set PWM output ports P1.0, P1.1 as push-pull output */
    P1M1 &= ~0x03;  //cpv P1.0, P1.1 = 0
    P1M0 |= 0x03;   //cpv P1.0, P1.1 = 1

    /* 设置指示灯端口P1.1为推挽输出
       Set indicator port P1.1 as push-pull output */
    //cpv P0M1 &= ~0x02;
    //cpv P0M0 |= 0x02;
    //cpv Set indicator port (i.e. LED) P2.6 as push-pull output */
    P2M1 &= ~0x40;  //cpv P2.6 = 0
    P2M0 |= 0x40;  //cpv P2.6 = 1

    /* cpv - 指示灯常亮 */
    P_Ready = 1;

    /* 设置编码器端口P3.2，P3.3，P3.4为准双向
       Set Encoder port P3.2, P3.3, P3.4 as quasi bidirectional */
    P3M1 &= ~0x1C;
    P3M0 &= ~0x1C;

    /* 设置OLED端口P2.1，P2.2，P2.3，P2.5，P4.2为推挽输出（提高驱动能力与抗干扰）
       Set OLED port P2.1, P2.2, P2.3, P2.5, P4.2 as push-pull output */
    //cpv P2M1 &= ~0xF8;
    //cpv P2M0 &= ~0xF8;
    //cpv Set OLED port P2.1, P2.2, P2.3, P2.5 & P4.2 as quasi bidirectional */
    P2M1 &= ~0x2e; //cpv P2.1, P2.2, P2.3, P2.5 = 0
    P2M0 |= 0x2e;  //cpv P2.1, P2.2, P2.3, P2.5 = 1
    P4M1 &= ~0x04; //cpv P4.2 = 0
    P4M0 |= 0x04;  //cpv P4.2 = 1

    /* 编码器旋转外部中断 
       Interrupt for rotating of Encoder */
    IT0 = 0; //cpv - 编码器已改为 Timer0 250us 轮询四相解码；INT0 仅保留清标志
    PX0 = 1; //外部中断0高优先级，可打断按键中断，用于判断按下同时旋转
    EX0 = 1; //开启外部中断0

    /* 编码器按键外部中断 
       Interrupt for clicking of Encoder */
    IT1 = 1; //外部中断1触发方式，下降沿
    PX1 = 0; //外部中断1低优先级
    EX1 = 1; //开启外部中断1

    /* 定时器0: 250us 时基，用于编码器 A/B 四相轮询采样 + 电池电压计时
       Timer 0: 250us tick for quadrature encoder polling and battery timing */
    AUXR |= 0x80; //定时器时钟1T模式
    TMOD &= 0xF0; //16 位自动重装
    TL0 = 0x0E;   //45MHz, 250us (65536-11250)
    TH0 = 0xD4;
    TF0 = 0;      //清除TF0标志
    ET0 = 1;      //允许定时器0中断
    PT0 = 1;      //高优先级: 保证按键长按/双击处理期间仍能轮询编码器
    TR0 = 1;      //常开(编码器轮询、电池计时)

    PWM_Init(); // cpv - PWM output timer
    UART_Init(); // cpv - UART1 115200 (Timer2 作波特率发生器)

    /* 开总中断
       Enable global interrupt */
    EA = 1;

    /* cpv - display test
    Read_Options();
    init();
    OLED_Init();
    OLED_SetFontWidth(6);
    //PlotChart();
	ClearDisplay = 1;
    PlotSettings();
    OLED_Display();*/

    /* cpv - timer / clock test
    P_Ready = 0;
    while (1)
    {
      Delay1000ms();
	  P_Ready = !P_Ready;
	}*/
	
    //UartInit();

    InitDelayTable(); //cpv - 先装默认时基延时表
    Read_Options();   //cpv - 再读 EEPROM(含校准表)

    /* cpv - 开机自检: EEPROM / 校准表 / BGV */
    {
        uint8 i;
        uint16 bgv;

        PostEepromOk = EepromValid;
        bgv = GetBGV_cpv();
        PostBgvOk = (bgv > 900 && bgv < 1800) ? 1 : 0;
        PostCalOk = 1;
        for (i = 0; i < 21; i++)
            if (CalTable[i] > 30000)
                PostCalOk = 0;
    }
    SetGenParams();   //cpv - 按保存的频率/占空比初始化方波发生器
    Output_Update(); //cpv - 按保存的开关状态设置输出(关闭即拉低 0V)
    init();
    OLED_Init();
    OLED_SetFontWidth(6);

    /* 启动页: LOGO + C.L./W.S.&D.S, 显示约 1 秒 */
    PlotSplash();
    OLED_Display();
    Delay1000ms();

    ClearDisplay = 1;
    PlotChart();
    OLED_Display();

    while (1)
    {
        Key_Poll();      /* 按键状态机(短按/长按/双击) */

        UART_Poll(); // cpv - 处理电脑端命令
        if (SettingsDirty)
        {
            SettingsDirty = 0;
            UART_SendSettings(); //cpv - 编码器改了参数，主动通知上位机
        }

        /* 采样波形
           Sampling*/
        GetWaveData();

        /* 进入设置界面
           Enter Settings Interface */
        if (InSettings)
        {
            runWhenInSettrings();
        }

        /* ADC采样中断
           ADC Sampling Interrupt */
        else if (ADCInterrupt)
        {
            runWhenADCInterrupt();
        }

        /* ADC采样完成
           ADC Sampling Complete */
        else
        {
            runWhenADCComplete();
        }
    }
}

/* 四相解码表: 索引 = (prev<<2)|cur, 值 = 方向(+1/-1/0)
   Quadrature decode table: index = (prev<<2)|cur, value = direction */
int8 code EC11_DirTab[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};

/* 编码器解码: 由 Timer0 每 250us 采样一次 A/B 做四相解码
   一个定位点 = 一个完整四相周期 = 4 次状态跳变
   抖动/漏采造成的反向跳变会在累加器里互相抵消，不会多走或少走 */
#define ENC_TRANS_PER_STEP 4

static uint8 EC11_Prev = 0;
static int8 EC11_Acc = 0;
static uint16 EncLastMs = 0;

void EC11_Poll(void)
{
    uint8 cur;
    int8 d;

    cur = (uint8)((EC11_A ? 2 : 0) | (EC11_B ? 1 : 0));
    if (cur == EC11_Prev)
        return;

    /* 记录"按下同时旋转"状态 */
    EC11PressAndRotate = !EC11_KEY;

    d = EC11_DirTab[(uint8)((EC11_Prev << 2) | cur)];
    EC11_Prev = cur;
    if (d == 0)
        return;

    EC11_Acc += d;
    if ((EC11_Acc >= ENC_TRANS_PER_STEP) || (EC11_Acc <= -ENC_TRANS_PER_STEP))
    {
        uint8 dir = (EC11_Acc > 0) ? 1 : 0;
        uint16 dt;
        uint8 reps = 1;

        EC11_Acc = 0;
        dt = (uint16)(AppMs - EncLastMs);
        EncLastMs = AppMs;

        /* 只有真的转出一格, 才算"按住旋转"(避免按键时 A/B 抖动误判) */
        if (EC11PressAndRotate)
            Key_NoteRotate();

        /* 旋钮加速: 只对"纯数值"项(亮度/分压/方波频率/占空比)
           慢转(>120ms/格) 1 步, 中速(<=120ms) 2 步, 快转(<=50ms) 3 步
           其它所有项(设置其它项/主界面全部)保持 1 格 1 步 */
        if (Setting_IsNumeric())
        {
            if (dt <= 50)
                reps = 3;
            else if (dt <= 120)
                reps = 2;
        }

        while (reps--)
            Change_Val(dir);

        ADCInterrupt = 1;
        DisplayUpdate = 1;
    }
}
/* 编码器旋转中断
   Interrput for Encoder Rotated */
//cpv void INT0_interrupt(void) interrupt INT_0
void INT0_interrupt(void) __interrupt (INT_0)
{
    /* 编码器旋转已改由 Timer0 轮询解码，这里只清标志 */
    IE0 = 0;
}
/* 编码器点击中断
   Interrput for Encoder Pressed */
//cpv void INT1_interrupt(void) interrupt INT_1
void INT1_interrupt(void) __interrupt (INT_1)
{
    IE1 = 0;
    Key_Isr();          /* 只记录按下时刻, 判定交给主循环 */
}

/* 为更新Vbat计时
   Timer for updating Vbat */
//cpv void TIMER0_interrupt(void) interrupt TIMER_0
void TIMER0_interrupt(void) __interrupt (TIMER_0) // cpv
{
    static uint16 n = 0;
    static uint8 msDiv = 0;

    if (++msDiv >= 4)          /* 250us x 4 = 1ms */
    {
        msDiv = 0;
        AppMs++;
        Key_Tick();            /* 按键计时(长按/双击)在中断里判定 */
    }

    SettingTicks++; /* 250us 计数, 供设置页轮播计时 */

    /* 校准方波模式保护: 60 秒没有新命令就恢复正常 9.01kHz 输出 */
    if ((SettingTicks & 3) == 0) /* 每 1ms 计一次 */
    {
        if (TestDiv)
        {
            if (++TestTimeout >= 60000)
            {
                TestTimeout = 0;
                TestDiv = 0;
            }
        }
    }

    /* 每 250us 采样一次编码器 A/B 并解码 */
    EC11_Poll();

    /* 设置界面里每 1s 更新一次电池电压 */
    if (InSettings)
    {
        if (++n >= VBAT_UPDATE_FREQ)
        {
            n = 0;
            UpdateVbat = 1;
            DisplayUpdate = 1;
        }
    }
}
/* UART1 中断入口 (向量 4)
   SDCC 的 8051 向量表只在包含 main() 的模块里生成，所以中断入口必须放这里，
   ISR 实际处理在 uart.c 的 UART_IsrBody() 里。 */
void UART_Isr(void) __interrupt (4)
{
    UART_IsrBody();
}
/* cpv - 正弦波查表: 8 点/周期, 8 位 PWM 占空比, 中心 128, 幅度 96
   Sine table: 8 entries, 8-bit PWM duty, centre 128, amplitude 96 */
/* 64 entries per cycle, 8-bit PWM duty (centre 128, amplitude 96) */
uint8 code SineTab[64] = {128, 140, 152, 164, 175, 186, 197, 207, 216, 224, 231, 237, 243, 247, 250, 251, 252, 251, 250, 247, 243, 237, 231, 224, 216, 207, 197, 186, 175, 164, 152, 140, 128, 116, 104, 92, 81, 70, 59, 49, 40, 32, 25, 19, 13, 9, 6, 5, 4, 5, 6, 9, 13, 19, 25, 32, 40, 49, 59, 70, 81, 92, 104, 116};
uint8 code TriTab[64] = {128, 132, 136, 140, 144, 148, 152, 156, 160, 164, 168, 172, 176, 180, 184, 188, 192, 196, 200, 204, 208, 212, 216, 220, 224, 228, 232, 236, 240, 244, 248, 252, 252, 248, 244, 240, 236, 232, 228, 224, 220, 216, 212, 208, 204, 200, 196, 192, 188, 184, 180, 176, 172, 168, 164, 160, 156, 152, 148, 144, 140, 136, 132, 128};
uint8 code SawTab[64] = {4, 8, 12, 16, 20, 24, 28, 32, 35, 39, 43, 47, 51, 55, 59, 63, 67, 71, 75, 79, 83, 87, 91, 95, 98, 102, 106, 110, 114, 118, 122, 126, 130, 134, 138, 142, 146, 150, 154, 158, 161, 165, 169, 173, 177, 181, 185, 189, 193, 197, 201, 205, 209, 213, 217, 221, 224, 228, 232, 236, 240, 244, 248, 252};
/* cpv - P1.0 正弦 + P1.1 方波
   P1.0 (PCA CCP0): 175.8kHz 8-bit PWM, 占空比按 8 点正弦表变化, 经板上 RC 滤波后为 9kHz 正弦
   P1.1: 9kHz 方波
   Timer1 中断 72.1kHz: 每次更新正弦占空比, 每 4 次翻转一次 P1.1 */
void PWM_Isr(void) __interrupt (TIMER_1)
{
  static __data uint8 SineIdx = 0;
  static __data uint8 PwmCnt = 0;    /* software PWM counter (0..31) */
  static __data uint8 PwmVal = 128;   /* target 8-bit level */
  static __data uint16 Acc = 0;       /* PDM accumulator */
  bit PdmBit = 0;
  static uint16 TestCnt = 0;
  static uint8 GenPreCnt = 0;
  static uint16 GenCnt = 0;

  /* 校准模式: P1.1 输出 TestDiv 分频的慢速方波(10Hz/2Hz 等) */
  if (TestDiv)
  {
    if (++TestCnt >= TestDiv)
    {
      TestCnt = 0;
      PWM1_OUT = !PWM1_OUT;
    }
    return;
  }

  /* P1.0 waveform out: 1-bit pulse-density modulation at the ISR rate
     (72.1kHz) with a 64-entry table stepped every 16 ticks (~70Hz).
     The on-board RP1 + L1 + C3 network averages the PDM stream, which is
     much smoother than a low-resolution PWM and immune to ISR jitter. */
  if (++PwmCnt >= WaveDiv)
  {
    PwmCnt = 0;
    if (WaveType == 1)
      PwmVal = TriTab[SineIdx];
    else if (WaveType == 2)
      PwmVal = SawTab[SineIdx];
    else
      PwmVal = SineTab[SineIdx];
    if (++SineIdx >= 64)
      SineIdx = 0;
  }
  Acc += PwmVal;
  if (Acc >= 256)
  {
    Acc -= 256;
    PdmBit = 1;
  }
  else
    PdmBit = 0;
  P10 = (OutSIN && PdmBit) ? 1 : 0;

  if (OutPWM)
  {
    if (++GenPreCnt >= GenPre)
    {
      GenPreCnt = 0;
      if (++GenCnt >= GenPeriod)
        GenCnt = 0;
      PWM1_OUT = (GenCnt < GenHigh) ? 1 : 0;
    }
  }
  else
    PWM1_OUT = 0;
}

// 45.000MHz: PCA 8-bit PWM 载波 175.8kHz, Timer1 中断 72.1kHz -> 正弦/方波 9.01kHz
void PWM_Init(void)
{
  /* PCA: P1.0 不受 CEX0 驱动(实测), 波形输出改用 Timer1 中断里的软 PWM */
  CMOD = 0x04;     // PCA 时钟 = SYSclk/1
  CL = 0;
  CH = 0;
  PCA_PWM0 = 0x00; // 8 位 PWM
  CCAP0H = 128;    // 初始 50% 占空比
  CCAPM0 = 0x00;   /* PCA not used for wave out (CEX0 not on P1.0) */   // ECOM0=1, PWM0=1
  CR = 1;          // 启动 PCA

  /* P1.1: Timer1 中断, 12T 模式, 72.1kHz */
  AUXR &= 0xBF; // Timer clock is 12T mode
  TMOD &= 0x0F; // Set timer work mode
  TL1 = 0xCC;   // Initial timer value (72.1kHz @45MHz)
  TH1 = 0xFF;   // Initial timer value
  TF1 = 0;      // Clear TF1 flag
  TR1 = 1;      // Timer1 start run
  ET1 = 1;      // Enable timer1 interrupt
}
