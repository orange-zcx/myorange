/*
 * STM32F103C8T6 + K210 UART receiver
 * No CubeMX/.ioc or HAL package is required.
 *
 * USART1: PA9 = TX, PA10 = RX, 115200 8N1
 * Blue Pill LED: PC13, active low
 */

#include <stdint.h>

#define REG32(address) (*(volatile uint32_t *)(address))

#define RCC_CR          REG32(0x40021000U)
#define RCC_CFGR        REG32(0x40021004U)
#define RCC_APB2ENR     REG32(0x40021018U)

#define GPIOA_CRH       REG32(0x40010804U)
#define GPIOC_CRH       REG32(0x40011004U)
#define GPIOC_ODR       REG32(0x4001100CU)
#define GPIOC_BSRR      REG32(0x40011010U)
#define GPIOC_BRR       REG32(0x40011014U)

#define USART1_SR       REG32(0x40013800U)
#define USART1_DR       REG32(0x40013804U)
#define USART1_BRR      REG32(0x40013808U)
#define USART1_CR1      REG32(0x4001380CU)

#define LED_PIN         13U

void SystemInit(void)
{
    /* Keep the reset-default 8 MHz HSI clock. */
    RCC_CR |= (1U << 0);             /* HSION */
    while ((RCC_CR & (1U << 1)) == 0U) {
    }
    RCC_CFGR &= ~0x3U;               /* SYSCLK = HSI */
}

static void delay_ms(uint32_t milliseconds)
{
    while (milliseconds-- > 0U) {
        for (volatile uint32_t i = 0U; i < 800U; ++i) {
            __asm volatile ("nop");
        }
    }
}

static void led_on(void)
{
    GPIOC_BRR = (1U << LED_PIN);     /* Blue Pill LED is active low. */
}

static void led_off(void)
{
    GPIOC_BSRR = (1U << LED_PIN);
}

static void led_toggle(void)
{
    GPIOC_ODR ^= (1U << LED_PIN);
}

static void gpio_and_usart1_init(void)
{
    /* AFIO, GPIOA, GPIOC and USART1 clocks. */
    RCC_APB2ENR |= (1U << 0) | (1U << 2) | (1U << 4) | (1U << 14);

    /* PC13: 2 MHz general-purpose push-pull output. */
    GPIOC_CRH &= ~(0xFU << 20);
    GPIOC_CRH |=  (0x2U << 20);
    led_off();

    /* PA9: alternate-function push-pull, 50 MHz. */
    /* PA10: floating input. */
    GPIOA_CRH &= ~((0xFU << 4) | (0xFU << 8));
    GPIOA_CRH |=  ((0xBU << 4) | (0x4U << 8));

    /* 8 MHz / 115200 baud = BRR 0x45 (about 0.64% error). */
    USART1_BRR = 0x45U;
    USART1_CR1 = (1U << 13) | (1U << 3) | (1U << 2); /* UE, TE, RE */
}

static void usart1_write_byte(uint8_t value)
{
    while ((USART1_SR & (1U << 7)) == 0U) {  /* TXE */
    }
    USART1_DR = value;
}

int main(void)
{
    gpio_and_usart1_init();

    /* Three flashes prove that the new program started successfully. */
    for (uint32_t i = 0U; i < 3U; ++i) {
        led_on();
        delay_ms(180U);
        led_off();
        delay_ms(180U);
    }

    for (;;) {
        if ((USART1_SR & (1U << 5)) != 0U) {  /* RXNE */
            uint8_t value = (uint8_t)USART1_DR;

            /* Echo the received byte for later diagnostics. */
            usart1_write_byte(value);

            if (value == (uint8_t)'L') {
                led_on();
            } else if (value == (uint8_t)'C') {
                led_off();
            } else if (value == (uint8_t)'R') {
                led_toggle();
            }
        }
    }
}
