from fpioa_manager import fm
from machine import UART
import time

# Common UART-capable GPIO mappings used by K210 development boards.
CANDIDATE_TX_PINS = [35, 34, 33, 32, 10, 11, 6, 7, 4, 5]

while True:
    for pin in CANDIDATE_TX_PINS:
        print("================================")
        print("Testing external UART TX on GPIO%d" % pin)
        print("Watch the STM32F103 PC13 LED now")

        fm.register(pin, fm.fpioa.UART1_TX, force=True)
        uart = UART(
            UART.UART1,
            115200,
            8,
            None,
            1,
            timeout=1000,
            read_buf_len=4096
        )

        time.sleep_ms(200)

        # Correct TX mapping makes the F103 LED turn on/off four times.
        for i in range(4):
            uart.write(b'L')
            time.sleep_ms(1000)
            uart.write(b'C')
            time.sleep_ms(1000)

        uart.deinit()
        fm.unregister(pin)
        del uart
        time.sleep_ms(500)

    print("Scan complete. Repeating in 3 seconds.")
    time.sleep_ms(3000)
