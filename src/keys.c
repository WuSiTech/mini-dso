/* keys.c - 按键状态机 + 软件看门狗
   原实现把 Delay50ms()/Delay800ms_Long_Press()/Delay300ms_Double_Click()
   都放在 INT1 中断里, 一次按键最多阻塞 1.15 秒, 期间 Timer1(信号源)、Timer0、
   UART 全部停摆。现在中断只记录按下的时刻, 判定逻辑放到主循环。 */
#include "STC8A8K64S4A12.H"
#include "global.h"
#include "config_stc.h"
#include "settings.h"
#include "keys.h"

#define KEY_DEBOUNCE_MS 10
#define KEY_LONG_MS     500
#define KEY_DBL_MS      300

__xdata uint16 AppMs = 0;

static bit KeyDown = 0;
static bit KeyLongFired = 0;
static bit KeyRotated = 0;
static __xdata uint16 KeyDownMs = 0;

/* 计时在 Timer0(1ms) 里判定, 动作留给主循环执行 */
static bit PendLong = 0;
static bit PendSingle = 0;
static bit PendDouble = 0;
static __xdata uint8 ClickCnt = 0;
static __xdata uint16 LastClickMs = 0;


static void Key_Long(void);
static void Key_Single(void);
static void Key_DoubleSettings(void);

/* ---------------- 按键 ---------------- */
void Key_Isr(void)
{
    if (!KeyDown)
    {
        KeyDown = 1;
        KeyDownMs = AppMs;   /* 只有真正的"按下沿"才重置计时(抖动不算) */
        KeyLongFired = 0;
        KeyRotated = 0;
    }
    ADCInterrupt = 1;        /* 按下立即中止当前扫描 */
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
                /* 设置页里: 300ms 内按两下 = 取消修改; 主页不识别双击 */
                if (InSettings)
                {
                    if (ClickCnt && (uint16)(AppMs - LastClickMs) <= KEY_DBL_MS)
                    {
                        ClickCnt = 0;
                        PendDouble = 1;
                    }
                    else
                    {
                        ClickCnt = 1;
                        LastClickMs = AppMs;
                    }
                }
                else
                {
                    PendSingle = 1;
                }
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
    else if (PendDouble)
    {
        PendDouble = 0;
        Key_DoubleSettings();
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
    if (InSettings && CalPage)
    {
        /* 校准表页长按: 立即写 EEPROM 并提示保存成功 */
        EA = 0;
        ShowSaveMsg = Save_Options() ? 1 : 0;
        EA = 1;
        if (!ShowSaveMsg)
            ShowCancelMsg = 1;   /* 保存失败也用提示区显示 */
        OptionChanged = 0;
        CalPage = 0;
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
        /* 恢复: 保留旧波形不清屏(慢时基一轮 4.4s, 空白会以为没反应),
           状态栏立即变成 Run, 扫描完成后再刷新波形 */
        WaveUpdate = 0;
        ClearWave = 0;
        DisplayUpdate = 1;
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

/* 设置页里连按两下: 放弃修改, 从 EEPROM 重新读取(参数 + 校准表) */
static void Key_DoubleSettings(void)
{
    if (!InSettings)
        return;

    {
        uint8 keepLang = Lang;
        uint8 wasPage = (CalPage || InfoPage || CursorPage) ? 1 : 0;

        Read_Options();              /* 参数 + 校准表回滚 */
        Lang = keepLang;             /* 界面语言保持当前选择 */
        CancelExit = wasPage ? 1 : 2; /* 子页 -> 回列表; 列表 -> 回主界面 */
    }
    OptionChanged = 0;
    SettingsDirty = 1;
    CalPage = 0;
    InfoPage = 0;
    CursorPage = 0;
    ShowCancelMsg = 1;
    ClearDisplay = 1;
    DisplayUpdate = 1;
    ADCInterrupt = 1;
}
