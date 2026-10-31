#ifndef CHART_H
#define CHART_H


#include "STC8A8K64S4A12.H" // cpv

#include "ssd1306.h"
#include "adc_stc8.h"
#include "settings.h"
#include "config_stc.h"


/* 屏幕上波形显示区域
   Region for waveform on display*/
#define CHART_H_MAX 126 
#define CHART_H_MIN 26
#define CHART_V_MAX 52
#define CHART_V_MIN 8

void PlotChart(void);
void PlotSettings(void);
void PlotSaveStatus(bit _saveStatus);
void GetWaveData(void);
bit GetTriggerPos(uint16 d1, uint16 d2, uint16 dTrigger, bit triSlope);
//cpv uint16 Convert_mv_ADC(uint16 mv, uint16 *BGV, uint16 BGADC, uint16 lsb);
uint16 Convert_mv_ADC(uint16 mv, uint16 BGV, uint16 BGADC, uint16 lsb);
void AnalyseData();
void PlotWave();
void OLED_DrawCNStr(uint8 x, uint8 y, const unsigned char code *str);
void OLED_DrawCNStr8(uint8 x, uint8 y, const unsigned char code *str);
void PlotInfoPage(void);
void PlotSplash(void);
extern uint16 plotADCMax, plotADCMin; //cpv - 屏幕纵向量程对应的 ADC 端点(供上位机换算 mV)

#endif