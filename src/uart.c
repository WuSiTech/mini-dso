/*
    uart.c

    cpv - UART1 二进制协议：采样数据上传 + 电脑端参数设置。

    帧格式: A5 5A TYPE LENH LENL PAYLOAD[LEN] SUM
            SUM = (TYPE + LENH + LENL + sum(PAYLOAD)) & 0xFF

    115200 8N1，波特率由 Timer2 (1T) 产生:
      波特率 = SYSclk / (4 * (65536 - [T2H,T2L]))
      45MHz: 65536 - 98 = 65438  ->  114.8kbps (-0.35%)
*/

#include "uart.h"
#include "delay.h"
#include "settings.h"
#include "chart.h"

#define UART_TX_SIZE 512
#define UART_RX_SIZE 128

/* 发送环形缓冲 (xdata) */
static __xdata uint8 UartTx[UART_TX_SIZE];
static uint16 UartTxHead;
static uint16 UartTxTail;
static bit UartTxBusy;

/* 接收环形缓冲 */
static __xdata uint8 UartRx[UART_RX_SIZE];
static uint8 UartRxHead;
static uint8 UartRxTail;

/* 接收帧解析 */
static __xdata uint8 FrameBuf[64]; /* 命令负载缓冲(校准表 42 字节) */
static __xdata uint8 CalBuf[42]; /* 时基校准表收发缓冲 */ /* 命令负载最大 18 字节 */
static uint8 FrameType;
static uint16 FrameLen;
static uint16 FrameIdx;
static uint8 FrameSum;
static uint8 ParseState;

static void UART_HandleFrame(void);

/* 初始化: 115200 8N1, Timer2 作波特率发生器 (Timer1 留给 PWM/正弦) */
void UART_Init(void)
{
    P3M1 &= ~0x02; /* P3.1 TXD 推挽输出 */
    P3M0 |= 0x02;

    SCON = 0x50;  /* 模式1: 8 位 UART, 允许接收 */
    T2H = 0xFF;   /* 45MHz: 65536-98 = 65438 */
    T2L = 0x9E;
    AUXR |= 0x01; /* S1ST2=1: UART1 波特率用 Timer2 */
    AUXR |= 0x04; /* T2x12=1: Timer2 1T 模式 */
    AUXR |= 0x10; /* T2R=1: 启动 Timer2 */
    ES = 1;       /* 使能串口1中断 */

    UartTxHead = 0;
    UartTxTail = 0;
    UartTxBusy = 0;
    UartRxHead = 0;
    UartRxTail = 0;
    ParseState = 0;
}

/* 发送一字节(进环形缓冲)；缓冲满则丢弃 */
void UART_WriteByte(uint8 b)
{
    uint16 next;

    next = UartTxHead + 1;
    if (next >= UART_TX_SIZE)
        next = 0;
    if (next == UartTxTail)
        return; /* 满 */

    UartTx[UartTxHead] = b;
    UartTxHead = next;

    if (!UartTxBusy)
    {
        UartTxBusy = 1;
        TI = 0;
        SBUF = UartTx[UartTxTail];
        UartTxTail = UartTxTail + 1;
        if (UartTxTail >= UART_TX_SIZE)
            UartTxTail = 0;
    }
}

/* 发送一整帧；缓冲空间不够则整帧丢弃，避免半帧 */
void UART_SendFrame(uint8 type, uint8 *buf, uint16 len)
{
    uint16 i;
    uint16 used;
    uint16 freebytes;
    uint8 sum;

    used = UartTxHead + UART_TX_SIZE - UartTxTail;
    if (used >= UART_TX_SIZE)
        used -= UART_TX_SIZE;
    freebytes = (UART_TX_SIZE - 1) - used;
    if (freebytes < (uint16)(len + 6))
        return;

    sum = type + (uint8)(len >> 8) + (uint8)(len & 0xFF);

    UART_WriteByte(UART_HEAD0);
    UART_WriteByte(UART_HEAD1);
    UART_WriteByte(type);
    UART_WriteByte((uint8)(len >> 8));
    UART_WriteByte((uint8)(len & 0xFF));
    for (i = 0; i < len; i++)
    {
        UART_WriteByte(buf[i]);
        sum += buf[i];
    }
    UART_WriteByte(sum);
}

