/*
    adc_stc8.c

    Sampling with ADC built in MCU
    
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

#include "adc_stc8.h"

#ifdef STC8

/* scale_h: Time scale 500ms, 300ms, 200ms, 150ms, 100ms, 50ms, 30ms, 20ms, 15ms, 10ms, 5ms, 3ms, 2ms, 1.5ms, 1ms, 500us, 300us, 200us, 150us, 100us, 70us */
void ADCInit(uint8 scale_h)
{
    uint8 ADC_SPEED = ADC_SPEED_512; // cpv

    switch (scale_h)
    {
    case 0:  //500ms
    case 1:  //300ms
    case 2:  //200ms
    case 3:  //150ms
    case 4:  //100ms
    case 5:  //50ms
    case 6:  //30ms
    case 7:  //20ms
    case 8:  //15ms
    case 9:  //10ms
    case 10: //5ms
    case 11: //3ms
    case 12: //2ms
        ADC_SPEED = ADC_SPEED_512;
        break;

    case 13: //1.5ms
    case 14: //1ms
        ADC_SPEED = ADC_SPEED_352;
        break;

    case 15: //500us
    case 16: //300us
        ADC_SPEED = ADC_SPEED_192;
        break;

    default: //200us, 150us, 100us, 70us
        ADC_SPEED = ADC_SPEED_32;
        break;
    }

    ADCCFG = RESFMT | ADC_SPEED; //结果右对齐，设置 ADC 时钟为系统时钟/2/16/16
    ADC_CONTR = ADC_POWER;       //使能 ADC 模块
    Delay5ms();                  //ADC上电并延时
}

uint16 ADCRead(uint8 chx)
{
    uint16 res;
    ADC_RES = 0;            //清除结果寄存器
    ADC_RESL = 0;           //清除结果寄存器
    ADC_CONTR &= 0xF0;      //选择ADC输入通道
    ADC_CONTR |= chx;       //选择ADC输入通道
    ADC_CONTR |= ADC_START; //启动 AD 转换
    _nop_();
    _nop_();

    while (!(ADC_CONTR & ADC_FLAG))
        ; //查询 ADC 完成标志

    ADC_CONTR &= ~ADC_FLAG;          //清完成标志
    res = (ADC_RES << 8) | ADC_RESL; //读取 ADC 结果
    return res;
}

#pragma save /* cpv */
#pragma disable_warning 196 /* cpv */
/*uint16 *GetBGV(void)
{
    uint16 *BGV;
    //cpv BGV = (uint16 code *)BGV_ADR;
    BGV = (uint16 __code *)BGV_ADR;
    return BGV;
}*/
#pragma restore /* cpv */
uint16 GetBGV_cpv(void)
{
  uint16 v = *(uint16 __code *)BGV_ADR;

  /* 校准字缺失/被擦除时(读出来是 0xFFFF 之类)用典型值，避免电压被放大几十倍 */
  if (v < 900 || v > 1800)
    v = 1200;
  return v;
}

uint16 GetADC_CHX(uint8 chx)
{
    uint16 ADCx;
    uint8 i;

    ADCInit(0); //ADC 初始化

    //通过ADC的chx通道读取Bandgap电压的ADC测量值
    ADCRead(chx); //前两个数据丢弃
    ADCRead(chx);
    ADCx = 0;

    for (i = 0; i < 16; i++)
    {
        ADCx += ADCRead(chx);
    }

    ADCx >>= 4; //取平均值
    return ADCx;
}

uint16 GetVoltage(uint8 chx, uint16 lsb)
{
    uint16 ADCbg;
    //cpv uint16 *BGV;
    uint16 ADCx;
    uint16 Vx;

    ADCInit(0); //ADC 初始化

    //通过ADC的第16通道读取Bandgap电压的ADC平均值
	// cpv - Read the ADC average value of the Bandgap voltage through ADC channel 16
    ADCbg = GetADC_CHX(ADC_CHS_BG);

    //通过ADC的chx通道读取外部输入电压的ADC平均值
	//cpv - Read the ADC average value of the external input voltage through ADC channel chx
    ADCx = GetADC_CHX(chx);

    //通过公式计算外部输入的实际电压值
	//cpv - Calculate the actual voltage value of the external input using a formula
    //cpv BGV = GetBGV();
    //cpv Vx = (uint32)*BGV * ADCx * lsb / ADCbg / 100;
    Vx = (uint32)GetBGV_cpv() * ADCx * lsb / ADCbg / 100;
    return Vx;
}

//	ADCRead(chx) Timing (45MHz 估算值): 500ms, 300ms, 200ms, 150ms, 100ms, 50ms, 30ms, 20ms, 15ms,
//	10ms, 5ms, 3ms, 2ms, 1.5ms, 1ms, 500us, 300us, 200us, 150us, 100us, 70us
//	屏幕的横向共4格，每格代表一个时间范围，每格25个采样点，时基 = 25 × 采样间隔
//  45MHz 下 ADC 转换时间估算（按 27MHz 实测值 26/19/11/4us 等比缩放，需上机实测校准）:
//	ADC_SPEED_512 15.6us
//	ADC_SPEED_352 11.4us
//	ADC_SPEED_192 6.6us
//	ADC_SPEED_32  2.4us
/* cpv - 各档 DelayUs() 的请求值(us), 由 COM5 自动测量逐档标定
   采样间隔 ≈ 该档基础开销 + DelayUs(请求值) */
/* cpv - 时基延时默认表(实测标定值)
   0~14 档: DelayUs 的微秒数;  15~19 档: DelayFine 的 0.25us 单位;  20 档不用 */
