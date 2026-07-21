import sensor
import image
import lcd
import time
import math
import gc
from maix import KPU

# Makerobo CanMV K210 digit recognition 0-9.
# V2 locator + official CanMV MNIST KPU model.

MODEL_FLASH_ADDR = 0x300000
MODEL_SIZE = 550124
DIGIT_ROI = (80, 40, 160, 160)
ROI_CX = 160
ROI_CY = 120
MIN_CONFIDENCE = 0.80
REQUIRED_SAME_RESULTS = 5
REQUIRED_BOX_FRAMES = 4

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

print("Loading MNIST model:")
print("Flash address: 0x%X, size: %d" % (MODEL_FLASH_ADDR, MODEL_SIZE))

kpu = KPU()
try:
    kpu.load_kmodel(MODEL_FLASH_ADDR, MODEL_SIZE)
except Exception as e:
    print("FLASH MODEL LOAD FAILED")
    print("Burn the MNIST model to K210 Flash:")
    print("Flash address: 0x%X, size: %d" % (MODEL_FLASH_ADDR, MODEL_SIZE))
    raise e

print("MODEL LOAD OK")
print("Show one black digit (0-9) inside the center box")

threshold_value = 85
last_rect = None
locked_rect = None
stable_frames = 0
miss_frames = 0
last_prediction = -1
same_prediction_count = 0

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


def square_crop(rect):
    cx = rect[0] + rect[2] // 2
    cy = rect[1] + rect[3] // 2
    side = rect[2] if rect[2] > rect[3] else rect[3]

    # Keep white space around the digit, as used by MNIST.
    side = side + side // 3
    if side < 48:
        side = 48
    if side > 156:
        side = 156

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

    # Stable softmax for models that output logits.
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

    # V2 automatic black/white separation.
    hist = img.get_histogram(roi=DIGIT_ROI)
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

        if bw < 5 or bh < 28:
            continue
        if bw > 112 or bh > 148:
            continue
        if dx > 55 or dy > 58:
            continue
        if density < 10:
            continue
        if bw > 105 and bh > 105:
            continue

        score = b.pixels() + (bh * 4) - (dx * 5) - (dy * 4)

        if score > best_score:
            candidate = b
            best_score = score

    result_text = "NO DIGIT"

    if candidate:
        current_rect = candidate.rect()

        if rect_is_similar(current_rect, last_rect):
            stable_frames += 1
        else:
            # Never classify using an old box after the target changes.
            stable_frames = 1
            locked_rect = None
            last_prediction = -1
            same_prediction_count = 0

        last_rect = current_rect
        miss_frames = 0

        if stable_frames >= REQUIRED_BOX_FRAMES:
            locked_rect = current_rect
        else:
            locked_rect = None

    else:
        # One missed frame invalidates the recognition sequence.
        miss_frames += 1
        locked_rect = None
        last_prediction = -1
        same_prediction_count = 0

        if miss_frames > 5:
            last_rect = None
            stable_frames = 0

    if locked_rect and candidate:
        crop_rect = square_crop(locked_rect)
        digit_cut = img.cut(
            crop_rect[0], crop_rect[1],
            crop_rect[2], crop_rect[3]
        )
        digit_112 = digit_cut.resize(112, 112)

        digit_112.invert()
        digit_112.strech_char(1)
        digit_112.pix_to_ai()

        out = kpu.run_with_output(digit_112, getlist=True)
        best_value = max(out)
        predicted_digit = out.index(best_value)
        confidence = confidence_from_output(out, best_value)
        confidence_percent = int(confidence * 100 + 0.5)

        if confidence >= MIN_CONFIDENCE:
            if predicted_digit == last_prediction:
                same_prediction_count += 1
            else:
                last_prediction = predicted_digit
                same_prediction_count = 1
        else:
            # Low-confidence guesses never contribute to a stable result.
            last_prediction = -1
            same_prediction_count = 0

        print("PREDICT: %d  CONFIDENCE: %d%%  SAME: %d" % (
            predicted_digit, confidence_percent, same_prediction_count
        ))

        if (confidence >= MIN_CONFIDENCE and
                same_prediction_count >= REQUIRED_SAME_RESULTS):
            result_text = "NUMBER:%d" % predicted_digit
            print("DIGIT: %d  CONFIDENCE: %d%%" % (
                predicted_digit, confidence_percent
            ))
        else:
            result_text = "CHECK:%d" % predicted_digit

        # Show exactly what the neural network received.
        digit_112.ai_to_pix()
        img.draw_image(digit_112, 204, 124)
        img.draw_rectangle((203, 123, 114, 114), color=180, thickness=1)

        lx = locked_rect[0] + locked_rect[2] // 2
        ly = locked_rect[1] + locked_rect[3] // 2
        img.draw_rectangle(locked_rect, color=255, thickness=2)
        img.draw_cross(lx, ly, color=255, size=8)

        del digit_cut
        del digit_112
        del out
    else:
        print(result_text)

    # Draw overlays only after KPU preprocessing.
    img.draw_rectangle(DIGIT_ROI, color=180, thickness=2)
    if candidate and not locked_rect:
        img.draw_rectangle(candidate.rect(), color=120, thickness=1)
    img.draw_string(4, 4, result_text, color=255, scale=3)
    lcd.display(img)
