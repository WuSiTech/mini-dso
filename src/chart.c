/*
    chart.c

    Sampling Data Analyse and Plot Interface

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

    Note:
    2020-04-30更新
    1. 修正波形最大电压和最小电压值，之前显示的是所有采样点中的最大和最小值，修正后显示为屏幕范围内的最大值和最小值
    2. 触发位置从之前的固定波形中点改为用户自定义
    3. 增加计算波形频率函数
*/
#include "chart.h"
#include "cnfont.h"
#include "bmp.h"

static void DrawMarqueeRow(uint8 y, uint8 *str, uint8 offset);
static void FillRowBand(uint8 y, bit white);
void PlotCursors(void);
void PlotCalPage(void);

uint16 *pADCSampling;       /* pointer to live ADC samples */
uint16 waveBuf[SAMPLE_NUM]; /* mapped waveform data */
uint8 triPre;               /* equal points before trigger */
uint8 triAft;               /* equal points after trigger */
uint16 plotADCMax, plotADCMin;

void GetWaveData()
{
    pADCSampling = GetWaveADC(ADC_DSO, ScaleH);
}

/* 获得自动量程纵轴上下限
   Calculate voltage range for Auto Range*/
void getRulerV()
{
    //自动量程，根据采样点的最大最小值，按500mV扩大范围取整，作为垂直标尺范围mV
    if (ScaleV_Auto == 1)
    {
        if (VMax / 100 % 10 >= 5)
            RulerVMax = (VMax + 500) / 1000 * 1000;
        else
            RulerVMax = VMax / 1000 * 1000 + 500;

        if (VMin / 100 % 10 >= 5)
            RulerVMin = VMin / 1000 * 1000 + 500;
        else
            RulerVMin = VMin / 1000 * 1000;

        if (RulerVMax > MAX_V)
            RulerVMax = MAX_V;

        if (RulerVMin < MIN_V)
            RulerVMin = MIN_V;
    }
}

/* 计算波长
   Calculate wave length*/
bit getWaveLength(uint16 triLevel, bit right_or_left)
{
    int16 i;
    uint8 tri_pre = 255;
    uint8 tri_aft = 255;
    // cpv uint8 triPos_tmp;
    // cpv bit triSlope_tmp;
    uint8 triPos_tmp = 0; // cpv
    bit triSlope_tmp = 0; // cpv
    bit triFail = 1;
    /* 查找距离屏幕中心最近的触发点
       Search the trigger poiont closest to the center of chart */
    if (right_or_left) //向右查找临时触发点 / Search right side
    {
        for (i = TriPos + TriPosOffset; i < SAMPLE_NUM - 2; i++)
        {
            if (GetTriggerPos(*(ADCbuf + i), *(ADCbuf + i + 1), triLevel, 1)) //按上升沿查找 / Search on rising edge
            {
                triPos_tmp = i;
                triSlope_tmp = 1;
                triFail = 0;
                break;
            }
            else if (GetTriggerPos(*(ADCbuf + i), *(ADCbuf + i + 1), triLevel, 0)) //按下降沿查找 / Search on falling edge
            {
                triPos_tmp = i;
                triSlope_tmp = 0;
                triFail = 0;
                break;
            }
        }
    }
    else //向左查找临时触发点 / Search left side
    {
        for (i = TriPos + TriPosOffset; i > 0; i--)
        {
            if (GetTriggerPos(*(ADCbuf + i), *(ADCbuf + i + 1), triLevel, 1)) //按上升沿查找 / Search on rising edge
            {
                triPos_tmp = i;
                triSlope_tmp = 1;
                triFail = 0;
                break;
            }
            else if (GetTriggerPos(*(ADCbuf + i), *(ADCbuf + i + 1), triLevel, 0)) //按下降沿查找 / Search on falling edge
            {
                triPos_tmp = i;
                triSlope_tmp = 0;
                triFail = 0;
                break;
            }
        }
    }

    if (!triFail)
    {
        for (i = triPos_tmp; i >= 0; i--) //查询触发位置左侧的等值点 / Search equal point left side
        {
            if (triSlope_tmp) //上升触发,查找下降点 / Trigger on rising edge, search on falling edge
            {
                if (*(ADCbuf + i) >= triLevel && *(ADCbuf + i + 1) <= triLevel)
                {
                    tri_pre = i;
                    break;
                }
            }
            else //下降触发，查找上升点 / Trigger on falling edge, search on rising edge
            {
                if (*(ADCbuf + i) <= triLevel && *(ADCbuf + i + 1) >= triLevel)
                {
                    tri_pre = i;
                    break;
                }
            }
        }

        for (i = triPos_tmp; i < SAMPLE_NUM - 1; i++) //查询触发位置右侧的等值点 / Search equal point right side
        {
            if (triSlope_tmp) //上升触发,查找下降点 / Trigger on rising edge, search on falling edge
            {
                if (*(ADCbuf + i) >= triLevel && *(ADCbuf + i + 1) <= triLevel)
                {
                    tri_aft = i;
                    break;
                }
            }
            else //下降触发，查找上升点 / Trigger on falling edge, search on rising edge
            {
                if (*(ADCbuf + i) <= triLevel && *(ADCbuf + i + 1) >= triLevel)
                {
                    tri_aft = i;
                    break;
                }
            }
        }
    }
    if (tri_pre == 255 || tri_aft == 255 || (tri_pre == tri_aft))
    {
        WaveLength = 0;
        return 0;
    }
    else
    {
        WaveLength = tri_aft - tri_pre;
        return 1;
    }
}

/* 计算波形频率
   Calculate the wave frequency*/
