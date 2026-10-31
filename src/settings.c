/*
    settings.c

    Settings Control and Parameter Adjusting

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

*/

#include "settings.h"
#include "keys.h"

/* waveform frequency divider: ISR 72.1kHz / div / 64 points -> 8.8/17.6/35/70/141/282 Hz */
static const uint8 code WaveDivTab[6] = {128, 64, 32, 16, 8, 4};
/* nominal table-step period (0.1us) for 8.8/17.6/35/70/141/282 Hz (64 points) */
static const uint16 code WaveStepNom[6] = {17760, 8880, 4440, 2220, 1110, 555};

void WaveFreq_Update(void)
{
    uint8 i;
    uint32 q;

    if (WaveFreqIdx > 5)
        WaveFreqIdx = 2;
    WaveDiv = WaveDivTab[WaveFreqIdx];

    /* per-step period (0.1us) plus calibration offset -> Q8 ticks */
    for (i = 0; i < 6; i++)
    {
        uint16 nom = WaveStepNom[i];
        int16 off = OutOff[15 + i];
        int16 tot;

        if (off > 3000)
            off = 3000;
        if (off < -3000)
            off = -3000;
        tot = (int16)nom + off;
        if (tot < 100)
            tot = 100;
        q = ((uint32)tot * 256UL) / GEN_TICK_US10;
        WaveStepQ[i] = (uint16)q;
    }
}


    //单片机速度限制，单次和普通触发的中间计算造成单片机无法完成70us区间计算
    //MCU speed limitation result in the Single Sweep and Normal Sweep calculations could not complete in 70us time interval.
void Check_MinTimeInterval()
{
    if (TriMode)
    {
        if (ScaleH > SCALE_H_MAX - 1)
            ScaleH = SCALE_H_MAX - 1;
    }
    else
    {
        if (ScaleH > SCALE_H_MAX)
            ScaleH = SCALE_H_MAX;
    }
}

/* cpv - 根据 Output PWM / Output SIN 开关设置输出状态
   关闭时把对应引脚明确拉到 0V（而不是悬空或继续输出）
   P1.1: 方波输出;  P1.0: PCA 8 位 PWM(正弦) */
void Output_Update(void)
{
    /* P1.1 方波 */
    if (!OutPWM)
        PWM1_OUT = 0;

    /* P1.0 正弦 */
    if (OutSIN)
    {
        CCAPM0 = 0x00;   /* wave out is software PWM on P1.0 */ /* PCA 8 位 PWM 模式, CEX0 由 PCA 驱动 */
    }
    else
    {
        CCAPM0 = 0x00; /* 关闭 PCA PWM, P1.0 变回普通 IO */
        P10 = 0;       /* 明确拉低到 0V */
    }
}
void change_ScaleH(bit i)
{
    if (i)
    {
        ScaleH++;
        Check_MinTimeInterval();
    }
    else
    {
        ScaleH--;

        if (ScaleH < SCALE_H_MIN)
            ScaleH = SCALE_H_MIN;
    }
}

void change_TriggerValue(bit i)
{
    if (i)
    {
        if (TriLevel >= 5000)
            TriLevel += 500;
        else
            TriLevel += 100;

        if (TriLevel > MAX_V)
            TriLevel = MAX_V;
    }
    else
    {
        if (TriLevel <= 5000)
            TriLevel -= 100;
        else
            TriLevel -= 500;

        if (TriLevel < MIN_V)
            TriLevel = MIN_V;
    }
}

void change_LSB(bit i)
{
    if (i)
    {
        Lsb++;

        if (Lsb > LSB_MAX)
            Lsb = LSB_MAX;
    }
    else
    {
        Lsb--;

        if (Lsb < LSB_MIN)
            Lsb = LSB_MIN;
    }
}

void change_PlotMode()
{
    // cpv PlotMode = ~PlotMode;
    PlotMode = !PlotMode; // cpv
}

