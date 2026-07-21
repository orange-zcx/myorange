import sensor, image, time, lcd

lcd.init()
lcd.rotation(2)
lcd.clear(lcd.BLACK)

sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)   # 320 x 240
sensor.set_hmirror(1)
sensor.set_vflip(1)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)
sensor.set_auto_whitebal(False)

RED_THRESHOLD = (30, 100, 15, 127, 10, 127)

IMAGE_CENTER_X = 160
IMAGE_CENTER_Y = 120
CENTER_DEAD_ZONE = 20

clock = time.clock()

while True:
    clock.tick()
    img = sensor.snapshot()

    # Draw the image center and the horizontal dead zone.
    img.draw_line((IMAGE_CENTER_X, 0, IMAGE_CENTER_X, 239), color=(255, 255, 0), thickness=1)
    img.draw_line((0, IMAGE_CENTER_Y, 319, IMAGE_CENTER_Y), color=(255, 255, 0), thickness=1)
    img.draw_line((IMAGE_CENTER_X - CENTER_DEAD_ZONE, 0,
                   IMAGE_CENTER_X - CENTER_DEAD_ZONE, 239), color=(100, 100, 100), thickness=1)
    img.draw_line((IMAGE_CENTER_X + CENTER_DEAD_ZONE, 0,
                   IMAGE_CENTER_X + CENTER_DEAD_ZONE, 239), color=(100, 100, 100), thickness=1)

    blobs = img.find_blobs(
        [RED_THRESHOLD],
        pixels_threshold=150,
        area_threshold=150,
        merge=True,
        margin=8
    )

    if blobs:
        target = max(blobs, key=lambda b: b.pixels())
        dx = target.cx() - IMAGE_CENTER_X
        dy = target.cy() - IMAGE_CENTER_Y

        if dx < -CENTER_DEAD_ZONE:
            direction = "LEFT"
        elif dx > CENTER_DEAD_ZONE:
            direction = "RIGHT"
        else:
            direction = "CENTER"

        img.draw_rectangle(target.rect(), color=(0, 255, 0), thickness=2)
        img.draw_cross(target.cx(), target.cy(), color=(0, 255, 0), size=12, thickness=2)

        print("POS,%s,dx=%d,dy=%d,x=%d,y=%d,pixels=%d,fps=%.1f" % (
            direction,
            dx,
            dy,
            target.cx(),
            target.cy(),
            target.pixels(),
            clock.fps()
        ))

    lcd.display(img)