void getWaveFreq()
{
    uint16 m_num; //求和次数
    uint8 n_num;  //求平均值右移位数

    //ADC停止采样时，每次动作都会显示波形频率，因此不求平均值
    if (!ADCRunning)
    {
        WaveLengthSumNum = 0;
        WaveLengthSum = 0;
    }

    //自动模式下为了让频率不频繁变动，取平均值，大于等于100ms区间不取平均值，一个原因是100ms波形变化慢，所以频率跳动不频繁，
    //另一方面越长的时间区间取平均值的延迟越高，影响使用体验
    else if (TriMode == 0 && ScaleH > 4)
    {
        switch (ScaleH)
        {
        case 5: //50ms
            m_num = 2;
            n_num = 1;
            break;

        case 6: //30ms
        case 7: //20ms
            m_num = 4;
            n_num = 2;
            break;

        default: //<10ms
            m_num = 8;
            n_num = 3;
            break;
        }

        WaveLengthSum += WaveLength;

        //达到求和次数后
        if (++WaveLengthSumNum >= m_num)
        {
            WaveLength = WaveLengthSum >> n_num; //求波长平均值
            WaveLengthSumNum = 0;                //清零波长求和次数
            WaveLengthSum = 0;                   //清零波长总和
        }

        //没达到求和次数，则返回，WaveFreq保持不变
        else
            return;
    }

    switch (ScaleH)
    {
    case 0: //500ms
        WaveFreq = (float)50 / WaveLength + 0.5;
        break;

    case 1: //300ms
        WaveFreq = 83 / WaveLength;
        break;

    case 2: //200ms
        WaveFreq = 125 / WaveLength;
        break;

    case 3: //150ms
        WaveFreq = 167 / WaveLength;
        break;

    case 4: //100ms
        WaveFreq = 250 / WaveLength;
        break;

    case 5: //50ms
        WaveFreq = 500 / WaveLength;
        break;

    case 6: //30ms
        WaveFreq = 833 / WaveLength;
        break;

    case 7: //20ms
        WaveFreq = 1250 / WaveLength;
        break;

    case 8: //15ms
        WaveFreq = 1667 / WaveLength;
        break;

    case 9: //10ms
        WaveFreq = 2500 / WaveLength;
        break;

    case 10: //5ms
        WaveFreq = 5000 / WaveLength;
        break;

    case 11: //3ms
        WaveFreq = 8333 / WaveLength;
        break;

    case 12: //2ms
        WaveFreq = 12500 / WaveLength;
        break;

    case 13: //1.5ms
        WaveFreq = 16667 / WaveLength;
        break;

    case 14: //1ms
        WaveFreq = 25000 / WaveLength;
        break;

    case 15: //500us
        WaveFreq = 50000 / WaveLength;
        break;

    case 16: //300us
        WaveFreq = 83333 / WaveLength;
        break;

    case 17: //200us
        WaveFreq = 125000 / WaveLength;
        break;

    case 18: //150us
        WaveFreq = 166667 / WaveLength;
        break;

    case 19: //100us
        WaveFreq = 161290 / WaveLength;
        break;

    default: //70us
        WaveFreq = 312500 / WaveLength;
        break;
    }
}

/* 将mv转换为ADC
   Convert voltage in mV to ADC*/
//cpv uint16 Convert_mv_ADC(uint16 mv, uint16 *BGV, uint16 ADCbg, uint16 lsb)
//cpv {
//cpv     uint16 ADC;
//cpv     ADC = (uint32)mv * ADCbg * 100 / (*BGV) / lsb;
//cpv     return ADC;
//cpv }
uint16 Convert_mv_ADC(uint16 mv, uint16 BGV, uint16 ADCbg, uint16 lsb)
{
    uint16 ADC;
    ADC = (uint32)mv * ADCbg * 100 / BGV / lsb;
    return ADC;
}

/* 将mv转换为ADC
   Convert ADC to voltage in mV */
//cpv uint16 c_ADC_mv(uint16 ADC, uint16 *BGV, uint16 BGADC, uint16 lsb)
//cpv {
//cpv     uint16 mv;
//cpv     mv = (uint32)ADC * *BGV * lsb / BGADC / 100;
//cpv     return mv;
//cpv }
uint16 c_ADC_mv(uint16 ADC, uint16 BGV, uint16 BGADC, uint16 lsb)
{
    uint16 mv;
    mv = (uint32)ADC * BGV * lsb / BGADC / 100;
    return mv;
}

/* 将uint16格式的mV转化为字符型V
   Convert voltage in mV to string*/
uint8 *c_mv_V(uint16 v)
{
    static uint8 s[5];

    if (v < 10000)
    {
        s[0] = v / 1000 + '0';
        s[1] = '.';
        s[2] = v / 100 % 10 + '0';
        s[3] = v / 10 % 10 + '0';
        s[4] = '\0';
    }
    else
    {
        s[0] = v / 10000 + '0';
        s[1] = v / 1000 % 10 + '0';
        s[2] = '.';
        s[3] = v / 100 % 10 + '0';
        s[4] = '\0';
    }

    return s;
}

/* 转换波形频率为字符
   Convert frequency to string */
uint8 *c_WaveFreq_Str()
{
    static uint8 s[5];
    if (WaveFreq == 0)
    {
        s[0] = '*';
        s[1] = '*';
        s[2] = '*';
        s[3] = '*';
        s[4] = '\0';
    }
    else if (WaveFreq >= 10000000)
    {
        s[0] = WaveFreq / 10000000 + '0';
        s[2] = ((WaveFreq) / 1000000) % 10 + '0';
        s[3] = 'M';
        s[4] = '\0';
    }
    else if (WaveFreq >= 1000000)
    {
        s[0] = WaveFreq / 1000000 + '0';
        s[1] = '.';
        s[2] = ((WaveFreq) / 100000) % 10 + '0';
        s[3] = 'M';
        s[4] = '\0';
    }
    else if (WaveFreq >= 100000)
    {
        s[0] = WaveFreq / 100000 + '0';
        s[1] = (WaveFreq / 10000) % 10 + '0';
        s[2] = ((WaveFreq) / 1000) % 10 + '0';
        s[3] = 'k';
        s[4] = '\0';
    }
    else if (WaveFreq >= 10000)
    {
        s[0] = WaveFreq / 10000 + '0';
        s[1] = ((WaveFreq) / 1000) % 10 + '0';
        s[2] = 'k';
        s[3] = '\0';
    }
    else if (WaveFreq >= 1000)
    {
        s[0] = WaveFreq / 1000 + '0';
        s[1] = '.';
        s[2] = ((WaveFreq) / 100) % 10 + '0';
        s[3] = 'k';
        s[4] = '\0';
    }
    else if (WaveFreq >= 100)
    {
        s[0] = WaveFreq / 100 + '0';
        s[1] = (WaveFreq / 10) % 10 + '0';
        s[2] = (WaveFreq) % 10 + '0';
        s[3] = '\0';
    }
    else if (WaveFreq >= 10)
    {
        s[0] = WaveFreq / 10 + '0';
        s[1] = (WaveFreq) % 10 + '0';
        s[2] = '\0';
    }
    else
    {
        s[0] = (WaveFreq) % 10 + '0';
        s[1] = '\0';
    }
    return s;
}

