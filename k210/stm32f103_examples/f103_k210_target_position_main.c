/*
 * STM32F103C8T6 + K210 anti-shake target position receiver.
 *
 * USART1: PA9 = TX, PA10 = RX, 115200 8N1
 * Blue Pill LED: PC13, active low
 *
 * K210 messages:
 *   A:5
 *   P:5,-32,7,2500,85
 *   H:5
 *   N:5
 *   D:5
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
#define LINE_BUFFER_SIZE 64U
#define CENTER_DEAD_ZONE 15

void SystemInit(void)
{
    RCC_CR |= (1U << 0);
    while ((RCC_CR & (1U << 1)) == 0U) {
    }
    RCC_CFGR &= ~0x3U;
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
    GPIOC_BRR = (1U << LED_PIN);
}

static void led_off(void)
{
    GPIOC_BSRR = (1U << LED_PIN);
}

static void led_toggle(void)
{
    GPIOC_ODR ^= (1U << LED_PIN);
}

static void show_received_digit(uint8_t digit)
{
    led_off();
    delay_ms(400U);

    if (digit == 0U) {
        led_on();
        delay_ms(1000U);
        led_off();
        delay_ms(600U);
        return;
    }

    for (uint8_t count = 0U; count < digit; ++count) {
        led_on();
        delay_ms(180U);
        led_off();
        delay_ms(260U);
    }

    delay_ms(600U);
}

static void gpio_and_usart1_init(void)
{
    RCC_APB2ENR |= (1U << 0) | (1U << 2) | (1U << 4) | (1U << 14);

    GPIOC_CRH &= ~(0xFU << 20);
    GPIOC_CRH |=  (0x2U << 20);
    led_off();

    GPIOA_CRH &= ~((0xFU << 4) | (0xFU << 8));
    GPIOA_CRH |=  ((0xBU << 4) | (0x4U << 8));

    USART1_BRR = 0x45U;
    USART1_CR1 = (1U << 13) | (1U << 3) | (1U << 2);
}

static void usart1_write_byte(uint8_t value)
{
    while ((USART1_SR & (1U << 7)) == 0U) {
    }
    USART1_DR = value;
}

static int32_t parse_integer(char **text)
{
    int32_t sign = 1;
    int32_t value = 0;

    if (**text == '-') {
        sign = -1;
        ++(*text);
    } else if (**text == '+') {
        ++(*text);
    }

    while (**text >= '0' && **text <= '9') {
        value = value * 10 + (int32_t)(**text - '0');
        ++(*text);
    }

    return value * sign;
}

static void process_line(char *line)
{
    if (line[0] == 'P' && line[1] == ':') {
        char *cursor = &line[2];

        /* Target digit is parsed for protocol validation. */
        (void)parse_integer(&cursor);
        if (*cursor != ',') {
            led_off();
            return;
        }

        ++cursor;
        int32_t error_x = parse_integer(&cursor);

        if (error_x < -CENTER_DEAD_ZONE) {
            /* Target is left of image center. */
            led_on();
        } else if (error_x > CENTER_DEAD_ZONE) {
            /* Target is right of image center. */
            led_toggle();
        } else {
            /* Target is centered. */
            led_off();
        }
    } else if (line[0] == 'A' && line[1] == ':') {
        /* Target acquired; the following P packet sets direction. */
        led_off();
    } else if (line[0] == 'H' && line[1] == ':') {
        /* Do not reuse stale direction while the camera is blurred. */
        led_off();
    } else if (line[0] == 'N' && line[1] == ':') {
        /* Target lost. Future motor control must stop correction here. */
        led_off();
    } else if (line[0] == 'D' && line[1] == ':' &&
               line[2] >= '0' && line[2] <= '9') {
        show_received_digit((uint8_t)(line[2] - '0'));
    }
}

int main(void)
{
    char line_buffer[LINE_BUFFER_SIZE];
    uint8_t line_length = 0U;

    gpio_and_usart1_init();

    for (uint32_t i = 0U; i < 3U; ++i) {
        led_on();
        delay_ms(180U);
        led_off();
        delay_ms(180U);
    }

    for (;;) {
        uint32_t status = USART1_SR;

        if ((status & ((1U << 3) | (1U << 2) | (1U << 1))) != 0U) {
            /* Clear overrun/noise/framing errors by reading DR. */
            (void)USART1_DR;
            line_length = 0U;
            continue;
        }

        if ((status & (1U << 5)) != 0U) {
            uint8_t value = (uint8_t)USART1_DR;
            usart1_write_byte(value);

            if (value == (uint8_t)'\r') {
                continue;
            }

            if (value == (uint8_t)'\n') {
                line_buffer[line_length] = '\0';
                process_line(line_buffer);
                line_length = 0U;
            } else if (line_length < (LINE_BUFFER_SIZE - 1U)) {
                line_buffer[line_length++] = (char)value;
            } else {
                line_length = 0U;
            }
        }
    }
}