/* 上传一帧采样数据: 28 字节头 + 100 个原始 ADC 值(小端) */
void UART_SendSamples(void)
{
    static __xdata uint8 pay[28 + UART_SAMP_NUM * 2];
    int16 base;
    uint16 v;
    uint8 i;

    if (!OutUART)
        return;

    base = (int16)TriPos + (int16)TriPosOffset - 50;
    if (base < 0)
        base = 0;
    if (base > SAMPLE_NUM - (int16)(UART_SAMP_NUM + 1))
        base = SAMPLE_NUM - (int16)(UART_SAMP_NUM + 1);

    pay[0] = (uint8)((ADCRunning ? 0x01 : 0x00) | (TriFail ? 0x02 : 0x00) | (ScaleV_Auto ? 0x04 : 0x00));
    pay[1] = (uint8)ScaleH;
    pay[2] = PlotMode ? 1 : 0;
    pay[3] = (uint8)TriMode;
    pay[4] = TriSlope ? 1 : 0;
    pay[5] = UART_SAMP_NUM;
    pay[6] = (uint8)(VMax & 0xFF);
    pay[7] = (uint8)(VMax >> 8);
    pay[8] = (uint8)(VMin & 0xFF);
    pay[9] = (uint8)(VMin >> 8);
    pay[10] = (uint8)(WaveFreq & 0xFF);
    pay[11] = (uint8)((WaveFreq >> 8) & 0xFF);
    pay[12] = (uint8)((WaveFreq >> 16) & 0xFF);
    pay[13] = (uint8)((WaveFreq >> 24) & 0xFF);
    /* 纵轴刻度: 屏幕上下对应的电压(mV) + 对应的 ADC 端点，供上位机换算 */
    pay[14] = (uint8)((uint16)RulerVMin & 0xFF);
    pay[15] = (uint8)((uint16)RulerVMin >> 8);
    pay[16] = (uint8)((uint16)RulerVMax & 0xFF);
    pay[17] = (uint8)((uint16)RulerVMax >> 8);
    pay[18] = (uint8)(plotADCMin & 0xFF);
    pay[19] = (uint8)(plotADCMin >> 8);
    pay[20] = (uint8)(plotADCMax & 0xFF);
    pay[21] = (uint8)(plotADCMax >> 8);
    /* 电压换算参数: mV = raw * BGV * Lsb / ADCbg / 100 */
    pay[22] = (uint8)(GetBGV_cpv() & 0xFF);
    pay[23] = (uint8)(GetBGV_cpv() >> 8);
    pay[24] = (uint8)(ADCbg & 0xFF);
    pay[25] = (uint8)(ADCbg >> 8);
    pay[26] = (uint8)(Lsb & 0xFF);
    pay[27] = (uint8)(Lsb >> 8);
    for (i = 0; i < UART_SAMP_NUM; i++)
    {
        v = ADCbuf[base + i];
        pay[28 + i * 2] = (uint8)(v & 0xFF);
        pay[29 + i * 2] = (uint8)(v >> 8);
    }
    UART_SendFrame(UART_T_SAMPLE, pay, 28 + UART_SAMP_NUM * 2);
}

/* 当前设置打包成 18 字节 (与 EEPROM 顺序一致) */
uint8 UART_GetSettings(uint8 *s)
{
    s[0] = (uint8)(Lsb & 0xFF);
    s[1] = (uint8)(Lsb >> 8);
    s[2] = PlotMode ? 1 : 0;
    s[3] = (uint8)ScaleH;
    s[4] = ScaleV_Auto ? 1 : 0;
    s[5] = (uint8)((uint16)RulerVMax & 0xFF);
    s[6] = (uint8)((uint16)RulerVMax >> 8);
    s[7] = (uint8)((uint16)RulerVMin & 0xFF);
    s[8] = (uint8)((uint16)RulerVMin >> 8);
    s[9] = (uint8)((uint16)TriLevel & 0xFF);
    s[10] = (uint8)((uint16)TriLevel >> 8);
    s[11] = (uint8)TriMode;
    s[12] = TriSlope ? 1 : 0;
    s[13] = WaveFreqIdx;
    s[14] = OLED_Brightness;
    s[15] = OutPWM ? 1 : 0;
    s[16] = OutSIN ? 1 : 0;
    s[17] = OutUART ? 1 : 0;
    s[18] = GenFreqIdx;
    s[19] = GenDuty;
    s[20] = WaveType;
    s[21] = Lang;
    return UART_SETTINGS_LEN;
}