/* 将采样值的映射到屏幕的显示范围，并反转
   Remap sampling data to display range and inverse */
uint16 remap(uint16 val, uint16 rangeMax, uint16 rangeMin, uint16 rangeMaxNew, uint16 rangeMinNew)
{
    if (val > rangeMax)
        val = rangeMax;
    else if (val < rangeMin)
        val = rangeMin;

    val = rangeMinNew + (uint32)(rangeMax - val) * (rangeMaxNew - rangeMinNew) / (rangeMax - rangeMin);
    return val;
}

/* 获取触发点位置
   Get Trigger Position */
bit GetTriggerPos(uint16 d1, uint16 d2, uint16 dTrigger, bit triSlope)
{
    /*  上升沿触发
        Trigger on Rising Edge  */
    if (triSlope)
    {
        if (d1 <= dTrigger && d2 >= dTrigger)
        {
            return 1;
        }
    }

    /*  下降沿触发
        Trigger on Falling Edge */
    else
    {
        if (d1 >= dTrigger && d2 <= dTrigger)
        {
            return 1;
        }
    }

    return 0;
}

/* 分析采样数据
   Analyse sampling date */
void AnalyseData()
{
    int16 i;
    uint16 tmp;
    uint16 adcMax = 0;
    uint16 adcMin = 4095;
    uint16 adcMid = 0;
    uint16 plotADCMid = 0;
    if (ADCComplete)
    {
        ScaleH_tmp = ScaleH; //记录完成采样的时间区间，由于采样点的数量较少，因此不支持实时根据时间区间缩放波形，时间区间改变则清空波形
        //将采样点复制到另一个数组，避免采样中断造成数据混乱
        //若采样被中断，则使用缓存中旧采样点显示波形
        for (i = 0; i < SAMPLE_NUM; i++)
        {
            *(ADCbuf + i) = *(pADCSampling + i);
        }

        //计算触发点位置
        //ADC采样停止时，TriPos不变，所以不进行下列计算
        TriPos = SAMPLE_NUM / 2;
        TriFail = 1; //置位触发失败标志
        for (i = ((CHART_H_MAX - CHART_H_MIN) >> 1); i < SAMPLE_NUM - ((CHART_H_MAX - CHART_H_MIN) >> 1); i++)
        {
            if (GetTriggerPos(*(ADCbuf + i), *(ADCbuf + i + 1), TriggerADC, TriSlope))
            {
                TriPos = i;
                TriFail = 0; //清零触发失败标志
                break;
            }
        }
        TriPosOffset = 0;
    }

    /*  获取屏幕显示波形的最大和最小值
        Get the MAX and MIN value of waveform on display*/
    for (i = 0; i <= 100; i++)
    {
        tmp = *(ADCbuf + TriPos + TriPosOffset - 50 + i);
        if (tmp > adcMax)
            adcMax = tmp;
        else if (tmp < adcMin)
            adcMin = tmp;
    }

    //将采样点的最大最小采样值转换成电压值mV
    //cpv VMax = c_ADC_mv(adcMax, BGV, ADCbg, Lsb);
    //cpv VMin = c_ADC_mv(adcMin, BGV, ADCbg, Lsb);
    VMax = c_ADC_mv(adcMax, GetBGV_cpv(), ADCbg, Lsb); //cpv
    VMin = c_ADC_mv(adcMin, GetBGV_cpv(), ADCbg, Lsb); //cpv

    //获得垂直标尺的上下限
    getRulerV();

    //用垂直标尺mV范围反求出ADC值的范围作为图表的显示上下限
    //cpv plotADCMax = Convert_mv_ADC(RulerVMax, BGV, ADCbg, Lsb);
    //cpv plotADCMin = Convert_mv_ADC(RulerVMin, BGV, ADCbg, Lsb);
    plotADCMax = Convert_mv_ADC(RulerVMax, GetBGV_cpv(), ADCbg, Lsb); //cpv
    plotADCMin = Convert_mv_ADC(RulerVMin, GetBGV_cpv(), ADCbg, Lsb); //cpv

    //计算波形的频率
    //如果当前的时间区间和采样数据的时间间隔一致则进行频率计算
    //由于STC8A8K在高频采样时，ADC值经常莫名其妙地跳变到满量程4095，咨询STC工程师无果
    //为避免ADC采样出错时频率跳变厉害，计算波长时使用电压标尺的中点和波幅中点的较小值
    //如果遇到频率跳变无法读取，将自动量程切换至合适的手动量程即可
    adcMid = (adcMax + adcMin) >> 1;
    plotADCMid = (plotADCMax + plotADCMin) >> 1;
    if (getWaveLength(adcMid < plotADCMid ? adcMid : plotADCMid, 1) || getWaveLength(adcMid < plotADCMid ? adcMid : plotADCMid, 0))
    {
        getWaveFreq();
    }
    else
    {
        WaveFreq = 0;
    }

    //映射采样值至屏幕的显示范围
    for (i = 0; i < SAMPLE_NUM; i++)
    {
        waveBuf[i] = remap(*(ADCbuf + i), plotADCMax, plotADCMin, CHART_V_MAX, CHART_V_MIN);
    }
}