void change_TriMode(bit i)
{
    if (i)
    {
        TriMode++;

        if (TriMode > 2)
            TriMode = 0;
    }
    else
    {
        TriMode--;

        if (TriMode < 0)
            TriMode = 2;
    }
}

void change_TriPosOffset(bit i)
{
    if (i)
    {
        TriPosOffset--;
        if (TriPosOffset + TriPos < ((CHART_H_MAX - CHART_H_MIN) >> 1))
            TriPosOffset = ((CHART_H_MAX - CHART_H_MIN) >> 1) - TriPos;
    }
    else
    {
        TriPosOffset++;
        if (TriPosOffset + TriPos > SAMPLE_NUM - ((CHART_H_MAX - CHART_H_MIN) >> 1) - 1)
            TriPosOffset = SAMPLE_NUM - ((CHART_H_MAX - CHART_H_MIN) >> 1) - 1 - TriPos;
    }
}

void change_OptionInChart(bit i)
{
    int8 maxopt = ADCRunning ? 4 : 5;   /* 暂停时多一个"滚动位置" */

    if (i)
    {
        OptionInChart++;
        if (OptionInChart > maxopt)
            OptionInChart = 0;
    }
    else
    {
        OptionInChart--;
        if (OptionInChart < 0)
            OptionInChart = maxopt;
    }
    ClearDisplay = 1;      /* 整屏重绘: 不让上一个选中光标留下残影 */
    DisplayUpdate = 1;
}

void change_OptionInSettings(bit i)
{
    if (i)
    {
        OptionInSettings++;
        if (OptionInSettings > 15)
            OptionInSettings = 0;
    }
    else
    {
        OptionInSettings--;
        if (OptionInSettings < 0)
            OptionInSettings = 15;
    }
}

void change_RulerVMax(bit i)
{
    if (i)
    {
        if (RulerVMax <= 1000)
        {
            RulerVMax -= 100;
            //RulerVMin += 100;
        }
        else
        {
            RulerVMax -= 500;
            //RulerVMin += 500;
        }

        if (RulerVMax <= RulerVMin)
            ScaleV_Auto = 1;
    }
    else
    {
        ScaleV_Auto = 0;
        if (RulerVMax >= 1000)
        {
            RulerVMax += 500;
            //RulerVMin -= 500;
        }
        else
        {
            RulerVMax += 100;
            //RulerVMin -= 100;
        }

        if (RulerVMax > MAX_V)
            RulerVMax = MAX_V;

        // if (RulerVMin < MIN_V)
        //     RulerVMin = MIN_V;
    }
}

void change_RulerV(bit i)
{
    ScaleV_Auto = 0;
    if (i)
    {
        RulerVMax -= 100;
        RulerVMin -= 100;
        if (RulerVMin < MIN_V + 100)
        {
            RulerVMax += 100;
            RulerVMin = MIN_V;
        }
    }
    else
    {
        RulerVMax += 100;
        RulerVMin += 100;
        if (RulerVMax > MAX_V)
        {
            RulerVMax = MAX_V;
            RulerVMin -= 100;
        }
    }
}

void change_OLED_Brightness(bit i)
{
    if (i)
    {
        OLED_Brightness++;
        if (OLED_Brightness > BRIGHTNESS_MAX)
            OLED_Brightness = BRIGHTNESS_MAX;
    }
    else
    {
        OLED_Brightness--;
        if (OLED_Brightness < BRIGHTNESS_MIN)
            OLED_Brightness = BRIGHTNESS_MIN;
    }
    OLED_BrightnessChanged = 1;
}

static uint16 CalLastMs = 0;

