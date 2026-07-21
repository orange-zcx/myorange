import sensor
import image
import lcd
import time

# Makerobo CanMV K210 digit framing test.
# This step only finds the black digit; it does not classify 1-8 yet.

sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.QVGA)
sensor.set_hmirror(1)
sensor.set_vflip(1)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)

lcd.init()
lcd.rotation(2)

DIGIT_ROI = (80, 40, 160, 160)
BLACK_THRESHOLD = (0, 85)

clock = time.clock()

while True:
    clock.tick()
    img = sensor.snapshot()
    img.draw_rectangle(DIGIT_ROI, color=180, thickness=2)

    blobs = img.find_blobs(
        [BLACK_THRESHOLD],
        roi=DIGIT_ROI,
        pixels_threshold=80,
        area_threshold=100,
        merge=True,
        margin=2
    )

    target = None
    best_score = 0

    for b in blobs:
        box_area = b.w() * b.h()

        # A printed/card border is usually both very wide and very high.
        # Reject it while keeping tall, narrow digit 1.
        looks_like_border = (b.w() > 120 and b.h() > 120)

        if (not looks_like_border) and box_area < 16000:
            # Prefer actual black-pixel count instead of bounding-box area.
            score = b.pixels()
            if score > best_score:
                target = b
                best_score = score

    if target:
        img.draw_rectangle(target.rect(), color=255, thickness=2)
        img.draw_cross(target.cx(), target.cy(), color=255, size=8)
        print("DIGIT FOUND x=%d y=%d w=%d h=%d pixels=%d" % (
            target.x(), target.y(), target.w(), target.h(), target.pixels()
        ))
    else:
        print("NO DIGIT")

    lcd.display(img)