/* 应用 18 字节设置: 立即生效(不写 EEPROM) */
/* 主动上传当前设置(示波器上用编码器改了参数时调用) */
void UART_SendSettings(void)
{
    uint8 s[UART_SETTINGS_LEN];
    UART_GetSettings(s);
    UART_SendFrame(UART_T_SETTINGS, s, UART_SETTINGS_LEN);
}
void UART_ApplySettings(uint8 *s)
{
    Lsb = (uint16)s[0] | ((uint16)s[1] << 8);
    PlotMode = s[2] ? 1 : 0;
    ScaleH = (int8)s[3];
    ScaleV_Auto = s[4] ? 1 : 0;
    RulerVMax = (int16)((uint16)s[5] | ((uint16)s[6] << 8));
    RulerVMin = (int16)((uint16)s[7] | ((uint16)s[8] << 8));
    TriLevel = (int16)((uint16)s[9] | ((uint16)s[10] << 8));
    TriMode = (int8)s[11];
    TriSlope = s[12] ? 1 : 0;
    WaveFreqIdx = s[13] > 5 ? 2 : s[13];
    WaveFreq_Update();
    OLED_Brightness = s[14];
    OutPWM = s[15] ? 1 : 0;
    OutSIN = s[16] ? 1 : 0;
    OutUART = s[17] ? 1 : 0;
    GenFreqIdx = s[18];
    GenDuty = s[19];
    WaveType = s[20];
    Lang = s[21] ? 1 : 0;
    SetGenParams();

    check_Options(); /* 合法性检查 + Check_MinTimeInterval() */

    Output_Update(); /* 关闭时明确拉低到 0V */

    OLED_Write_Command(0x81);
    OLED_Write_Command(OLED_Brightness * 10);

    DisplayUpdate = 1;
    WaveUpdate = 1;
    ClearWave = 0;
    ADCInterrupt = 1;

    /* 参数可能被 check_Options() 修正，回传一份让上位机同步 */
    SettingsDirty = 1;
}

static void UART_HandleFrame(void)
{
    uint8 s[UART_SETTINGS_LEN];
    uint8 ok;

    switch (FrameType)
    {
    case UART_T_SET:
        if (FrameLen >= UART_SETTINGS_LEN)
        {
            UART_ApplySettings(FrameBuf);
            s[0] = 0;
            s[1] = 0;
        }
        else
        {
            s[0] = 1;
            s[1] = 0;
        }
        UART_SendFrame(UART_T_ACK, s, 2);
        break;

    case UART_T_SAVE:
        EA = 0;
        ok = Save_Options();
        EA = 1;
        s[0] = 0;
        s[1] = ok ? 1 : 0;
        UART_SendFrame(UART_T_ACK, s, 2);
        break;

    case UART_T_GET:
        UART_GetSettings(s);
        UART_SendFrame(UART_T_SETTINGS, s, UART_SETTINGS_LEN);
        break;

    case UART_T_REBOOT:
        /* 回复 ACK 后软复位到 ISP 监控程序区, 便于上位机自动烧录 */
        s[0] = 0;
        s[1] = 1;
        UART_SendFrame(UART_T_ACK, s, 2);
        Delay1000ms(); /* 给上位机 stcgal 一点时间先开始握手, 再软复位进 ISP */
        Delay500us();
        EA = 0;                /* cpv - 复位前关中断 */
        IAP_CONTR = 0x60; /* SWBS=1, SWRST=1: 软复位并从 ISP 监控区启动 */
        break;

    case UART_T_CAL_W: /* 写入时基校准表(42 字节) */
        if (FrameLen >= 42)
        {
            uint8 ci;
            for (ci = 0; ci < 21; ci++)
                CalTable[ci] = (uint16)FrameBuf[ci * 2] | ((uint16)FrameBuf[ci * 2 + 1] << 8);
            EA = 0;
            ok = Save_Options();
            EA = 1;
            s[0] = 0;
            s[1] = ok ? 1 : 0;
        }
        else
        {
            s[0] = 1;
            s[1] = 0;
        }
        UART_SendFrame(UART_T_ACK, s, 2);
        break;

    case UART_T_OUTO:   /* read output offset table: 21 x int16 */
    {
        uint8 oi;
        static __xdata uint8 obuf[42];
        for (oi = 0; oi < 21; oi++)
        {
            obuf[oi * 2] = (uint8)(OutOff[oi] & 0xFF);
            obuf[oi * 2 + 1] = (uint8)((uint16)OutOff[oi] >> 8);
        }
        UART_SendFrame(UART_T_OUTO, obuf, 42);
        break;
    }
    case UART_T_OUTW:   /* write output offset table */
        if (FrameLen >= 42)
        {
            uint8 oi;
            for (oi = 0; oi < 21; oi++)
                OutOff[oi] = (int16)((uint16)FrameBuf[oi * 2] | ((uint16)FrameBuf[oi * 2 + 1] << 8));
            WaveFreq_Update();
            SetGenParams();
            EA = 0;
            ok = Save_Options();
            EA = 1;
            s[0] = 0;
            s[1] = ok ? 1 : 0;
        }
        else
        {
            s[0] = 1;
            s[1] = 0;
        }
        UART_SendFrame(UART_T_ACK, s, 2);
        break;

    case UART_T_SCRL:   /* 读滚动位置: [0]offset [1]TriPos [2]running [3]宽度 */
        s[0] = (uint8)TriPosOffset;
        s[1] = TriPos;
        s[2] = ADCRunning ? 1 : 0;
        s[3] = (uint8)(SAMPLE_NUM - 50 - 1 - (int16)TriPos);  /* 最大正偏移 */
        UART_SendFrame(UART_T_SCRL, s, 4);
        break;

    case UART_T_RUN:    /* 运行/暂停: payload[0] 1=运行 0=暂停 */
        if (FrameLen >= 1)
        {
            ADCRunning = FrameBuf[0] ? 1 : 0;
            WaveUpdate = 0;
            ClearWave = 0;
            DisplayUpdate = 1;
            ADCInterrupt = 1;
            s[0] = 0;
            s[1] = 1;
        }
        else
        {
            s[0] = 1;
            s[1] = 0;
        }
        UART_SendFrame(UART_T_ACK, s, 2);
        break;

    case UART_T_SCRS:   /* 设滚动位置: payload[0] = int8 offset */
        if (FrameLen >= 1)
        {
            TriPosOffset = (int8)FrameBuf[0];
            WaveUpdate = 1;
            DisplayUpdate = 1;
            s[0] = 0;
            s[1] = 1;
        }
        else
        {
            s[0] = 1;
            s[1] = 0;
        }
        UART_SendFrame(UART_T_ACK, s, 2);
        break;

    case UART_T_INFO:
        s[0] = FW_VER_MAJOR;
        s[1] = FW_VER_MINOR;
        s[2] = FW_VER_PATCH;
        s[3] = UART_SETTINGS_LEN;
        s[4] = 28;
        s[5] = 0x03;
        s[6] = (uint8)GEN_TICK_US10;
        s[7] = 0;
        UART_SendFrame(UART_T_INFO, s, 8);
        break;

    case UART_T_CAL_R: /* 读取时基校准表 */
        {
            uint8 ci;
            for (ci = 0; ci < 21; ci++)
            {
                CalBuf[ci * 2] = (uint8)(CalTable[ci] & 0xFF);
                CalBuf[ci * 2 + 1] = (uint8)(CalTable[ci] >> 8);
            }
        }
        UART_SendFrame(UART_T_CAL_R, CalBuf, 42);
        break;

    case UART_T_TEST:
        if (FrameLen >= 2)
            TestDiv = (uint16)FrameBuf[0] | ((uint16)FrameBuf[1] << 8);
            TestTimeout = 0;
        s[0] = (uint8)(TestDiv & 0xFF);
        s[1] = (uint8)(TestDiv >> 8);
        UART_SendFrame(UART_T_ACK, s, 2);
        break;

    default:
        break;
    }
}