void Change_Val(bit i)
{
    /* ---------------- 输出波偏移表页 ---------------- */
    if (OutCalPage)
    {
        if (EC11PressAndRotate)
        {
            if (i)
            {
                if (++OutCalSel > 20)
                    OutCalSel = 0;
            }
            else
            {
                if (OutCalSel == 0)
                    OutCalSel = 20;
                else
                    OutCalSel--;
            }
        }
        else
        {
            uint8 step = 1;
            if ((uint16)(AppMs - CalLastMs) <= 60)
                step = 8;
            CalLastMs = AppMs;
            if (i)
            {
                if (OutOff[OutCalSel] < 30000)
                    OutOff[OutCalSel] += step;
            }
            else
            {
                if (OutOff[OutCalSel] > -30000)
                    OutOff[OutCalSel] -= step;
            }
            OptionChanged = 1;
            WaveFreq_Update();
            SetGenParams();
        }
        ClearDisplay = 1;
        DisplayUpdate = 1;
        return;
    }

    /* ---------------- 时基偏移表页 ---------------- */
    if (CalPage)
    {
        if (EC11PressAndRotate)
        {
            if (i)
            {
                if (++CalSel > 20)
                    CalSel = 0;
            }
            else
            {
                if (CalSel == 0)
                    CalSel = 20;
                else
                    CalSel--;
            }
        }
        else
        {
            uint16 step = 1;
            if ((uint16)(AppMs - CalLastMs) <= 60)
                step = 8;
            CalLastMs = AppMs;
            if (i)
            {
                if (CalTable[CalSel] < 65000)
                    CalTable[CalSel] += step;
            }
            else
            {
                if (CalTable[CalSel] >= step)
                    CalTable[CalSel] -= step;
                else
                    CalTable[CalSel] = 0;
            }
            OptionChanged = 1;
        }
        ClearDisplay = 1;
        DisplayUpdate = 1;
        return;
    }

    /* ---------------- 光标测量页 ---------------- */
    if (CursorPage)
    {
        if (EC11PressAndRotate)
            CurSel = !CurSel;           /* 长按旋转: 切换 A/B */
        else if (i)
        {
            if (CurSel) { if (CurB < (CHART_H_MAX - CHART_H_MIN - 1)) CurB++; }
            else        { if (CurA < (CHART_H_MAX - CHART_H_MIN - 1)) CurA++; }
        }
        else
        {
            if (CurSel) { if (CurB > 0) CurB--; }
            else        { if (CurA > 0) CurA--; }
        }
        ClearDisplay = 1;          /* 整屏重绘, 光标移动不留残影 */
        DisplayUpdate = 1;
        return;
    }

    /* ---------------- 创作者信息页 ---------------- */
    if (InfoPage)
    {
        if (EC11PressAndRotate)
        {
            /* 长按旋转: 选择 原作 / 开发 / 项目地址 / 返回 */
            if (i)
            {
                if (++InfoSel > 3)
                    InfoSel = 0;
            }
            else
            {
                if (InfoSel == 0)
                    InfoSel = 3;
                else
                    InfoSel--;
            }
        }
        else
        {
            /* 直接旋转: 前三项切换地址显示; 返回 -> 退出 */
            if (InfoSel == 0)
                ShowOriUrl = !ShowOriUrl;
            else if (InfoSel == 1)
                ShowDevUrl = !ShowDevUrl;
            else if (InfoSel == 2)
                ShowProjUrl = !ShowProjUrl;
            else
            {
                InfoPage = 0;
                ClearDisplay = 1;
            }
        }
        MarqueeOffset = 0;
        DisplayUpdate = 1;
        return;
    }

    /* 按下同时旋转编码器
       Rotating Encoder while pressing */
    if (EC11PressAndRotate)
    {
        //设置界面
        //In settings
        if (InSettings)
        {
            change_OptionInSettings(i);
        }

        //波形滚动模式
        //In waveform scroll mode
        else if (WaveScroll)
        {
            change_RulerV(i);
            WaveUpdate = 1; //置位波形更新标志
        }

        //非波形滚动模式
        //Not in waveform scroll mode
        else
        {
            change_OptionInChart(i);
            //切换选项时，不清空波形
            //Not to clear waveform when switch options
            ClearWave = 0;
        }
    }

    /* 在设置界面旋转编码器
       Rotating Encoder in settings */
    else if (InSettings)
    {
        /* 0: 打印模式  1: 亮度  2: LSB */
        if (OptionInSettings == 0)
            change_PlotMode();
        else if (OptionInSettings == 1)
            change_OLED_Brightness(i);
        else if (OptionInSettings == 2)
            change_LSB(i);

        /* 3: 方波输出开关 */
        else if (OptionInSettings == 3)
        {
            OutPWM = !OutPWM;
            Output_Update();
        }
        /* 4: 方波频率档位 */
        else if (OptionInSettings == 4)
        {
            if (i)
            {
                if (++GenFreqIdx > 14)
                    GenFreqIdx = 0;
            }
            else
            {
                if (GenFreqIdx == 0)
                    GenFreqIdx = 14;
                else
                    GenFreqIdx--;
            }
            SetGenParams();
        }
        /* 5: 方波占空比 1~99% */
        else if (OptionInSettings == 5)
        {
            if (i)
            {
                if (GenDuty < 99)
                    GenDuty++;
            }
            else
            {
                if (GenDuty > 1)
                    GenDuty--;
            }
            SetGenParams();
        }
        /* 6: 波形输出开关 */
        else if (OptionInSettings == 6)
        {
            OutSIN = !OutSIN;
            Output_Update();
        }
        /* 7: 波形类型 */
        else if (OptionInSettings == 7)
        {
            if (i)
            {
                if (++WaveType > 2)
                    WaveType = 0;
            }
            else
            {
                if (WaveType == 0)
                    WaveType = 2;
                else
                    WaveType--;
            }
        }
        /* 8: 串口输出开关 */
        else if (OptionInSettings == 9)
        {
            OutUART = !OutUART;
        }
        /* 9: 语言(中文/英文) */
        else if (OptionInSettings == 10)
        {
            Lang = !Lang;
            ClearDisplay = 1;
        }
        /* 10: 光标测量 -> 选中后再旋转进入光标页 */
        else if (OptionInSettings == 11)
        {
            CursorPage = 1;
            CurA = 30;             /* 图表宽 100 列, 默认一左一右偏中 */
            CurB = 70;
            CurSel = 0;
            ClearDisplay = 1;
            ADCInterrupt = 1;
            return;
        }
        /* 11: 创作者信息 -> 选中后再旋转进入信息页 */
        else if (OptionInSettings == 14)
        {
            InfoPage = 1;
            InfoSel = 0;
            MarqueeOffset = 0;
            ClearDisplay = 1;
            return;
        }
        /* 12: 校准表 -> 选中后再旋转进入 */
        /* 13: output offset table */
        else if (OptionInSettings == 13)
        {
            OutCalPage = 1;
            OutCalSel = 0;
            ClearDisplay = 1;
            return;
        }
        else if (OptionInSettings == 12)
        {
            CalPage = 1;
            CalSel = 0;
            ClearDisplay = 1;
            return;
        }
        /* 13: 波形频率 (正弦/三角/锯齿): 6 档 */
        else if (OptionInSettings == 8)
        {
            if (i)
            {
                if (++WaveFreqIdx > 5)
                    WaveFreqIdx = 0;
            }
            else
            {
                if (WaveFreqIdx == 0)
                    WaveFreqIdx = 5;
                else
                    WaveFreqIdx--;
            }
            WaveDiv = WaveDivTab[WaveFreqIdx];
            WaveType = WaveType;      /* no-op, keep */
            DisplayUpdate = 1;
        }
        /* 14: 电池电压 -> 无操作 */
        else if (OptionInSettings == 15)
        {
            DisplayUpdate = 1;
            return;
        }


        /* 置位设置保存标志
           Options need to be saved */
        OptionChanged = 1;
        SettingsDirty = 1; //cpv - 通知上位机重新读取
    }

    /* 滚动波形模式下旋转编码器
       Rotate Encoder in waveform horizontal scroll mode */
    else if (WaveScroll)
    {
        change_TriPosOffset(i);
        WaveUpdate = 1; 
    }

    /* 在主界面旋转编码器
       Rotate Encoder in Main interface */
    else
    {
        /* 滚动位置: 左右滚动波形(仅暂停时可选, 方向与旧滚动模式相反) */
        if (OptionInChart == 5)
        {
            change_TriPosOffset(!i);
            WaveUpdate = 1;
            DisplayUpdate = 1;
        }
        /* 调节时间区间
           Adjust time scale */
        else if (OptionInChart == 0)
        {
            change_ScaleH(i);
            WaveUpdate = 1;
            ClearWave = 1;
            WaveLengthSumNum = 0; 
            WaveLengthSum = 0;   
        }

        /* 调节量程
           Adjust measuring range */
        else if (OptionInChart == 1)
        {
            change_RulerVMax(i);
            WaveUpdate = 1;
            ClearWave = 0;
        }

        /* 调节触发值
           Adjust Trigger level */
        else if (OptionInChart == 2)
        {
            change_TriggerValue(i);
            WaveUpdate = 0;
            ClearWave = 0;
        }

        /* 调节触发方向
           Adjust Trigger Slope */
        else if (OptionInChart == 3)
        {
            // cpv TriSlope = ~TriSlope;
            TriSlope = !TriSlope; // cpv
            WaveUpdate = 0;
            ClearWave = 0;
        }

        /* 更改触发方式
           Switch Trigger Mode */
        if (OptionInChart == 4)
        {
            change_TriMode(i);
            Check_MinTimeInterval(); //检查时间区间的合法性
            WaveUpdate = 1;
            ClearWave = 1;
            WaveLengthSumNum = 0; 
            WaveLengthSum = 0;   
        }

        /* 置位设置保存标志
           Options need to be saved */
        OptionChanged = 1;
        SettingsDirty = 1; //cpv - 通知上位机重新读取
    }
}

