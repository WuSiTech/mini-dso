/*
    uart.h

    cpv - UART1 binary protocol for sample streaming / settings control.

    Frame:  A5 5A TYPE LENH LENL PAYLOAD[LEN] SUM
            SUM = (TYPE + LENH + LENL + sum(PAYLOAD)) & 0xFF

    PC -> DSO:
      0x10  SET      18-byte settings block (same order as EEPROM)
      0x11  SAVE     empty -> ACK (result 0, extra = save status)
      0x12  GET      empty -> SETTINGS frame

    DSO -> PC:
      0x01  SAMPLE   28-byte header + N*2 raw ADC samples (little endian)
      0x02  ACK      [0]=result (0 ok / 1 fail) [1]=extra
      0x03  SETTINGS 18-byte settings block
*/

#ifndef UART_H
#define UART_H

#include "STC8A8K64S4A12.H"
#include "global.h"

#define UART_HEAD0      0xA5
#define UART_HEAD1      0x5A

#define UART_T_SAMPLE   0x01
#define UART_T_ACK      0x02
#define UART_T_SETTINGS 0x03
#define UART_T_SET      0x10
#define UART_T_SAVE     0x11
#define UART_T_GET      0x12
#define UART_T_REBOOT   0x14   /* 软复位进 ISP 下载模式(自动烧录用) */
#define UART_T_TEST     0x15   /* 设置 P1.1 测试方波分频(慢档校时基用), 参数=16bit 分频*/
#define UART_T_CAL_W    0x16   /* 写入时基校准表: 21 x uint16 小端 (42 字节) */
#define UART_T_CAL_R    0x17
#define UART_T_INFO   0x19
#define UART_T_SCRL   0x1A   /* 读取波形滚动位置 */
#define UART_T_SCRS   0x1B   /* 设置波形滚动位置(int8 偏移) */   /* 固件版本/能力 */   /* 读取时基校准表: 回复 42 字节 */   /* 设置 P1.1 测试方波分频(慢档校时基用), 参数=16bit 分频*/

#define UART_SETTINGS_LEN 22
#define UART_SAMP_NUM     100    /* sampled points sent to PC */

void UART_Init(void);
void UART_IsrBody(void);
void UART_Poll(void);
void UART_WriteByte(uint8 b);
void UART_SendFrame(uint8 type, uint8 *buf, uint16 len);
void UART_SendSamples(void);
uint8 UART_GetSettings(uint8 *s);
void UART_ApplySettings(uint8 *s);
void UART_SendSettings(void);

#endif