/*
 * cpv - to replace string array stored in program memory
    OLED_DrawString(ScaleHTxt[ScaleH]);
*/
void OLED_DrawString_ScaleHTxt(int8 _ScaleH)
{
  if (_ScaleH==0) OLED_DrawString("500ms"); //0
  else if (_ScaleH==1) OLED_DrawString("300ms"); //1
  else if (_ScaleH==2) OLED_DrawString("200ms"); //2
  else if (_ScaleH==3) OLED_DrawString("150ms"); //3
  else if (_ScaleH==4) OLED_DrawString("100ms"); //4
  else if (_ScaleH==5) OLED_DrawString("50ms"); //5
  else if (_ScaleH==6) OLED_DrawString("30ms"); //6
  else if (_ScaleH==7) OLED_DrawString("20ms"); //7
  else if (_ScaleH==8) OLED_DrawString("15ms"); //8
  else if (_ScaleH==9) OLED_DrawString("10ms"); //9
  else if (_ScaleH==10) OLED_DrawString("5ms"); //10
  else if (_ScaleH==11) OLED_DrawString("3ms"); //11
  else if (_ScaleH==12) OLED_DrawString("2ms"); //12
  else if (_ScaleH==13) OLED_DrawString("1.5ms"); //13
  else if (_ScaleH==14) OLED_DrawString("1ms"); //14
  else if (_ScaleH==15) OLED_DrawString("500us"); //15
  else if (_ScaleH==16) OLED_DrawString("300us"); //16
  else if (_ScaleH==17) OLED_DrawString("200us"); //17
  else if (_ScaleH==18) OLED_DrawString("150us"); //18
  else if (_ScaleH==19) OLED_DrawString("100us"); //19
  else if (_ScaleH==20) OLED_DrawString("80us"); //20
  else               OLED_DrawString("---us");  // out of bounds
}

/* 绘制主界面
   Draw main interface */
void PlotChart(void)
{
    uint8 i;
    uint8 *s;

    if (ClearDisplay)
    {
        ClearDisplay = 0;
        OLED_Clear();

        /* 图表边框
           波形横向绘图区101格,26~126
           波形纵向绘图区45格,8~52
           Frame of chart 45x101*/
        OLED_DrawHLine(CHART_H_MIN, CHART_V_MIN, 4);
        OLED_DrawHLine(CHART_H_MIN, CHART_V_MAX, 4);
        OLED_DrawHLine(CHART_H_MAX - 3, CHART_V_MIN, 4);
        OLED_DrawHLine(CHART_H_MAX - 3, CHART_V_MAX, 4);
        OLED_DrawHLine(CHART_H_MIN + 25 - 2, CHART_V_MIN, 5);
        OLED_DrawHLine(CHART_H_MIN + 25 - 2, CHART_V_MAX, 5);
        OLED_DrawHLine(CHART_H_MIN + 50 - 2, CHART_V_MIN, 5);
        OLED_DrawHLine(CHART_H_MIN + 50 - 2, CHART_V_MAX, 5);
        OLED_DrawHLine(CHART_H_MIN + 75 - 2, CHART_V_MIN, 5);
        OLED_DrawHLine(CHART_H_MIN + 75 - 2, CHART_V_MAX, 5);
        OLED_DrawVLine(CHART_H_MIN - 1, CHART_V_MIN, CHART_V_MAX - CHART_V_MIN + 1);
        OLED_DrawVLine(CHART_H_MAX + 1, CHART_V_MIN, CHART_V_MAX - CHART_V_MIN + 1);

        /* 图表虚线网格
           Grid of chart */
        for (i = 0; i < 14; i++)
        {
            OLED_DrawHLine(CHART_H_MIN + 7 * i, CHART_V_MIN + ((CHART_V_MAX - CHART_V_MIN) >> 1), 3);
        }
        for (i = 0; i < 6; i++)
        {
            OLED_DrawVLine(CHART_H_MIN + 25, CHART_V_MIN + 1 + i * 8, 3);
            OLED_DrawVLine(CHART_H_MIN + 50, CHART_V_MIN + 1 + i * 8, 3);
            OLED_DrawVLine(CHART_H_MIN + 75, CHART_V_MIN + 1 + i * 8, 3);
        }

        /* 波形位置标尺
           Ruler for waveform position*/
        /* 选中"滚动位置"时: 整条标尺反色(白底黑线); 未选中则清黑, 不留残影 */

        /* 波形电压范围
           Voltage range of waveform*/
        OLED_Set_Pos(26, 56);
        s = c_mv_V(VMin);
        OLED_DrawString(s);
        OLED_DrawString("-");
        s = c_mv_V(VMax);
        OLED_DrawString(s);
        OLED_DrawString("V");
    }

        if (OptionInChart == 5)
        {
            OLED_FillRect(0, 56, 25, 63, 1);
            OLED_Reverse(1);
        }
        else
        {
            OLED_FillRect(0, 56, 25, 63, 0);
            OLED_Reverse(0);
        }
        OLED_DrawHLine(0, 62, 25);
        OLED_DrawVLine(0, 60, 3);
        OLED_DrawVLine(24, 60, 3);
        OLED_DrawVLine((TriPos + TriPosOffset - 50) * 24 / 119, 58, 4);
        if (OptionInChart == 5)
            OLED_Reverse(0);

    OLED_Overlap(0); //设置绘图模式为覆盖

    /* 频率
       Frequency */
    OLED_Set_Pos(92, 0);
    OLED_DrawString("      ");
    OLED_Set_Pos(92, 0);
    s = c_WaveFreq_Str();
    OLED_DrawString(s);
    OLED_DrawString("Hz");

    /* 自动量程标志
       Flag for Auto Range*/
    if (ScaleV_Auto == 1)
    {
        OLED_Set_Pos(0, 0);
        OLED_DrawString("Auto");
    }
    else
    {
        OLED_Set_Pos(0, 0);
        OLED_DrawString("    ");
    }

    /* 触发值
       Trigger Level */
    OLED_Set_Pos(33, 0);
    if (OptionInChart == 2 && !WaveScroll)
    {
        OLED_DrawVLine(69, 0, 8);
        OLED_Reverse(1);
    }
    else
    {
        OLED_Reverse(1);
        OLED_DrawVLine(69, 0, 8);
        OLED_Reverse(0);
    }
    s = c_mv_V(TriLevel);
    OLED_DrawString("T");
    OLED_DrawString(s);
    OLED_DrawString("V");
    OLED_Reverse(0);

    /* 触发方向标志
       Trigger Slope */
    if (OptionInChart == 3 && !WaveScroll)
    {
        OLED_DrawVLine(71, 0, 8);
        OLED_DrawVLine(78, 0, 8);
        OLED_Reverse(1);
    }
    else
    {
        OLED_Reverse(1);
        OLED_DrawVLine(71, 0, 8);
        OLED_DrawVLine(78, 0, 8);
        OLED_Reverse(0);
    }
    if (TriSlope)
    {
        OLED_DrawChar(72, 0, 123); //123上箭头，上升沿触发
    }
    else
    {
        OLED_DrawChar(72, 0, 124); //124下箭头，下降沿触发
    }
    OLED_Reverse(0);

    /* 触发方式标志
       Trigger Mode */
    if (OptionInChart == 4 && !WaveScroll)
    {
        OLED_DrawVLine(86, 0, 8);
        OLED_Reverse(1);
    }
    else
    {
        OLED_Reverse(1);
        OLED_DrawVLine(86, 0, 8);
        OLED_Reverse(0);
    }
    OLED_Set_Pos(80, 0);
    if (TriMode == 0)
    {
        OLED_DrawString("A");
    }
    else if (TriMode == 1)
    {
        OLED_DrawString("N");
    }
    else if (TriMode == 2)
    {
        OLED_DrawString("S");
    }
    OLED_Reverse(0);

    /* 触发失败标志
       Flag for Trigger Fail*/
    if (TriFail)
    {
        OLED_Set_Pos(0, 24);
        OLED_DrawString("Fail");
    }

    //绘制运行/停止标志
    //    if (TriS && ADCRuning)
    //    {
    //        OLED_Set_Pos(0, 16);
    //        OLED_DrawString("Wait");
    //    }
    if (ADCRunning)
    {
        OLED_Set_Pos(0, 16);
        OLED_DrawString("Run ");
    }
    else
    {
        OLED_Set_Pos(0, 16);
        OLED_DrawString("Stop");
    }

    /* 横轴时间区间
       Seconds per division */
    OLED_Set_Pos(97, 56);
    OLED_DrawString("     ");
    if (OptionInChart == 0 && !WaveScroll)
    {
        OLED_Reverse(1);
    }
    OLED_Set_Pos(97, 56);
    //cpv OLED_DrawString(ScaleHTxt[ScaleH]);
    OLED_DrawString_ScaleHTxt(ScaleH); //cpv
    OLED_Reverse(0);

    /* 纵轴电压区间
       Ruler for Voltage */
    OLED_Set_Pos(0, 8);
    OLED_DrawString("    ");
    if (OptionInChart == 1 && !WaveScroll)
    {
        OLED_Reverse(1);
    }
    s = c_mv_V(RulerVMax);
    OLED_Set_Pos(0, 8);
    OLED_DrawString(s);
    OLED_Reverse(0);
    s = c_mv_V(RulerVMin);
    OLED_Set_Pos(0, 46);
    OLED_DrawString(s);

    OLED_Overlap(1); //恢复绘图模式为叠加
}