static const uint16 code DefaultDelayTable[21] = {
    19558, 11754, 7818, 5867, 3919, 1934, 1154, 757,
    564, 366, 169, 90, 53, 40, 21,
    20, 2, 6, 1, 1,
    0
};

/* 上电初始化时基延时表: 先装默认值, 再尝试从 EEPROM 载入校准值 */
void InitDelayTable(void)
{
    uint8 i;

    for (i = 0; i < 21; i++)
        CalTable[i] = DefaultDelayTable[i];
}

void switch_Dealy(uint8 scale_h)
{
    uint16 v;

    if (scale_h > 20)
        return;
    v = CalTable[scale_h];
    if (!v)
        return;
    if (scale_h >= 15)
        DelayFine(v); /* 快档: 0.25us 步进, 精度更高 */
    else
        DelayUs(v);
}
uint16 *GetWaveADC(uint8 chx, uint8 scale_h)
{
    uint8 i, j;
    static uint16 ADCSampling[SAMPLE_NUM];
    uint16 ADCPreSampling[PRE_BUF_NUM + 1]; //单次触发预缓存，有效采样点PRE_BUF_NUM个，多出的第一个位置用于复制最后一个位置的值，组成循环缓存

    ADCComplete = 0; //清零采样完成标志
    if (ADCInterrupt)
        return ADCSampling;
    memset(ADCSampling, 0x00, SAMPLE_NUM * 2);
    memset(ADCPreSampling, 0x00, (PRE_BUF_NUM + 1) * 2);
    //BGV = GetBGV(); //获取参考电压值 //cpv - this was already commented out, but BGV is used two lines below.
    ADCbg = GetADC_CHX(ADC_CHS_BG);                         //获取参考ADC值
    //cpv TriggerADC = Convert_mv_ADC(TriLevel, BGV, ADCbg, Lsb); //将用户设定的出发电压值转换为ADC值
    TriggerADC = Convert_mv_ADC(TriLevel, GetBGV_cpv(), ADCbg, Lsb); //将用户设定的出发电压值转换为ADC值

    //初次打开内部A/D转换模拟电源，需适当延时，等内部模拟电源稳定后，再启动A/D转换
    ADCInit(scale_h);
    //通过ADC的第x通道读取外部输入电压的ADC测量值
    ADCRead(chx); //前两个数据丢弃
    ADCRead(chx);

    //最快档(70us)不支持单次触发，采样过程中不能有多余的代码，所以单独分立出来
    if (scale_h == SCALE_H_MAX) //70 us (最快档)
    {
        for (i = 0; i < SAMPLE_NUM; i++)
        {
            if (ADCInterrupt)
                return ADCSampling;
            ADCSampling[i] = ADCRead(chx);
#ifdef DEBUG
            P15 = ~P15;
#endif
        }
    }

    /* 单次触发或普通触发
       Single or Normal Trigger Mode */
    else if (TriMode)
    {
        for (j = 1; j <= PRE_BUF_NUM; j++) //预缓存PRE_BUF_NUM个采样点，预缓存的第一个位置保留，用于存储和预缓存最后一个位置相同的值，组成环形缓存
        {
            if (ADCInterrupt)
                return ADCSampling;
            switch_Dealy(scale_h); //采样延时
            ADCPreSampling[j] = ADCRead(chx);
#ifdef DEBUG
            P15 = ~P15;
#endif
        }

        //循环缓存触发前的PRE_BUF_NUM个采样点，并检测采样点是否满足触发条件
        while (1)
        {
            if (ADCInterrupt)
                return ADCSampling;

            //预缓存溢出则置1，并把最后一个采样值复制到第一个位置
            if (j > PRE_BUF_NUM)
            {
                j = 1;
                ADCPreSampling[0] = ADCPreSampling[PRE_BUF_NUM];
            }
            switch_Dealy(scale_h); //采样延时
            ADCPreSampling[j] = ADCRead(chx);
            if (GetTriggerPos(ADCPreSampling[j - 1], ADCPreSampling[j], TriggerADC, TriSlope)) //是否满足触发条件
            {
                break;
            }
            j++;
#ifdef DEBUG
            P15 = ~P15;
#endif
        }

        //继续采样AFT_BUF_NUM个采样点
        for (i = 0; i < AFT_BUF_NUM; i++)
        {
            if (ADCInterrupt)
                return ADCSampling;
            switch_Dealy(scale_h); //采样延时
            ADCSampling[i + PRE_BUF_NUM] = ADCRead(chx);
#ifdef DEBUG
            P15 = ~P15;
#endif
        }

        //将前PRE_BUF_NUM个和后PRE_BUF_NUM个采样点组合成完整波形
        for (i = 0; i < PRE_BUF_NUM; i++) //预缓存中第一个和最后一个采样值相等，舍掉第一个值，将剩余PRE_BUF_NUM-1个采样点按采样顺序排序，作为ADCSampling的前PRE_BUF_NUM-1个采样点
        {
            if (ADCInterrupt)
                return ADCSampling;
            if (++j > PRE_BUF_NUM) //预缓存溢出，跳转到预缓存第二个位置
                j = 1;

            ADCSampling[i] = ADCPreSampling[j];
        }
    }

    /* 自动触发
       Auto Trigger Mode */
    else
    {
        for (i = 0; i < SAMPLE_NUM; i++)
        {
            if (ADCInterrupt)
                return ADCSampling;
            ADCSampling[i] = ADCRead(chx);
            switch_Dealy(scale_h); //采样延时
#ifdef DEBUG
            P15 = ~P15;
#endif
        }
    }
    ADCComplete = 1; //置位采样完成标志
    return ADCSampling;
}

#endif
