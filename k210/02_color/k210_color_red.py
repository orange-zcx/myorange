import sensor, image, time, lcd

# Hardware LCD orientation.
lcd.init()
lcd.rotation(2)
lcd.clear(lcd.BLACK)

# Camera initialization.
sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)   # 320 x 240
sensor.set_hmirror(1)
sensor.set_vflip(1)
sensor.skip_frames(time=2000)

# Keep colors stable after startup.
sensor.set_auto_gain(False)
sensor.set_auto_whitebal(False)

# LAB threshold: L min/max, A min/max, B min/max.
# This is a practical starting value for a bright red object indoors.
RED_THRESHOLD = (30, 100, 15, 127, 10, 127)

clock = time.clock()

while True:
    clock.tick()
    img = sensor.snapshot()

    blobs = img.find_blobs(
        [RED_THRESHOLD],
        pixels_threshold=150,
        area_threshold=150,
        merge=True,
        margin=8
    )

    if blobs:
        target = max(blobs, key=lambda b: b.pixels())

        img.draw_rectangle(target.rect(), color=(0, 255, 0), thickness=2)
        img.draw_cross(target.cx(), target.cy(), color=(0, 255, 0), size=12, thickness=2)

        print("RED,x=%d,y=%d,w=%d,h=%d,pixels=%d,fps=%.1f" % (
            target.cx(),
            target.cy(),
            target.w(),
            target.h(),
            target.pixels(),
            clock.fps()
        ))

    lcd.display(img)