/* 主循环里调用: 解析接收帧并执行 */
void UART_Poll(void)
{
    uint8 b;

    while (UartRxTail != UartRxHead)
    {
        b = UartRx[UartRxTail];
        UartRxTail = UartRxTail + 1;
        if (UartRxTail >= UART_RX_SIZE)
            UartRxTail = 0;

        switch (ParseState)
        {
        case 0: /* 等 A5 */
            if (b == UART_HEAD0)
                ParseState = 1;
            break;

        case 1: /* 等 5A */
            if (b == UART_HEAD1)
                ParseState = 2;
            else if (b != UART_HEAD0)
                ParseState = 0;
            break;

        case 2: /* TYPE */
            FrameType = b;
            FrameSum = b;
            ParseState = 3;
            break;

        case 3: /* LENH */
            FrameLen = (uint16)b << 8;
            FrameSum += b;
            ParseState = 4;
            break;

        case 4: /* LENL */
            FrameLen |= b;
            FrameSum += b;
            FrameIdx = 0;
            if (FrameLen > 64)
                ParseState = 0;
            else if (FrameLen == 0)
                ParseState = 6;
            else
                ParseState = 5;
            break;

        case 5: /* PAYLOAD */
            FrameBuf[FrameIdx] = b;
            FrameIdx = FrameIdx + 1;
            FrameSum += b;
            if (FrameIdx >= FrameLen)
                ParseState = 6;
            break;

        case 6: /* SUM */
            ParseState = 0;
            if (b == FrameSum)
                UART_HandleFrame();
            break;

        default:
            ParseState = 0;
            break;
        }
    }
}

/* 串口1中断服务体: 发送移位 + 接收入队 (向量入口在 main.c) */
void UART_IsrBody(void)
{
    if (TI)
    {
        TI = 0;
        if (UartTxTail != UartTxHead)
        {
            SBUF = UartTx[UartTxTail];
            UartTxTail = UartTxTail + 1;
            if (UartTxTail >= UART_TX_SIZE)
                UartTxTail = 0;
        }
        else
            UartTxBusy = 0;
    }

    if (RI)
    {
        RI = 0;
        UartRx[UartRxHead] = SBUF;
        UartRxHead = UartRxHead + 1;
        if (UartRxHead >= UART_RX_SIZE)
            UartRxHead = 0;
        ADCInterrupt = 1; /* 让采样循环尽快退出，及时处理命令 */
    }
}
