from fpioa_manager import fm
from machine import UART
import time

# Confirm the Makerobo external TX connector mapping.
fm.register(7, fm.fpioa.UART1_TX, force=True)

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

while True:
    uart.write(b'L')
    print("GPIO7 sent L: F103 LED ON for 2 seconds")
    time.sleep_ms(2000)

    uart.write(b'C')
    print("GPIO7 sent C: F103 LED OFF for 2 seconds")
    time.sleep_ms(2000)
