from fpioa_manager import fm
from machine import UART
import time

# CanMV K210 hardware UART1 TX is mapped to GPIO35.
fm.register(35, fm.fpioa.UART1_TX, force=True)

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
    print("UART1 sent: L  -> F103 LED should be ON")
    time.sleep_ms(2000)

    uart.write(b'C')
    print("UART1 sent: C  -> F103 LED should be OFF")
    time.sleep_ms(2000)
