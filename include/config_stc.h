/*Register of MCU and Pins defined here*/

#ifndef CONFIG_STC_H
#define CONFIG_STC_H


#include "STC8A8K64S4A12.H" // cpv
//#define DEBUG

/* ADC采样通道设置
   ADC Channel Setup */
//#define ADC_DSO ADC_CHS_06
//#define ADC_BAT ADC_CHS_04
// cpv - moved on 56dz.com board
#define ADC_DSO ADC_CHS_01  /* signal input, P06 -> P01: AD1 */
#define ADC_BAT ADC_CHS_14  /* battery, P04 -> P14: AD14 */

// cpv - new on 56dz.com board
#define PWM0_OUT  P10  /* cpv - PCA 8-bit PWM (CCP0), RC 滤波后为 9 kHz 正弦 */
#define PWM1_OUT  P11  /* cpv - 9 kHz 方波 ('PWM') 输出 */


/* EC11编码器管脚设置
   Setup EC11 Encoder Pin */
/* cpv 
sbit EC11_KEY = P3 ^ 3; //编码器按键连接外部中断1 connect to External Interrupt 1
sbit EC11_A = P3 ^ 2;   //编码器A脉冲连接外部中断0 connect to External Interrupt 0
sbit EC11_B = P3 ^ 4;   //编码器B脉冲连接普通IO口 connect to GPIO
*/
// cpv
//__sbit __at (0xb0+3) EC11_KEY; // cpv - P33 - 编码器按键连接外部中断1 connect to External Interrupt 1
//__sbit __at (0xb0+2) EC11_A;   // cpv - P32 - 编码器A脉冲连接外部中断0 connect to External Interrupt 0
//__sbit __at (0xb0+4) EC11_B;   // cpv - P34 - 编码器B脉冲连接普通IO口 connect to GPIO
// cpv better this way?
#define EC11_KEY  P33
#define EC11_A  P32
#define EC11_B  P34

/* 采样运行指示灯
   Indicator for sampling running */
// cpv sbit P_Ready = P1 ^ 1;
//__sbit __at (0x90+1) P_Ready; // cpv
// cpv better this way?
#define P_Ready  P26  /* moved on 56dz.com board */

/*  OLED Pin */
/* cpv
sbit OLED_SCLK = P2 ^ 7; //时钟（D0/SCLK）
sbit OLED_SDIN = P2 ^ 6; //数据（D1/MOSI）
sbit OLED_RST = P2 ^ 5;  //复位（RES）
sbit OLED_DC = P2 ^ 4;   //数据/命令控制（DC）
sbit OLED_CS = P2 ^ 3;   //片选（CS）
*/
// cpv
//__sbit __at (0xa0+7) OLED_SCLK; //时钟（D0/SCLK）
//__sbit __at (0xa0+6) OLED_SDIN; //数据（D1/MOSI）
//__sbit __at (0xa0+5) OLED_RST;  //复位（RES）
//__sbit __at (0xa0+4) OLED_DC;   //数据/命令控制（DC）
//__sbit __at (0xa0+3) OLED_CS;   //片选（CS）
// cpv better this way?
#define OLED_SCLK  P25  /* D0, moved on 56dz.com board (was P27) */
#define OLED_SDIN  P23  /* D1, moved on 56dz.com board (was P26) */
#define OLED_RST  P22  /* RES, moved on 56dz.com board (was P25) */
#define OLED_DC  P21  /* moved on 56dz.com board (was P24) */
#define OLED_CS  P42  /* moved on 56dz.com board (was P23) */


#ifdef DEBUG
// cpv sbit P15 = P1 ^ 5;
#endif

#endif