/* refgen_f411.c - STM32F411CEU6 (Black Pill): HSE 25MHz -> PLL 100MHz
   TIM2 CH1 PWM 1kHz 50% on PA0 (AF1)  作为 Mini-DSO 的绝对频率基准 */
#include <stdint.h>

#define REG32(a) (*(volatile uint32_t *)(a))

#define RCC_BASE      0x40023800
#define RCC_CR        REG32(RCC_BASE + 0x00)
#define RCC_PLLCFGR   REG32(RCC_BASE + 0x04)
#define RCC_CFGR      REG32(RCC_BASE + 0x08)
#define RCC_AHB1ENR   REG32(RCC_BASE + 0x30)
#define RCC_APB1ENR   REG32(RCC_BASE + 0x40)

#define FLASH_ACR     REG32(0x40023C00)

#define GPIOA_MODER   REG32(0x40020000)
#define GPIOA_OSPEEDR REG32(0x40020008)
#define GPIOA_AFRL    REG32(0x40020020)

#define TIM2_CR1      REG32(0x40000000)
#define TIM2_CCMR1    REG32(0x40000018)
#define TIM2_CCER     REG32(0x40000020)
#define TIM2_PSC      REG32(0x40000028)
#define TIM2_ARR      REG32(0x4000002C)
#define TIM2_CCR1     REG32(0x40000034)
#define TIM2_EGR      REG32(0x40000014)

extern uint32_t _estack;

void Reset_Handler(void);

__attribute__((section(".isr_vector"), used))
void (*const vectors[])(void) = {
    (void (*)(void))(&_estack),
    Reset_Handler,
};

void Reset_Handler(void)
{
    /* 1) HSE 25MHz */
    RCC_CR |= (1u << 16);
    while (!(RCC_CR & (1u << 17)))
        ;

    /* 2) 电压调节/时钟: 100MHz 需要 5 wait states */
    FLASH_ACR = 5u | (1u << 8) | (1u << 9) | (1u << 10);

    /* 3) PLL: M=25 N=200 P=2 -> 25/25*200/2 = 100MHz */
    RCC_PLLCFGR = (25u << 0) | (200u << 6) | (0u << 16) | (1u << 22) /* PLLSRC=HSE */
                  | (4u << 24);                                      /* PLLQ=4 -> 50MHz USB */
    RCC_CR |= (1u << 24);                                            /* PLLON */
    while (!(RCC_CR & (1u << 25)))
        ;

    /* 4) AHB/1, APB1/2, APB2/1 -> Sysclk 100MHz, APB1 50MHz(TIM2=100MHz) */
    RCC_CFGR = (0u << 4) | (5u << 10) | (0u << 13);
    RCC_CFGR |= 2u;                     /* SW = PLL */
    while (((RCC_CFGR >> 2) & 3u) != 2u)
        ;

    /* 5) GPIOA + TIM2 时钟 */
    RCC_AHB1ENR |= (1u << 0);           /* GPIOAEN */
    RCC_APB1ENR |= (1u << 0);           /* TIM2EN */

    /* 6) PA0 = AF1 (TIM2_CH1), 高速 */
    GPIOA_MODER = (GPIOA_MODER & ~3u) | 2u;
    GPIOA_OSPEEDR = (GPIOA_OSPEEDR & ~3u) | 3u;
    GPIOA_AFRL = (GPIOA_AFRL & ~0xFu) | 1u;

    /* 7) TIM2: 100MHz/(99+1)=1MHz, ARR=999 -> 1kHz, CCR=500 -> 50% */
    TIM2_PSC = 99;
    TIM2_ARR = 999;
    TIM2_CCR1 = 500;
    TIM2_CCMR1 = (6u << 4);             /* PWM mode 1 */
    TIM2_CCER = (1u << 0);
    TIM2_EGR = 1u;
    TIM2_CR1 = (1u << 0);

    while (1)
        __asm__ volatile("nop");
}