/* 绘制波形
   Draw waveform*/
void PlotWave(void)
{
    uint8 i;
    //Vector Mode
    //cpv if (PlotMode == 0)
    if (PlotMode == 1)
    {
        for (i = 0; i < (CHART_H_MAX - CHART_H_MIN); i++)
        {
            OLED_DrawLine(
                i + CHART_H_MIN,
                waveBuf[TriPos + TriPosOffset - ((CHART_H_MAX - CHART_H_MIN) >> 1) + i],
                i + CHART_H_MIN + 1,
                waveBuf[TriPos + TriPosOffset - ((CHART_H_MAX - CHART_H_MIN) >> 1) + i + 1]);
        }
    }
    //Dots Mode
    //cpv if (PlotMode == 1)
    else
    {
        for (i = 0; i <= (CHART_H_MAX - CHART_H_MIN); i++)
        {
            OLED_DrawPixel(i + CHART_H_MIN, waveBuf[TriPos + TriPosOffset - ((CHART_H_MAX - CHART_H_MIN) >> 1) + i]);
        }
    }

    /* cpv - 光标页: 波形画完叠加光标 */
    if (CursorPage)
        PlotCursors();
}

void OLED_DrawCNStr(uint8 x, uint8 y, const unsigned char code *str)
{
    uint8 i = 0;
    uint8 c;

    while ((c = str[i++]) != 0xFF)
    {
        if (x > WIDTH - CN_W)
            break;
        OLED_DrawGlyph12(x, y, (const unsigned char code *)CHS_12x12[c]);
        x += CN_W;
    }
}

/* 反色高亮: 先填白, 再用"擦除"模式重画该行内容 */
static void HighlightRow(uint8 y)
{
    OLED_FillRect(0, y, WIDTH - 1, y + CN_H - 1, 1);
    OLED_Reverse(1);
}

/* 反色高亮一整行(8 像素), 供设置页用 */
static void InvertRow16(uint8 y)
{
    OLED_InvertRect(0, y, WIDTH);
    if (y + 8 <= 56)
        OLED_InvertRect(0, y + 8, WIDTH);
}

/* 设置页: 12 行(打印模式/亮度/LSB/方波/波形/串口/电池/ORI/DEV), 一屏 8 行自动滚动 */
#define OLED_FONT_W 6
#define SETT_ROW_COUNT 12
#define SETT_ROWS_VIS 8

static const uint8 *code GenFreqName[15] = {
    "1Hz", "2Hz", "5Hz", "10Hz", "20Hz", "50Hz", "100Hz", "200Hz",
    "500Hz", "1kHz", "2kHz", "5kHz", "10kHz", "17kHz", "42kHz"
};
static const uint8 *code WaveTypeName[3] = {"Sine", "Tri ", "Saw "};

static void DrawNumRight(uint32 v, uint8 width)
{
    uint8 d = 1;
    if (v >= 10) d = 2;
    if (v >= 100) d = 3;
    if (v >= 1000) d = 4;
    if (v >= 10000) d = 5;
    while (d < width)
    {
        OLED_DrawString(" ");
        d++;
    }
    OLED_DrawNum(v, d);
}

#define SETT_ITEMS 14