void check_Options()
{
    if (Lsb > LSB_MAX || Lsb < LSB_MIN)
        Lsb = 600;

    if (ScaleH > SCALE_H_MAX || ScaleH < SCALE_H_MIN)
        ScaleH = 0;

    if (RulerVMax > MAX_V || RulerVMax < MIN_V)
        RulerVMax = 0;

    if (RulerVMin > MAX_V || RulerVMin < MIN_V)
        RulerVMin = 0;

    if (RulerVMax <= RulerVMin)
    {
        RulerVMax = RulerVMin;
        ScaleV_Auto = 1;
    }

    if (TriLevel > MAX_V || TriLevel < MIN_V)
        TriLevel = 2000;

    if (TriMode > 2 || TriMode < 0)
        TriMode = 0;

    if (OLED_Brightness > BRIGHTNESS_MAX || OLED_Brightness < BRIGHTNESS_MIN)
        OLED_Brightness = 10;

    // cpv - unchecked bit values, added for completeness' sake
    // cpv PlotMode
    // cpv ScaleV_Auto
    // cpv WaveScroll

    /* 信号源参数合法性 */
    if (GenFreqIdx > 14)
        GenFreqIdx = 9;   /* 默认 1kHz */
    if (GenDuty < 1 || GenDuty > 99)
        GenDuty = 50;
    if (WaveType > 2)
        WaveType = 0;
    if (Lang > 1)
        Lang = 0;
    SetGenParams();

    Check_MinTimeInterval();
}

