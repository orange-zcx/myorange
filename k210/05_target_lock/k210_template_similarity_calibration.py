import sensor
import image
import lcd
import time
import math
import gc
from maix import KPU

# Calibrate structural similarity against the saved target template.
# Place digit 2 on the left, 5 in the center, and 8 on the right.

MODEL_FLASH_ADDR = 0x300000
MODEL_SIZE = 550124
TEMPLATE_PATH = "/flash/target_5.pgm"

SEARCH_ROI = (10, 10, 300, 220)
MAX_CANDIDATES = 3
MAX_EXPOSURE_US = 12000

sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.QVGA)
sensor.set_hmirror(0)
sensor.set_vflip(0)
sensor.skip_frames(time=2000)

sensor.set_auto_gain(False)
sensor.set_auto_whitebal(False)
sensor.skip_frames(time=300)

current_exposure = sensor.get_exposure_us()
locked_exposure = current_exposure
if locked_exposure > MAX_EXPOSURE_US:
    locked_exposure = MAX_EXPOSURE_US
sensor.set_auto_exposure(False, exposure_us=locked_exposure)

lcd.init()
lcd.rotation(0)

kpu = KPU()
kpu.load_kmodel(MODEL_FLASH_ADDR, MODEL_SIZE)
target_template = image.Image(TEMPLATE_PATH)

print("MODEL LOAD OK")
print("TEMPLATE LOAD OK:", TEMPLATE_PATH)
print("Place: 2=LEFT, 5=CENTER, 8=RIGHT")

threshold_value = 85
clock = time.clock()


def square_crop(rect):
    cx = rect[0] + rect[2] // 2
    cy = rect[1] + rect[3] // 2
    side = rect[2] if rect[2] > rect[3] else rect[3]

    side = side + side // 3
    if side < 48:
        side = 48
    if side > 180:
        side = 180

    x = cx - side // 2
    y = cy - side // 2

    if x < 0:
        x = 0
    if y < 0:
        y = 0
    if x + side > 320:
        x = 320 - side
    if y + side > 240:
        y = 240 - side

    return (x, y, side, side)


def confidence_from_output(out, best_value):
    total_raw = 0.0
    looks_like_probability = True

    for value in out:
        total_raw += value
        if value < 0.0 or value > 1.0:
            looks_like_probability = False

    if looks_like_probability and total_raw > 0.80 and total_raw < 1.20:
        return best_value / total_raw

    exp_sum = 0.0
    for value in out:
        exp_sum += math.exp(value - best_value)

    if exp_sum <= 0.0:
        return 0.0
    return 1.0 / exp_sum


while True:
    gc.collect()
    clock.tick()
    img = sensor.snapshot()

    hist = img.get_histogram(roi=SEARCH_ROI)
    dark = hist.get_percentile(0.03).value()
    light = hist.get_percentile(0.80).value()
    measured = dark + ((light - dark) * 38 // 100)

    if measured < 45:
        measured = 45
    elif measured > 145:
        measured = 145
    threshold_value = (threshold_value * 3 + measured) // 4

    blobs = img.find_blobs(
        [(0, threshold_value)],
        roi=SEARCH_ROI,
        pixels_threshold=60,
        area_threshold=80,
        merge=False
    )

    candidate_items = []

    for b in blobs:
        bw = b.w()
        bh = b.h()
        box_area = bw * bh

        if box_area <= 0:
            continue

        density = b.pixels() * 100 // box_area

        if bw < 5 or bh < 24:
            continue
        if bw > 145 or bh > 185:
            continue
        if density < 9:
            continue
        if bw > 125 and bh > 125:
            continue

        score = b.pixels() + bh * 4
        inserted = False

        for index in range(len(candidate_items)):
            if score > candidate_items[index][0]:
                candidate_items.insert(index, (score, b))
                inserted = True
                break

        if not inserted:
            candidate_items.append((score, b))

        if len(candidate_items) > MAX_CANDIDATES:
            candidate_items.pop()

    print("----- FRAME candidates=%d -----" % len(candidate_items))

    for item in candidate_items:
        blob = item[1]
        rect = blob.rect()
        crop_rect = square_crop(rect)

        digit_cut = img.cut(
            crop_rect[0], crop_rect[1],
            crop_rect[2], crop_rect[3]
        )
        digit_112 = digit_cut.resize(112, 112)
        digit_112.invert()
        digit_112.strech_char(1)

        similarity = digit_112.get_similarity(target_template)
        similarity_score = int(similarity.mean() * 100)

        digit_112.pix_to_ai()
        out = kpu.run_with_output(digit_112, getlist=True)
        best_value = max(out)
        model_digit = out.index(best_value)
        confidence = confidence_from_output(out, best_value)
        confidence_percent = int(confidence * 100 + 0.5)

        print(
            "X=%d MODEL=%d CONF=%d%% SIM5=%d" %
            (
                blob.cx(), model_digit,
                confidence_percent, similarity_score
            )
        )

        img.draw_rectangle(rect, color=180, thickness=2)

        label_y = rect[1] - 14
        if label_y < 0:
            label_y = 0

        img.draw_string(
            rect[0],
            label_y,
            "M%d C%d S%d" % (
                model_digit,
                confidence_percent,
                similarity_score
            ),
            color=255,
            scale=1
        )

        del digit_cut
        del digit_112
        del out

    img.draw_rectangle(SEARCH_ROI, color=140, thickness=1)
    img.draw_string(4, 4, "2 LEFT  5 MID  8 RIGHT", color=255, scale=1)
    lcd.display(img)