void PlotSettings()
{
    uint8 i;
    int8 y, scroll;

    /* 进入"光标测量"页 */
    if (CursorPage)
    {
        return;                 /* 光标页由主循环绘制波形+光标 */
    }

    /* 校准表页 */
    if (CalPage)
    {
        PlotCalPage();
        return;
    }

    /* 进入"创作者信息"页 */
    if (InfoPage)
    {
        PlotInfoPage();
        return;
    }

    OLED_Overlap(0);

    /* 进入设置/切语言时先整屏清空, 避免底部残留上一画面 */
    if (ClearDisplay)
    {
        ClearDisplay = 0;
        OLED_Clear();
    }

    if (Lang)
    {
        uint8 slot;

        /* 先把 5 行可见区全部清黑, 再画内容(防止滚动后残留) */
        for (slot = 0; slot < 5; slot++)
            FillRowBand((uint8)(slot * 12), 0);

        /* ---------- 中文: 12x12 字, 5 行/屏 ---------- */
        if (OptionInSettings > 4)
            scroll = OptionInSettings - 4;
        else
            scroll = 0;

        for (i = 0; i < 14; i++)
        {
            uint8 hi = ((int8)i == OptionInSettings) ? 1 : 0;

            y = ((int8)i - scroll) * 12;
            if (y < 0 || y > 52)
                continue;

            FillRowBand((uint8)y, hi);
            OLED_Reverse(hi);

            switch (i)
            {
            case 0:
                OLED_DrawCNStr(0, (uint8)y, S_PlotMode);
                OLED_DrawCNStr(4 * CN_W + 2, (uint8)y, PlotMode ? S_Vect : S_Dots);
                break;
            case 1:
                OLED_DrawCNStr(0, (uint8)y, S_Bright);
                OLED_Set_Pos(2 * CN_W + 2, (uint8)(y + 2));
                if (OLED_Brightness < 10) OLED_DrawString("0");
                OLED_DrawNum(OLED_Brightness, 2);
                break;
            case 2:
                OLED_DrawCNStr(0, (uint8)y, S_Lsb);
                OLED_Set_Pos(4 * CN_W + 2, (uint8)(y + 2));
                OLED_DrawNum(Lsb, 3);
                break;
            case 3:
                OLED_DrawCNStr(0, (uint8)y, S_PwmOut);
                OLED_DrawCNStr(4 * CN_W + 2, (uint8)y, OutPWM ? S_On : S_Off);
                break;
            case 4:
                OLED_DrawCNStr(0, (uint8)y, S_PwmFreq);
                OLED_Set_Pos(4 * CN_W + 2, (uint8)(y + 2));
                OLED_DrawString(GenFreqName[GenFreqIdx > 14 ? 0 : GenFreqIdx]);
                break;
            case 5:
                OLED_DrawCNStr(0, (uint8)y, S_PwmDuty);
                OLED_Set_Pos(3 * CN_W + 2, (uint8)(y + 2));
                if (GenDuty < 10) OLED_DrawString("0");
                OLED_DrawNum(GenDuty, 2);
                OLED_DrawString("%");
                break;
            case 6:
                OLED_DrawCNStr(0, (uint8)y, S_WaveOut);
                OLED_DrawCNStr(4 * CN_W + 2, (uint8)y, OutSIN ? S_On : S_Off);
                break;
            case 7:
                OLED_DrawCNStr(0, (uint8)y, S_WaveType);
                OLED_DrawCNStr(4 * CN_W + 2, (uint8)y,
                               (WaveType == 1) ? S_Tri : ((WaveType == 2) ? S_Saw : S_Sine));
                break;
            case 8:
                OLED_DrawCNStr(0, (uint8)y, S_UartOut);
                OLED_DrawCNStr(4 * CN_W + 2, (uint8)y, OutUART ? S_On : S_Off);
                break;
            case 9:
                OLED_DrawCNStr(0, (uint8)y, S_Lang);
                OLED_DrawCNStr(2 * CN_W + 2, (uint8)y, Lang ? S_Cn : S_En);
                break;
            case 10:
                OLED_DrawCNStr(0, (uint8)y, S_Cursor);
                OLED_Set_Pos(4 * CN_W + 2, (uint8)(y + 2));
                OLED_DrawString(">");
                break;
            case 11:
                OLED_DrawCNStr(0, (uint8)y, S_Creator);
                OLED_Set_Pos(5 * CN_W + 2, (uint8)(y + 2));
                OLED_DrawString(">");
                break;
            case 12:
                OLED_DrawCNStr(0, (uint8)y, S_Cal);
                OLED_Set_Pos(3 * CN_W + 2, (uint8)(y + 2));
                OLED_DrawString(">");
                break;
            case 13:
                OLED_DrawCNStr(0, (uint8)y, S_Batt);
                OLED_Set_Pos(4 * CN_W + 2, (uint8)(y + 2));
                OLED_DrawString(c_mv_V(VBat));
                OLED_DrawString("V");
                break;
            }
            OLED_Reverse(0);
        }
    }
    else
    {
        /* ---------- English: 8 像素行 ---------- */
        uint8 slot;

        if (OptionInSettings > 7)
            scroll = OptionInSettings - 7;
        else
            scroll = 0;

        /* 先清 8 行可见区 */
        for (slot = 0; slot < 8; slot++)
            OLED_ClearRow((uint8)(slot * 8));

        for (i = 0; i < 14; i++)
        {
            uint8 hi = ((int8)i == OptionInSettings) ? 1 : 0;

            y = ((int8)i - scroll) * 8;
            if (y < 0 || y > 56)
                continue;

            OLED_ClearRow((uint8)y);
            if (hi)
            {
                OLED_FillRect(0, (uint8)y, WIDTH - 1, (uint8)(y + 7), 1);
                OLED_Reverse(1);
            }
            OLED_Set_Pos(0, (uint8)y);

            switch (i)
            {
            case 0: OLED_DrawString("Plot Mode="); OLED_DrawString(PlotMode ? "Vect" : "Dots"); break;
            case 1: OLED_DrawString("Bright="); if (OLED_Brightness < 10) OLED_DrawString("0"); OLED_DrawNum(OLED_Brightness, 2); break;
            case 2: OLED_DrawString("LSB="); OLED_DrawNum(Lsb, 3); break;
            case 3: OLED_DrawString("PWM Out="); OLED_DrawString(OutPWM ? "ON " : "OFF"); break;
            case 4: OLED_DrawString("PWM Freq="); OLED_DrawString(GenFreqName[GenFreqIdx > 14 ? 0 : GenFreqIdx]); break;
            case 5: OLED_DrawString("PWM Duty="); if (GenDuty < 10) OLED_DrawString("0"); OLED_DrawNum(GenDuty, 2); OLED_DrawString("%"); break;
            case 6: OLED_DrawString("Wave Out="); OLED_DrawString(OutSIN ? "ON " : "OFF"); break;
            case 7: OLED_DrawString("Wave Type="); OLED_DrawString(WaveTypeName[WaveType > 2 ? 0 : WaveType]); break;
            case 8: OLED_DrawString("UART Out="); OLED_DrawString(OutUART ? "ON " : "OFF"); break;
            case 9: OLED_DrawString("Language="); OLED_DrawString(Lang ? "CN" : "EN"); break;
            case 10: OLED_DrawString("Cursor >"); break;
            case 11: OLED_DrawString("Dev-er Info >"); break;
            case 12: OLED_DrawString("Cal table >"); break;
            case 13: OLED_DrawString("Batt Voltage="); OLED_DrawString(c_mv_V(VBat)); OLED_DrawString("V"); break;
            }
            OLED_Reverse(0);
        }
    }
    OLED_Reverse(0);
    OLED_Overlap(1);
}