/* EEPROM 一个扇区 512 字节, 擦除是整扇区, 所以设置和校准表必须一起写
   布局: [0..17] 设置  [18..31] 0xFF  [32..33] 'C','L'  [34..75] 校准表(21x16bit LE)  [76] 校验和 */
static __xdata uint8 EeBuf[128];

/* 参数无效(新片/擦除后)时载入的默认值: 两个波形输出都关 */
static void Load_Defaults(void)
{
    Lsb = 600;
    PlotMode = 1;
    ScaleH = 15;              /* 500us/div */
    ScaleV_Auto = 1;
    RulerVMax = 3000;
    RulerVMin = 0;
    TriLevel = 1500;
    TriMode = 0;
    TriSlope = 1;
    WaveScroll = 0;
    OLED_Brightness = 10;
    OutPWM = 1;               /* 方波输出: 默认开 */
    OutSIN = 1;               /* 波形输出: 默认开 */
    OutUART = 1;
    GenFreqIdx = 9;
    GenDuty = 50;
    WaveType = 0;
    WaveFreqIdx = 2;
    Lang = 1;
}

bit Save_Options()
{
    uint8 *p;
    uint8 i, sum;

    check_Options();
    p = EeBuf;
    *p++ = Lsb >> 8;
    *p++ = Lsb;
    *p++ = PlotMode;
    *p++ = ScaleH;
    *p++ = ScaleV_Auto;
    *p++ = RulerVMax >> 8;
    *p++ = RulerVMax;
    *p++ = RulerVMin >> 8;
    *p++ = RulerVMin;
    *p++ = TriLevel >> 8;
    *p++ = TriLevel;
    *p++ = TriMode;
    *p++ = TriSlope;
    *p++ = WaveFreqIdx;
    *p++ = OLED_Brightness;
    *p++ = OutPWM;
    *p++ = OutSIN;
    *p++ = OutUART;
    *p++ = GenFreqIdx;
    *p++ = GenDuty;
    *p++ = WaveType;
    *p = Lang;

    for (i = 21; i < 32; i++)
        EeBuf[i] = 0xFF;
    EeBuf[32] = 'C';
    EeBuf[33] = 'L';
    sum = 0;
    for (i = 0; i < 21; i++)
    {
        EeBuf[34 + i * 2] = (uint8)(CalTable[i] & 0xFF);
        EeBuf[35 + i * 2] = (uint8)(CalTable[i] >> 8);
    }
    for (i = 0; i < 42; i++)
        sum += EeBuf[34 + i];
    EeBuf[76] = sum;

    /* 参数块校验: 'M','S' + 22 字节和 */
    sum = 0;
    for (i = 0; i < 22; i++)
        sum += EeBuf[i];
    EeBuf[77] = 'M';
    EeBuf[78] = 'S';
    EeBuf[79] = sum;

    /* output offset table: 82..123, magic 'O','C', checksum */
    for (i = 0; i < 21; i++)
    {
        EeBuf[82 + i * 2] = (uint8)(OutOff[i] & 0xFF);
        EeBuf[83 + i * 2] = (uint8)((uint16)OutOff[i] >> 8);
    }
    EeBuf[124] = 'O';
    EeBuf[125] = 'C';
    sum = 0;
    for (i = 82; i < 124; i++)
        sum += EeBuf[i];
    EeBuf[126] = sum;

    return EEPROM_Save(EeBuf, 127);
}

