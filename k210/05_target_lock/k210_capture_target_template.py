import sensor
import image
import lcd
import os
import time
import math
import gc
from maix import KPU

# Capture one normalized target template to K210 internal Flash.
# Hold only the requested standard digit card inside the center box.

MODEL_FLASH_ADDR = 0x300000
MODEL_SIZE = 550124

TARGET_DIGIT = 5
TEMPLATE_PATH = "/flash/target_5.pgm"
DIGIT_ROI = (80, 40, 160, 160)
REQUIRED_GOOD_FRAMES = 10
MIN_CONFIDENCE = 0.80

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

kpu = KPU()
kpu.load_kmodel(MODEL_FLASH_ADDR, MODEL_SIZE)

print("MODEL LOAD OK")
print("Template target: %d" % TARGET_DIGIT)
print("Template path:", TEMPLATE_PATH)
print("Show only digit %d inside the center box" % TARGET_DIGIT)

threshold_value = 85
good_frames = 0
template_saved = False
save_attempted = False

clock = time.clock()


def square_crop(rect):
    cx = rect[0] + rect[2] // 2
    cy = rect[1] + rect[3] // 2
    side = rect[2] if rect[2] > rect[3] else rect[3]

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
        dx = abs(b.cx() - 160)
        dy = abs(b.cy() - 120)

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

        score = b.pixels() + bh * 4 - dx * 5 - dy * 4

        if score > best_score:
            candidate = b
            best_score = score

    status_text = "WAIT T:%d 0/%d" % (
        TARGET_DIGIT, REQUIRED_GOOD_FRAMES
    )

    if candidate:
        crop_rect = square_crop(candidate.rect())
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

        if (predicted_digit == TARGET_DIGIT and
                confidence >= MIN_CONFIDENCE):
            good_frames += 1
        else:
            good_frames = 0

        status_text = "T:%d P:%d %d%% %d/%d" % (
            TARGET_DIGIT,
            predicted_digit,
            confidence_percent,
            good_frames,
            REQUIRED_GOOD_FRAMES
        )

        print(status_text)

        digit_112.ai_to_pix()

        if (good_frames >= REQUIRED_GOOD_FRAMES and
                not save_attempted):
            save_attempted = True

            try:
                digit_112.save(TEMPLATE_PATH)

                try:
                    os.sync()
                except Exception:
                    pass

                verify_template = image.Image(TEMPLATE_PATH)
                print("VERIFY IMAGE SIZE: %d x %d" % (
                    verify_template.width(),
                    verify_template.height()
                ))
                del verify_template

                print("FLASH FILES:", os.listdir("/flash"))
                print("TEMPLATE STAT:", os.stat(TEMPLATE_PATH))

                template_saved = True
                print("==============================")
                print("TEMPLATE SAVED AND VERIFIED")
                print(TEMPLATE_PATH)
                print("==============================")
            except Exception as e:
                print("==============================")
                print("TEMPLATE SAVE/VERIFY FAILED")
                print(e)
                print("==============================")

        img.draw_rectangle(candidate.rect(), color=255, thickness=2)
        img.draw_cross(candidate.cx(), candidate.cy(), color=255, size=10)
        img.draw_image(digit_112, 204, 124)
        img.draw_rectangle((203, 123, 114, 114), color=180, thickness=1)

        del digit_cut
        del digit_112
        del out
    else:
        good_frames = 0
        print("NO DIGIT")

    img.draw_rectangle(DIGIT_ROI, color=180, thickness=2)
    img.draw_string(4, 4, status_text, color=255, scale=2)

    if template_saved:
        img.draw_string(4, 28, "TEMPLATE SAVED", color=255, scale=2)

    lcd.display(img)