static void FillRowBand(uint8 y, bit white)
{
    OLED_FillRect(0, y, WIDTH - 1, y + 11, white);
}

/* 开机启动页: Mini-DSO 图标 + 作者缩写 */
/* 每档每采样点的间隔(us) */
static const uint16 code TB_DT_US[21] = {
    20000, 12000, 8000, 6000, 4000, 2000, 1200, 800, 600, 400,
    200, 120, 80, 60, 40, 20, 12, 8, 6, 4, 3
};

static uint8 NumDigits(uint16 v)
{
    uint8 n = 1;
    while (v >= 10) { v /= 10; n++; }
    return n;
}

/* 光标测量叠加层: 两条竖线 + dT / dV 读数 */


void PlotSplash(void)
{
    OLED_Overlap(0);
    OLED_Clear();
    /* LOGO 82x13, 居中: (128-82)/2 = 23 */
    OLED_DrawBMP(23, 14, 23 + 81, 14 + 12, (uint8 *)MINIDSO, sizeof(MINIDSO));
    /* 文字 13 字符 x 6px = 78, 居中: (128-78)/2 = 25 */
    OLED_Set_Pos(25, 38);
    OLED_DrawString("C.L./W.S.&D.S");

    /* 自检结果 */
    OLED_Set_Pos(4, 52);
    OLED_DrawString("EEP:");
    OLED_DrawString(PostEepromOk ? "OK " : "DEF");
    OLED_DrawString(" CAL:");
    OLED_DrawString(PostCalOk ? "OK " : "ERR");
    OLED_DrawString(" ");
    OLED_DrawString(c_mv_V(GetBGV_cpv()));
    OLED_DrawString("V");
    OLED_Overlap(1);
}

/* 轮播画一行 ASCII(反色模式下会画成黑字) */
static void DrawMarqueeRow(uint8 y, uint8 *str, uint8 offset)
{
    uint8 i, idx, len;

    len = strlen(str);
    if (!len)
        return;
    for (i = 0; i < WIDTH / 6; i++)
    {
        idx = (uint8)((offset + i) % (len + 3));
        OLED_DrawChar((uint8)(i * 6), y, (idx < len) ? str[idx] : ' ');
    }
}

/* 校准表页: 显示 5 档校准值, 逐档微调 */
void PlotCalPage(void)
{
    uint8 slot, idx, base;
    int8 y;

    OLED_Overlap(0);
    if (ClearDisplay)
    {
        ClearDisplay = 0;
        OLED_Clear();
    }

    OLED_Set_Pos(2, 0);
    OLED_DrawString("CAL ");
    OLED_DrawNum(CalSel, NumDigits(CalSel));
    OLED_DrawString("/20");
    OLED_Set_Pos(70, 0);
    OLED_DrawString_ScaleHTxt((int8)CalSel);

    base = (CalSel > 2) ? (uint8)(CalSel - 2) : 0;
    for (slot = 0; slot < 5; slot++)
    {
        idx = base + slot;
        if (idx > 20)
            break;
        y = (int8)(slot * 12 + 12);
        if (y > 52)
            break;
        FillRowBand((uint8)y, (idx == CalSel) ? 1 : 0);
        OLED_Reverse((idx == CalSel) ? 1 : 0);
        OLED_Set_Pos(2, (uint8)(y + 2));
        OLED_DrawString("#");
        OLED_DrawNum(idx, NumDigits(idx));
        OLED_Set_Pos(40, (uint8)(y + 2));
        OLED_DrawNum(CalTable[idx], 5);
        OLED_Reverse(0);
    }
    OLED_Overlap(1);
}

