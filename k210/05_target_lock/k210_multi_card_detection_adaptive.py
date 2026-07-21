import sensor
import lcd
import time
import gc

# Adaptive white-card detection debug.
# Thin boxes: raw bright regions. Thick boxes: accepted card candidates.

MAX_CARDS = 5

sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.QVGA)
sensor.set_hmirror(0)
sensor.set_vflip(0)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)
sensor.set_auto_whitebal(False)

lcd.init()
lcd.rotation(0)

print("ADAPTIVE MULTI CARD DETECTION")
print("Use white cards on a visibly darker background")

while True:
    gc.collect()
    img = sensor.snapshot()

    histogram = img.get_histogram()
    background = histogram.get_percentile(0.60).value()
    bright = histogram.get_percentile(0.95).value()

    contrast = bright - background
    white_low = background + contrast * 50 // 100

    if white_low < 60:
        white_low = 60
    elif white_low > 220:
        white_low = 220

    blobs = img.find_blobs(
        [(white_low, 255)],
        pixels_threshold=180,
        area_threshold=300,
        merge=False
    )

    cards = []

    for blob in blobs:
        rect = blob.rect()
        width = blob.w()
        height = blob.h()
        area = width * height
        ratio100 = width * 100 // height

        # Draw every raw bright region for diagnosis.
        img.draw_rectangle(rect, color=100, thickness=1)

        if width < 20 or height < 20:
            continue
        if width > 305 or height > 230:
            continue
        if area < 500 or area > 65000:
            continue
        if ratio100 < 35 or ratio100 > 260:
            continue

        score = blob.pixels()
        inserted = False

        for index in range(len(cards)):
            if score > cards[index][0]:
                cards.insert(index, (score, rect))
                inserted = True
                break

        if not inserted:
            cards.append((score, rect))

        if len(cards) > MAX_CARDS:
            cards.pop()

    for index in range(len(cards)):
        rect = cards[index][1]
        cx = rect[0] + rect[2] // 2
        cy = rect[1] + rect[3] // 2

        img.draw_rectangle(rect, color=255, thickness=3)
        img.draw_cross(cx, cy, color=255, size=10)
        img.draw_string(
            rect[0],
            rect[1],
            "CARD%d" % (index + 1),
            color=255,
            scale=2
        )

    print(
        "BG=%d BRIGHT=%d CONTRAST=%d TH=%d RAW=%d CARDS=%d" %
        (
            background,
            bright,
            contrast,
            white_low,
            len(blobs),
            len(cards)
        )
    )

    img.draw_string(
        4,
        4,
        "T:%d R:%d C:%d" % (
            white_low,
            len(blobs),
            len(cards)
        ),
        color=255,
        scale=2
    )
    lcd.display(img)
