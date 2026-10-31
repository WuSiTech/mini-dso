/* keys.c - 按键状态机 + 软件看门狗
   原实现把 Delay50ms()/Delay800ms_Long_Press()/Delay300ms_Double_Click()
   都放在 INT1 中断里, 一次按键最多阻塞 1.15 秒, 期间 Timer1(信号源)、Timer0、
   UART 全部停摆。现在中断只记录按下的时刻, 判定逻辑放到主循环。 */
#include "STC8A8K64S4A12.H"
#include "global.h"
#include "config_stc.h"
#include "keys.h"

#define KEY_DEBOUNCE_MS 10
#define KEY_LONG_MS     500

__xdata uint16 AppMs = 0;

static bit KeyDown = 0;
static bit KeyLongFired = 0;
static bit KeyRotated = 0;
static __xdata uint16 KeyDownMs = 0;

/* 计时在 Timer0(1ms) 里判定, 动作留给主循环执行 */
static bit PendLong = 0;
static bit PendSingle = 0;


static void Key_Long(void);
static void Key_Single(void);

/* ---------------- 按键 ---------------- */
void Key_Isr(void)
{
    KeyDown = 1;
    KeyLongFired = 0;
    KeyRotated = 0;
    KeyDownMs = AppMs;
    ADCInterrupt = 1;       /* 按下立即中止当前扫描 */
}

void Key_NoteRotate(void)
{
    KeyRotated = 1;
    if (KeyDown)
    {
        /* 按住旋转: 取消本次长按, 避免转到一半弹出设置 */
        KeyLongFired = 1;
        PendLong = 0;
    }
}

/* 每 1ms 由 Timer0 调用: 只做计时/判定, 不执行动作
   规则: 松开时 时长>=20ms -> 立即算一次单击(不再等双击窗口) */
void Key_Tick(void)
{
    uint16 d;

    if (KeyDown)
    {
        if (EC11_KEY)                    /* 已松开 */
        {
            KeyDown = 0;
            d = (uint16)(AppMs - KeyDownMs);

            if (KeyLongFired)
                KeyLongFired = 0;        /* 长按动作已排队 */
            else if (KeyRotated)
                KeyRotated = 0;          /* 按住旋转过, 不算点击 */
            else if (d >= KEY_DEBOUNCE_MS)
            {
                PendSingle = 1;          /* 立刻排队: 下一圈主循环就执行 */
                ADCInterrupt = 1;
            }
        }
        else if (!KeyLongFired && !KeyRotated &&
                 (uint16)(AppMs - KeyDownMs) >= KEY_LONG_MS)
        {
            KeyLongFired = 1;
            PendLong = 1;                /* 按住满 500ms 立即排队 */
            ADCInterrupt = 1;            /* 打断当前采样 */
        }
    }
}

/* 主循环调用: 执行排队的动作 */
void Key_Poll(void)
{
    if (PendLong)
    {
        PendLong = 0;
        Key_Long();
    }
    else if (PendSingle)
    {
        PendSingle = 0;
        Key_Single();
    }
}

/* 长按: 主界面<->设置; 信息页/光标页 -> 返回设置 */
static void Key_Long(void)
{
    if (InSettings && InfoPage)
    {
        InfoPage = 0;
        ClearDisplay = 1;      /* 返回设置前整屏重绘 */
        DisplayUpdate = 1;
        ADCInterrupt = 1;
        return;
    }
    if (InSettings && CursorPage)
    {
        CursorPage = 0;
        ClearDisplay = 1;
        DisplayUpdate = 1;
        ADCInterrupt = 1;
        return;
    }
    InSettings = !InSettings;

    if (InSettings)
    {
        DisplayUpdate = 1;
        UpdateVbat = 1;
        TF0 = 0;
        IE0 = 0;
        EX0 = 1;
    }
    else
    {
        TF0 = 0;
        WaveFreq = 0;
        TriFail = 0;
        VMax = 0;
        VMin = 0;
        DisplayUpdate = 1;
        WaveUpdate = 1;
        ClearWave = 0;
    }
    ADCInterrupt = 1;
}

/* 单击: 主界面 暂停/继续; 光标页 -> 返回设置 */
static void Key_Single(void)
{
    if (InSettings)
        return;

    if (CursorPage)
    {
        CursorPage = 0;
        DisplayUpdate = 1;
        ADCInterrupt = 1;
        return;
    }

    ADCRunning = !ADCRunning;
    if (ADCRunning)
    {
        WaveUpdate = 1;
        ClearWave = 1;
    }
    else
    {
        DisplayUpdate = 1;
        WaveUpdate = 0;
        ClearWave = 0;
    }
    ADCInterrupt = 1;
    IE0 = 0;
    IE1 = 0;
}

