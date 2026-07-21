import sensor
import lcd
import time
import os
from fpioa_manager import fm
from machine import UART

print("==============================")
print("K210 INTERFACE CHECK")
print("==============================")

try:
    print("ROOT:", os.listdir("/"))
except Exception as e:
    print("ROOT ERROR:", e)

try:
    print("FLASH:", os.listdir("/flash"))
except Exception as e:
    print("FLASH ERROR:", e)

try:
    print("SD:", os.listdir("/sd"))
except Exception as e:
    print("SD ERROR:", e)

sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.QVGA)
sensor.set_hmirror(0)
sensor.set_vflip(0)
sensor.skip_frames(time=1500)
print("CAMERA OK")

lcd.init()
lcd.rotation(0)
print("LCD OK")

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
print("UART1 TX OK: GPIO7 115200 8N1")
print("F103 should flash 3 times every 6 seconds")

last_send = time.ticks_ms() - 6000

while True:
    img = sensor.snapshot()
    img.draw_string(4, 4, "INTERFACE CHECK", color=255, scale=2)
    img.draw_cross(160, 120, color=255, size=12)
    lcd.display(img)

    now = time.ticks_ms()
    if time.ticks_diff(now, last_send) >= 6000:
        uart.write("D:3\n")
        print("UART SEND: D:3")
        last_send = now