/* 创作者信息页: LOGO + 作者/开发(可选中) + 底部 <Back */
/* 创作者信息页: LOGO + 作者/开发(可选中) + 底部 <Back */
void PlotInfoPage(void)
{
    OLED_Overlap(0);
    OLED_Clear();
    OLED_DrawBMP(23, 0, 23 + 81, 0 + 12, (uint8 *)MINIDSO, sizeof(MINIDSO));

    /* ---- 原作行 (y=16) ---- */
    FillRowBand(16, (InfoSel == 0) ? 1 : 0);
    OLED_Reverse((InfoSel == 0) ? 1 : 0);
    if (ShowOriUrl)
        DrawMarqueeRow(18, (uint8 *)"github.com/CreativeLau/Mini-DSO", MarqueeOffset);
    else
    {
        if (Lang)
        {
            OLED_DrawCNStr(0, 16, S_Ori);
            OLED_Set_Pos(2 * CN_W + 2, 18);
        }
        else
        {
            OLED_Set_Pos(0, 18);
            OLED_DrawString("ORI:");
        }
        OLED_DrawString("CreativeLau");
    }
    OLED_Reverse(0);

    /* ---- 开发行 (y=28) ---- */
    FillRowBand(28, (InfoSel == 1) ? 1 : 0);
    OLED_Reverse((InfoSel == 1) ? 1 : 0);
    if (ShowDevUrl)
        DrawMarqueeRow(30, (uint8 *)"wstek.win", MarqueeOffset);
    else
    {
        if (Lang)
        {
            OLED_DrawCNStr(0, 28, S_Dev);
            OLED_Set_Pos(2 * CN_W + 2, 30);
        }
        else
        {
            OLED_Set_Pos(0, 30);
            OLED_DrawString("DEV:");
        }
        OLED_DrawString("WuSi&Deepseek");
    }
    OLED_Reverse(0);

    /* ---- 项目说明及地址行 (y=40) ---- */
    FillRowBand(40, (InfoSel == 2) ? 1 : 0);
    OLED_Reverse((InfoSel == 2) ? 1 : 0);
    if (ShowProjUrl)
        DrawMarqueeRow(42, (uint8 *)"github.com/WuSiTech/mini-dso", MarqueeOffset);
    else
    {
        if (Lang)
        {
            OLED_DrawCNStr(0, 40, S_Proj);
            OLED_Set_Pos(7 * CN_W + 2, 42);
            OLED_DrawString("(v1.3)");
        }
        else
        {
            OLED_Set_Pos(0, 42);
            OLED_DrawString("PROJ:(v1.3)");
        }
    }
    OLED_Reverse(0);

    /* ---- 底部 <Back 行 (y=52) ---- */
    FillRowBand(52, (InfoSel == 3) ? 1 : 0);
    OLED_Reverse((InfoSel == 3) ? 1 : 0);
    OLED_Set_Pos(40, 56);
    OLED_DrawString("<Back");
    OLED_Reverse(0);
    OLED_Overlap(1);
}

/* 绘制保存状态
   Draw saving status*/
void PlotSaveStatus(uint8 _st)
{
    OLED_Overlap(0);
    OLED_ClearRow(50);
    OLED_ClearRow(56);
    if (_st == 2)                 /* 已取消修改 */
    {
        if (Lang)
            OLED_DrawCNStr(16, 50, S_Cancel);
        else
        {
            OLED_Set_Pos(0, 56);
            OLED_DrawString("Changes discarded");
            OLED_InvertRect(0, 56, WIDTH);
        }
    }
    else if (_st == 1)            /* 保存成功 */
    {
        if (Lang)
            OLED_DrawCNStr(16, 50, S_SaveOk);
        else
        {
            OLED_Set_Pos(0, 56);
            OLED_DrawString("Save Success");
            OLED_InvertRect(0, 56, WIDTH);
        }
    }
    else                          /* 保存失败 */
    {
        if (Lang)
            OLED_DrawCNStr(16, 50, S_SaveFail);
        else
        {
            OLED_Set_Pos(0, 56);
            OLED_DrawString("Save Failed");
            OLED_InvertRect(0, 56, WIDTH);
        }
    }
    OLED_Overlap(1);
}


/* 光标测量叠加层: 两条竖线 + 底部一行显示 dT / dV */
void PlotCursors(void)
{
    uint8 y;
    int16 idxA, idxB;
    uint16 mvA, mvB, dv, bgv;
    uint32 d10;

    if (!CursorPage)
        return;

    OLED_Overlap(0);

    /* 竖线: 选中的实线, 另一个虚线; 只在图表区内 */
    for (y = CHART_V_MIN + 1; y < CHART_V_MAX; y++)
    {
        OLED_DrawPixel((uint8)(CHART_H_MIN + CurA), y);
        if (y & 1)
            OLED_DrawPixel((uint8)(CHART_H_MIN + CurB), y);
    }
    if (CurSel)
    {
        for (y = CHART_V_MIN + 1; y < CHART_V_MAX; y += 2)
            OLED_DrawPixel((uint8)(CHART_H_MIN + CurA), y);
        for (y = CHART_V_MIN + 1; y < CHART_V_MAX; y++)
            OLED_DrawPixel((uint8)(CHART_H_MIN + CurB), y);
    }

    /* 采样索引: 与 PlotWave 一致 (TriPos + TriPosOffset - 50 + i) */
    idxA = (int16)TriPos + (int16)TriPosOffset - ((CHART_H_MAX - CHART_H_MIN) >> 1) + (int16)CurA;
    idxB = (int16)TriPos + (int16)TriPosOffset - ((CHART_H_MAX - CHART_H_MIN) >> 1) + (int16)CurB;
    if (idxA < 0) idxA = 0;
    if (idxA > SAMPLE_NUM - 1) idxA = SAMPLE_NUM - 1;
    if (idxB < 0) idxB = 0;
    if (idxB > SAMPLE_NUM - 1) idxB = SAMPLE_NUM - 1;

    bgv = GetBGV_cpv();
    mvA = c_ADC_mv(ADCbuf[idxA], bgv, ADCbg, Lsb);
    mvB = c_ADC_mv(ADCbuf[idxB], bgv, ADCbg, Lsb);
    dv = (mvA > mvB) ? (mvA - mvB) : (mvB - mvA);

    /* 底部一行(原来的电压范围/时基信息位置, 光标模式下被替换) */
    OLED_ClearRow(56);
    OLED_Set_Pos(2, 56);

    OLED_DrawString("dT:");
    d10 = (uint32)TB_DT_US[ScaleH] * 10UL;
    if (CurA > CurB)
        d10 *= (uint32)(CurA - CurB);
    else
        d10 *= (uint32)(CurB - CurA);

    if (d10 >= 100000UL)
    {
        uint16 ms = (uint16)(d10 / 10000UL);
        OLED_DrawNum(ms, NumDigits(ms));
        OLED_DrawString("ms");
    }
    else if (d10 >= 10000UL)
    {
        uint16 t = (uint16)(d10 / 1000UL);
        OLED_DrawNum((uint16)(t / 10), NumDigits((uint16)(t / 10)));
        OLED_DrawString(".");
        OLED_DrawNum((uint16)(t % 10), 1);
        OLED_DrawString("ms");
    }
    else
    {
        uint16 t = (uint16)(d10 / 10UL);
        OLED_DrawNum(t, NumDigits(t));
        OLED_DrawString("us");
    }

    OLED_DrawString(" dV:");
    OLED_DrawString(c_mv_V(dv));
    OLED_DrawString("V");

    OLED_Overlap(1);
}