void Read_Options()
{
    uint8 *p;
    uint8 i, sum, ok;

    EEPROM_Read(EeBuf, 127);

    /* 参数块校验: 擦除后全 0xFF 不能当成有效参数(否则输出全被打开) */
    sum = 0;
    for (i = 0; i < 22; i++)
        sum += EeBuf[i];
    if (EeBuf[77] != 'M' || EeBuf[78] != 'S' || EeBuf[79] != sum)
    {
        Load_Defaults();
        EepromValid = 0;
        WaveScroll = 0;
        check_Options();
        return;
    }

    p = EeBuf;
    Lsb = *p++;
    Lsb <<= 8;
    Lsb |= *p++;
    PlotMode = *p++;
    ScaleH = *p++;
    ScaleV_Auto = *p++;
    RulerVMax = *p++;
    RulerVMax <<= 8;
    RulerVMax |= *p++;
    RulerVMin = *p++;
    RulerVMin <<= 8;
    RulerVMin |= *p++;
    TriLevel = *p++;
    TriLevel <<= 8;
    TriLevel |= *p++;
    TriMode = *p++;
    TriSlope = *p++;
    WaveFreqIdx = *p++;
    WaveScroll = 0;
    OLED_Brightness = *p++;
    OutPWM = *p++;
    OutSIN = *p++;
    OutUART = *p++;
    GenFreqIdx = *p++;
    GenDuty = *p++;
    WaveType = *p++;
    Lang = *p ? 1 : 0;

    /* 校准表: 校验通过才覆盖默认值 */
    /* output offsets: valid magic+checksum, otherwise zero (nominal) */
    sum = 0;
    for (i = 82; i < 124; i++)
        sum += EeBuf[i];
    if (EeBuf[124] == 'O' && EeBuf[125] == 'C' && EeBuf[126] == sum)
    {
        for (i = 0; i < 21; i++)
            OutOff[i] = (int16)(((uint16)EeBuf[82 + i * 2]) | ((uint16)EeBuf[83 + i * 2] << 8));
    }
    else
    {
        for (i = 0; i < 21; i++)
            OutOff[i] = 0;
    }
    WaveFreq_Update();

    ok = (EeBuf[32] == 'C' && EeBuf[33] == 'L');
    if (ok)
    {
        sum = 0;
        for (i = 0; i < 42; i++)
            sum += EeBuf[34 + i];
        if (sum != EeBuf[76])
            ok = 0;
    }
    if (ok)
    {
        for (i = 0; i < 21; i++)
            CalTable[i] = ((uint16)EeBuf[34 + i * 2 + 1] << 8) | EeBuf[34 + i * 2];
    }

    WaveScroll = 0;   /* 旧滚动模式已停用(改用暂停+光标指滚动条) */
    if (WaveFreqIdx > 5)
        WaveFreqIdx = 2;
    WaveDiv = WaveDivTab[WaveFreqIdx];
    EepromValid = ok;   /* cpv - 供开机自检 */

    check_Options(); /* 检查选项合法性 */
}

