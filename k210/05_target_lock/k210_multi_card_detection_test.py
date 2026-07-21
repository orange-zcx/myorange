import sensor
import lcd
import time
import gc

# Step 1 for multi-digit recognition:
# detect complete white digit cards, without loading the KPU model.

WHITE_THRESHOLD = (150, 255)
MAX_CARDS = 3

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

print("MULTI CARD DETECTION TEST")
print("Place up to 3 white digit cards on a darker background")
print("Keep visible gaps between cards")

while True:
    gc.collect()
    img = sensor.snapshot()

    blobs = img.find_blobs(
        [WHITE_THRESHOLD],
        pixels_threshold=500,
        area_threshold=900,
        merge=True,
        margin=2
    )

    cards = []

    for blob in blobs:
        width = blob.w()
        height = blob.h()
        area = width * height

        if width < 30 or height < 30:
            continue
        if width > 250 or height > 210:
            continue
        if area < 1400 or area > 45000:
            continue

        ratio100 = width * 100 // height
        if ratio100 < 55 or ratio100 > 190:
            continue

        score = blob.pixels()
        inserted = False

        for index in range(len(cards)):
            if score > cards[index][0]:
                cards.insert(index, (score, blob.rect()))
                inserted = True
                break

        if not inserted:
            cards.append((score, blob.rect()))

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

    print("CARDS FOUND:", len(cards))
    img.draw_string(
        4, 4,
        "CARDS:%d" % len(cards),
        color=255,
        scale=3
    )
    lcd.display(img)
