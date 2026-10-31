/* keil_main.c - STM32F103C8T6 Blue Pill: HSE 8MHz -> PLL 72MHz
   TIM2 CH1 PWM 1kHz 50% on PA0 (AF push-pull)
   给 Mini-DSO 做绝对频率基准(晶振 ±20ppm)

   Keil v5 用法:
   1) Project -> New uVision Project -> 选 STM32F103C8
   2) 勾选 CMSIS/CORE + Device/Startup (Startup 文件保留)
   3) 把这个文件加入工程, 替换默认的 main.c
   4) 编译(F7) -> 下载(F8), ST-Link 接 SWD
   (本文件只用寄存器, 不依赖标准外设库/HAL)
*/
#include <stdint.h>

#define REG32(a) (*(volatile uint32_t *)(a))

#define RCC_CR        REG32(0x40021000)
#define RCC_CFGR      REG32(0x40021004)
#define RCC_APB2ENR   REG32(0x40021018)
#define RCC_APB1ENR   REG32(0x4002101C)

#define GPIOA_CRL     REG32(0x40010800)

#define TIM2_CR1      REG32(0x40000000)
#define TIM2_CCMR1    REG32(0x40000018)
#define TIM2_CCER     REG32(0x40000020)
#define TIM2_PSC      REG32(0x40000028)
#define TIM2_ARR      REG32(0x4000002C)
#define TIM2_CCR1     REG32(0x40000034)
#define TIM2_EGR      REG32(0x40000014)

int main(void)
{
    /* 1) HSE 8MHz 起振 */
    RCC_CR |= (1u << 16);                 /* HSEON */
    while (!(RCC_CR & (1u << 17)))        /* HSERDY */
        ;

    /* 2) PLL: HSE/1 * 9 = 72MHz, APB1/2 (TIM2 时钟 = 72MHz) */
    RCC_CFGR = (1u << 16)                 /* PLLSRC = HSE */
               | (7u << 18)               /* PLLMUL = x9 */
               | (0u << 8)                /* PPRE1 = /2 */
               | (0u << 11);              /* PPRE2 = /1 */
    RCC_CR |= (1u << 24);                 /* PLLON */
    while (!(RCC_CR & (1u << 25)))        /* PLLRDY */
        ;
    RCC_CFGR = (RCC_CFGR & ~3u) | 2u;     /* SW = PLL */
    while (((RCC_CFGR >> 2) & 3u) != 2u)  /* SWS = PLL */
        ;

    /* 3) 时钟使能 */
    RCC_APB2ENR |= (1u << 2);             /* IOPAEN */
    RCC_APB1ENR |= (1u << 0);             /* TIM2EN */

    /* 4) PA0 = 复用推挽输出 (MODE=11 CNF=10 -> 0xB) */
    GPIOA_CRL = (GPIOA_CRL & ~0xFu) | 0xBu;

    /* 5) TIM2: 72MHz/(71+1)=1MHz, ARR=999 -> 1kHz, CCR=500 -> 50% */
    TIM2_PSC = 71;
    TIM2_ARR = 999;
    TIM2_CCR1 = 500;
    TIM2_CCMR1 = (6u << 4);               /* OC1M = PWM mode 1 */
    TIM2_CCER = (1u << 0);                /* CC1E */
    TIM2_EGR = 1u;                        /* UG */
    TIM2_CR1 = (1u << 0);                 /* CEN */

    while (1)
        __asm volatile("nop");
}