/* 根据 GenFreqIdx / GenDuty 计算方波参数(Timer1 tick 13.87us) */
void SetGenParams(void)
{
    /* 目标周期(单位 0.1us): 1Hz 2 5 10 20 50 100 200 500 1k 2k 5k 10k 18k 42k */
    static const uint32 code GenPeriodUs10[15] = {
        10000000UL, 5000000UL, 2000000UL, 1000000UL, 500000UL,
        200000UL, 100000UL, 50000UL, 20000UL, 10000UL,
        5000UL, 2000UL, 1000UL, 555UL, 238UL
    };
    uint32 p10, tick;
    uint8 pre, k;

    if (GenFreqIdx > 14)
        GenFreqIdx = 0;
    if (GenDuty < 1)
        GenDuty = 1;
    if (GenDuty > 99)
        GenDuty = 99;

    {
        uint32 nom = GenPeriodUs10[GenFreqIdx];
        int16 off = OutOff[GenFreqIdx];
        long tot;

        if (off > 30000)
            off = 30000;
        if (off < -30000)
            off = -30000;
        tot = (long)nom + (long)off;
        if (tot < 100)
            tot = 100;
        p10 = (uint32)tot;
    }
    tick = GEN_TICK_US10;        /* 1 tick = GEN_TICK_US10/10 us */
    pre = 1;
    while ((p10 / (tick * pre)) > 60000UL && pre < 128)
        pre <<= 1;

    GenPre = pre;
    GenPeriod = (uint16)(p10 / (tick * pre));
    if (GenPeriod < 2)
        GenPeriod = 2;

    k = (uint8)(((uint32)GenPeriod * GenDuty) / 100UL);
    if (k < 1)
        k = 1;
    if (k >= GenPeriod)
        k = GenPeriod - 1;
    GenHigh = k;
}


/* cpv - 旋钮加速: 当前上下文是否数值类选项 */
bit Setting_IsNumeric(void)
{
    /* 只有"纯数字"的 4 项才允许旋钮加速:
       1 亮度  2 分压系数  4 方波频率  5 占空比
       其余(设置项其它 + 主界面全部)都保持 1 格 1 步 */
    if (!InSettings || CursorPage || InfoPage || EC11PressAndRotate)
        return 0;

    return (OptionInSettings == 1 || OptionInSettings == 2 ||
            OptionInSettings == 4 || OptionInSettings == 5) ? 1 : 0;
}
