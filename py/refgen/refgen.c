/* refgen.c - STM32F103C8T6: HSE 8MHz -> PLL 72MHz -> TIM2 CH1 PWM 1kHz on PA0
   用于给 Mini-DSO 提供精确 1 kHz 基准(晶振 ±20ppm) */
#include <stdint.h>

#define REG32(a) (*(volatile uint32_t *)(a))

/* RCC */
#define RCC_CR        REG32(0x40021000)
#define RCC_CFGR      REG32(0x40021004)
#define RCC_APB2ENR   REG32(0x40021018)
#define RCC_APB1ENR   REG32(0x4002101C)
/* GPIOA */
#define GPIOA_CRL     REG32(0x40010800)
/* TIM2 (APB1) */
#define TIM2_CR1      REG32(0x40000000)
#define TIM2_CCMR1    REG32(0x40000018)
#define TIM2_CCER     REG32(0x40000020)
#define TIM2_PSC      REG32(0x40000028)
#define TIM2_ARR      REG32(0x4000002C)
#define TIM2_CCR1     REG32(0x40000034)
#define TIM2_EGR      REG32(0x40000014)

extern uint32_t _estack;

void Reset_Handler(void);

/* 向量表: 放在 0x08000000 */
__attribute__((section(".isr_vector"), used))
void (*const vectors[])(void) = {
    (void (*)(void))(&_estack),
    Reset_Handler,
};

static void delay(volatile uint32_t n)
{
    while (n--)
        __asm__ volatile("nop");
}

void Reset_Handler(void)
{
    /* 1) HSE 8MHz */
    RCC_CR |= (1u << 16);                 /* HSEON */
    while (!(RCC_CR & (1u << 17)))        /* HSERDY */
        ;
    /* 2) Flash 等待周期: 72MHz 需要 2WS + 预取 (缺这个会跑飞!) */
    REG32(0x40022000) = 0x12;             /* FLASH_ACR: PRFTBE | LATENCY=2 */

    /* 3) PLL: HSE/1 * 9 = 72MHz, AHB/1, APB1/2, APB2/1 */
    RCC_CFGR = (1u << 16)                 /* PLLSRC = HSE */
               | (7u << 18)               /* PLLMUL = x9 */
               | (4u << 8)                /* PPRE1 = /2 */
               | (0u << 11);              /* PPRE2 = /1 */
    RCC_CR |= (1u << 24);                 /* PLLON */
    while (!(RCC_CR & (1u << 25)))        /* PLLRDY */
        ;
    RCC_CFGR = (RCC_CFGR & ~3u) | 2u;     /* SW = PLL */
    while (((RCC_CFGR >> 2) & 3u) != 2u)  /* SWS = PLL */
        ;

    /* 3) 时钟: GPIOA + TIM2 */
    RCC_APB2ENR |= (1u << 2);             /* IOPAEN */
    RCC_APB1ENR |= (1u << 0);             /* TIM2EN */

    /* 4) PA0 = 复用推挽输出 (MODE=11, CNF=10 -> 0xB) */
    GPIOA_CRL = (GPIOA_CRL & ~0xFu) | 0xBu;

    /* 5) TIM2: f = 72MHz / ((PSC+1) * (ARR+1)), 50% 占空比
       默认 1kHz (PSC=71, ARR=999)；可用 -DREFGEN_PSC=.. -DREFGEN_ARR=.. 覆盖 */
#ifndef REFGEN_PSC
#define REFGEN_PSC 71
#endif
#ifndef REFGEN_ARR
#define REFGEN_ARR 999
#endif
    TIM2_PSC = REFGEN_PSC;
    TIM2_ARR = REFGEN_ARR;
    TIM2_CCR1 = (REFGEN_ARR + 1) / 2;
    TIM2_CCMR1 = (6u << 4);               /* OC1M = PWM mode 1 */
    TIM2_CCER = (1u << 0);                /* CC1E */
    TIM2_EGR = 1u;                        /* UG: 载入预分频/ARR */
    TIM2_CR1 = (1u << 0);                 /* CEN */

    while (1)
    {
        /* 空转: 只输出 1 kHz 方波 */
        delay(100000);
    }
}
