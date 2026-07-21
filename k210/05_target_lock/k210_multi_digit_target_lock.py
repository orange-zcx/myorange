import sensor
import image
import lcd
import time
import math
import gc
from maix import KPU

# Multi-digit scene: lock only the selected digit.
# Learning setup: standard digit cards, simple background, up to 3 cards.

MODEL_FLASH_ADDR = 0x300000
MODEL_SIZE = 550124

TARGET_DIGIT = 5
SEARCH_ROI = (10, 10, 300, 220)
FRAME_CX = 160
FRAME_CY = 120

MAX_CANDIDATES = 3
MIN_TARGET_CONFIDENCE = 0.65
VOTE_WINDOW = 7
VOTES_TO_ACQUIRE = 4
MAX_HOLD_FRAMES = 8
MAX_TRACK_JUMP = 85
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

print("Loading MNIST model from Flash")
print("Target digit: %d" % TARGET_DIGIT)
print("Maximum candidates per frame: %d" % MAX_CANDIDATES)
print("Exposure: %d us" % sensor.get_exposure_us())

kpu = KPU()
kpu.load_kmodel(MODEL_FLASH_ADDR, MODEL_SIZE)
print("MODEL LOAD OK")

threshold_value = 85
presence_history = [0, 0, 0, 0, 0, 0, 0]
history_index = 0

target_active = False
hold_frames = 0
smooth_x = FRAME_CX
smooth_y = FRAME_CY
smooth_w = 0
smooth_h = 0

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


def rect_center_x(rect):
    return rect[0] + rect[2] // 2


def rect_center_y(rect):
    return rect[1] + rect[3] // 2


def continuity_ok(rect):
    jump = (
        abs(rect_center_x(rect) - smooth_x) +
        abs(rect_center_y(rect) - smooth_y)
    )

    if jump > MAX_TRACK_JUMP:
        return False

    if smooth_w > 0 and smooth_h > 0:
        current_area = rect[2] * rect[3]
        smooth_area = smooth_w * smooth_h

        if current_area * 3 < smooth_area:
            return False
        if current_area > smooth_area * 3:
            return False

    return True


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

    # Keep only the strongest three digit-like black regions.
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

    detections = []

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
        digit_112.pix_to_ai()

        out = kpu.run_with_output(digit_112, getlist=True)
        best_value = max(out)
        model_digit = out.index(best_value)
        confidence = confidence_from_output(out, best_value)
        confidence_percent = int(confidence * 100 + 0.5)

        detections.append(
            (model_digit, confidence, confidence_percent, rect)
        )

        del digit_cut
        del digit_112
        del out

    # Find the requested digit. Before acquisition choose best confidence;
    # after acquisition choose the nearest matching target.
    target_detection = None
    target_score = -1000000

    for detection in detections:
        digit = detection[0]
        confidence = detection[1]
        rect = detection[3]

        if digit != TARGET_DIGIT:
            continue
        if confidence < MIN_TARGET_CONFIDENCE:
            continue

        if target_active:
            distance = (
                abs(rect_center_x(rect) - smooth_x) +
                abs(rect_center_y(rect) - smooth_y)
            )
            score = detection[2] * 10 - distance * 4
        else:
            score = detection[2] * 10 + rect[2] * rect[3] // 100

        if score > target_score:
            target_score = score
            target_detection = detection

    presence_history[history_index] = 1 if target_detection else 0
    history_index += 1
    if history_index >= VOTE_WINDOW:
        history_index = 0

    target_votes = 0
    for present in presence_history:
        target_votes += present

    just_acquired = False
    just_lost = False
    state_text = "SEARCH"
    verified_rect = None

    if not target_active:
        if target_detection and target_votes >= VOTES_TO_ACQUIRE:
            verified_rect = target_detection[3]
            target_active = True
            just_acquired = True
            hold_frames = 0
            smooth_x = rect_center_x(verified_rect)
            smooth_y = rect_center_y(verified_rect)
            smooth_w = verified_rect[2]
            smooth_h = verified_rect[3]
    else:
        if target_detection and continuity_ok(target_detection[3]):
            verified_rect = target_detection[3]
            smooth_x = (
                smooth_x * 3 + rect_center_x(verified_rect)
            ) // 4
            smooth_y = (
                smooth_y * 3 + rect_center_y(verified_rect)
            ) // 4
            smooth_w = (smooth_w * 3 + verified_rect[2]) // 4
            smooth_h = (smooth_h * 3 + verified_rect[3]) // 4
            hold_frames = 0
        else:
            # If classification is blurred, continue only with a nearby
            # candidate of similar size. It remains HOLD, not TRACK.
            nearest_rect = None
            nearest_distance = 1000000

            for detection in detections:
                rect = detection[3]
                if not continuity_ok(rect):
                    continue

                distance = (
                    abs(rect_center_x(rect) - smooth_x) +
                    abs(rect_center_y(rect) - smooth_y)
                )

                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_rect = rect

            if nearest_rect:
                smooth_x = (
                    smooth_x * 3 + rect_center_x(nearest_rect)
                ) // 4
                smooth_y = (
                    smooth_y * 3 + rect_center_y(nearest_rect)
                ) // 4
                smooth_w = (smooth_w * 3 + nearest_rect[2]) // 4
                smooth_h = (smooth_h * 3 + nearest_rect[3]) // 4

            hold_frames += 1

        if hold_frames > MAX_HOLD_FRAMES:
            target_active = False
            just_lost = True
            hold_frames = 0
            smooth_w = 0
            smooth_h = 0
            presence_history = [0, 0, 0, 0, 0, 0, 0]

    if just_acquired:
        print("ACQUIRED target=%d votes=%d/7" % (
            TARGET_DIGIT, target_votes
        ))

    if just_lost:
        print("LOST target=%d" % TARGET_DIGIT)

    # Draw all classified candidates after inference.
    for detection in detections:
        digit = detection[0]
        confidence_percent = detection[2]
        rect = detection[3]

        img.draw_rectangle(rect, color=100, thickness=1)

        label_y = rect[1] - 12
        if label_y < 0:
            label_y = 0

        img.draw_string(
            rect[0],
            label_y,
            "%d:%d" % (digit, confidence_percent),
            color=180,
            scale=1
        )

    if target_active:
        error_x = smooth_x - FRAME_CX
        error_y = smooth_y - FRAME_CY

        if hold_frames == 0:
            state_text = "TRACK"
            print("TRACK target=%d ex=%d ey=%d votes=%d/7 candidates=%d" % (
                TARGET_DIGIT, error_x, error_y,
                target_votes, len(detections)
            ))
        else:
            state_text = "HOLD"
            print("HOLD target=%d missed=%d/%d candidates=%d" % (
                TARGET_DIGIT, hold_frames,
                MAX_HOLD_FRAMES, len(detections)
            ))

        img.draw_rectangle(
            (
                smooth_x - smooth_w // 2,
                smooth_y - smooth_h // 2,
                smooth_w,
                smooth_h
            ),
            color=255,
            thickness=3
        )
        img.draw_cross(smooth_x, smooth_y, color=255, size=14)
    else:
        print("SEARCH target=%d votes=%d/7 candidates=%d" % (
            TARGET_DIGIT, target_votes, len(detections)
        ))

    img.draw_rectangle(SEARCH_ROI, color=150, thickness=1)
    img.draw_cross(FRAME_CX, FRAME_CY, color=160, size=10)
    img.draw_string(
        4,
        4,
        "%s T:%d V:%d/7 C:%d" % (
            state_text, TARGET_DIGIT,
            target_votes, len(detections)
        ),
        color=255,
        scale=2
    )

    lcd.display(img)
