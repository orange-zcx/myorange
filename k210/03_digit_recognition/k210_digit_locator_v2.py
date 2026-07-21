import sensor
import image
import lcd
import time

# Makerobo CanMV K210 robust digit locator V2.
# It locates a black digit on a white card. It does not classify 1-8 yet.

sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.QVGA)
sensor.set_hmirror(1)
sensor.set_vflip(1)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)
sensor.set_auto_whitebal(False)

lcd.init()
lcd.rotation(2)

DIGIT_ROI = (80, 40, 160, 160)
ROI_CX = 160
ROI_CY = 120

threshold_value = 85
last_rect = None
locked_rect = None
stable_frames = 0
miss_frames = 0

clock = time.clock()


def rect_is_similar(a, b):
    if (a is None) or (b is None):
        return False

    acx = a[0] + a[2] // 2
    acy = a[1] + a[3] // 2
    bcx = b[0] + b[2] // 2
    bcy = b[1] + b[3] // 2

    return (abs(acx - bcx) <= 22 and
            abs(acy - bcy) <= 22 and
            abs(a[2] - b[2]) <= 30 and
            abs(a[3] - b[3]) <= 30)


while True:
    clock.tick()
    img = sensor.snapshot()

    # Estimate black/white separation from the current card area.
    hist = img.get_histogram(roi=DIGIT_ROI)
    dark = hist.get_percentile(0.03).value()
    light = hist.get_percentile(0.80).value()
    measured = dark + ((light - dark) * 38 // 100)

    # Avoid unreasonable thresholds, then smooth frame-to-frame changes.
    if measured < 45:
        measured = 45
    elif measured > 145:
        measured = 145
    threshold_value = (threshold_value * 3 + measured) // 4

    blobs = img.find_blobs(
        [(0, threshold_value)],
        roi=DIGIT_ROI,
        pixels_threshold=60,
        area_threshold=80,
        merge=False
    )

    candidate = None
    best_score = -100000

    for b in blobs:
        bw = b.w()
        bh = b.h()
        box_area = bw * bh

        if box_area <= 0:
            continue

        density = b.pixels() * 100 // box_area
        dx = abs(b.cx() - ROI_CX)
        dy = abs(b.cy() - ROI_CY)

        # Digits must be large enough, near the middle, and not fill the ROI.
        if bw < 5 or bh < 28:
            continue
        if bw > 112 or bh > 148:
            continue
        if dx > 55 or dy > 58:
            continue

        # Thin rectangular outlines have very low filled-pixel density.
        if density < 10:
            continue

        # Reject a large card/frame outline while keeping a tall narrow digit 1.
        if bw > 105 and bh > 105:
            continue

        # Prefer a tall, solid object near the center.
        score = b.pixels() + (bh * 4) - (dx * 5) - (dy * 4)

        if score > best_score:
            candidate = b
            best_score = score

    if candidate:
        current_rect = candidate.rect()

        if rect_is_similar(current_rect, last_rect):
            stable_frames += 1
        else:
            stable_frames = 1

        last_rect = current_rect
        miss_frames = 0

        # Require two similar frames before accepting a new target.
        if stable_frames >= 2:
            locked_rect = current_rect

        # Dim box means a candidate is being checked.
        img.draw_rectangle(current_rect, color=120, thickness=1)
    else:
        miss_frames += 1

        # Ignore a few isolated missed frames.
        if miss_frames > 5:
            locked_rect = None
            last_rect = None
            stable_frames = 0

    # Draw only after detection so graphics cannot affect image processing.
    img.draw_rectangle(DIGIT_ROI, color=180, thickness=2)

    if locked_rect:
        lx = locked_rect[0] + locked_rect[2] // 2
        ly = locked_rect[1] + locked_rect[3] // 2
        img.draw_rectangle(locked_rect, color=255, thickness=2)
        img.draw_cross(lx, ly, color=255, size=8)
        print("LOCKED threshold=%d x=%d y=%d w=%d h=%d" % (
            threshold_value,
            locked_rect[0], locked_rect[1],
            locked_rect[2], locked_rect[3]
        ))
    elif candidate:
        print("CHECKING threshold=%d" % threshold_value)
    else:
        print("NO DIGIT threshold=%d" % threshold_value)

    lcd.display(img)
