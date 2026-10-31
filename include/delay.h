#ifndef DELAY_H
#define DELAY_H

//cpv #include "reg51.h"
#include "STC8A8K64S4A12.H" // cpv
#include "config_stc.h"
#include "global.h"


bit Delay800ms_Long_Press(void);
bit Delay300ms_Double_Click(void);
void Delay500us(void);
void Delay5ms(void);
void Delay50ms(void);
void Delay200ms(void);
void Delay1000ms(void);
void Delay3us(void);
void Delay2us(void);
void Delay10us(void);
void Delay19971us(void);
void Delay7971us(void);
void Delay3971us(void);
void Delay1971us(void);
void Delay771us(void);
void Delay371us(void);
void Delay171us(void);
void Delay51us(void);
void Delay18us(void);
void Delay6us(void);
void Delay1us(void);
void Delay05us(void);
void DelayUs(uint16 us);
void DelayFine(uint16 n);

#endif