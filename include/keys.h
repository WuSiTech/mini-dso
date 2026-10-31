/* keys.h - key state machine (INT1 records event, main loop decides) */
#ifndef KEYS_H
#define KEYS_H

#include "STC8A8K64S4A12.H"

extern __xdata uint16 AppMs;   /* 1ms counter maintained by Timer0 ISR */

void Key_Isr(void);
void Key_Poll(void);
void Key_Tick(void);
void Key_NoteRotate(void);

#endif
