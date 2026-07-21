import sensor
import image
import lcd
import time
import math
import gc
from maix import KPU

# Detect up to 3 complete white digit cards.
# Only one card is classified per frame to keep RAM usage low.

MODEL_FLASH_ADDR = 0x300000
MODEL_SIZE = 550124

MAX_CARDS = 3
TARGET_DIGIT = 5

MIN_CONFIDENCE = 0.70
TARGET_VOTES_TO_ACQUIRE = 3
MAX_TARGET_HOLD_FRAMES = 8
MAX_TARGET_JUMP = 90
REQUIRED_SAMPLES = 3
MAX_CENTER_JUMP = 35

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
print("ROUND-ROBIN MULTI CARD RECOGNITION")
print("Only one card is inferred per frame")

round_robin_index = 0
last_centers = [-1000, -1000, -1000]
raw_digits = [-1, -1, -1]
raw_confidence = [0, 0, 0]
same_counts = [0, 0, 0]
stable_digits = [-1, -1, -1]

target_active = False
target_hold_frames = 0
target_pending_rect = None
target_pending_votes = 0
smooth_x = 160
smooth_y = 120
smooth_w = 0
smooth_h = 0


def rect_center_x(rect):
    return rect[0] + rect[2] // 2


def rect_center_y(rect):
    return rect[1] + rect[3] // 2


def rect_is_near(rect, x, y, max_jump):
    distance = (
        abs(rect_center_x(rect) - x) +
        abs(rect_center_y(rect) - y)
    )
    return distance <= max_jump


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

    card_items = []

    for blob in blobs:
        width = blob.w()
        height = blob.h()
        area = width * height
        ratio100 = width * 100 // height

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

        for index in range(len(card_items)):
            if score > card_items[index][0]:
                card_items.insert(index, (score, blob.rect()))
                inserted = True
                break

        if not inserted:
            card_items.append((score, blob.rect()))

        if len(card_items) > MAX_CARDS:
            card_items.pop()

    cards = []

    for item in card_items:
        cards.append(item[1])

    # Sort cards from left to right, giving stable CARD1/2/3 indices.
    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            if cards[j][0] < cards[i][0]:
                temporary = cards[i]
                cards[i] = cards[j]
                cards[j] = temporary

    # Reset a slot if a different card suddenly occupies that index.
    for index in range(len(cards)):
        center = cards[index][0] + cards[index][2] // 2

        if abs(center - last_centers[index]) > MAX_CENTER_JUMP:
            raw_digits[index] = -1
            raw_confidence[index] = 0
            same_counts[index] = 0
            stable_digits[index] = -1

        last_centers[index] = center

    if len(cards) > 0:
        process_index = round_robin_index % len(cards)
        round_robin_index += 1
        rect = cards[process_index]

        # Remove a small white-card border before classification.
        margin_x = rect[2] // 14
        margin_y = rect[3] // 14

        if margin_x < 2:
            margin_x = 2
        if margin_y < 2:
            margin_y = 2

        crop_x = rect[0] + margin_x
        crop_y = rect[1] + margin_y
        crop_w = rect[2] - margin_x * 2
        crop_h = rect[3] - margin_y * 2

        if crop_w >= 16 and crop_h >= 16:
            gc.collect()
            card_cut = img.cut(
                crop_x, crop_y, crop_w, crop_h
            )
            digit_112 = card_cut.resize(112, 112)
            del card_cut

            digit_112.invert()
            digit_112.strech_char(1)
            digit_112.pix_to_ai()

            output = kpu.run_with_output(
                digit_112, getlist=True
            )
            best_value = max(output)
            predicted_digit = output.index(best_value)
            confidence = confidence_from_output(
                output, best_value
            )
            confidence_percent = int(confidence * 100 + 0.5)

            if confidence >= MIN_CONFIDENCE:
                if predicted_digit == raw_digits[process_index]:
                    same_counts[process_index] += 1
                else:
                    raw_digits[process_index] = predicted_digit
                    same_counts[process_index] = 1

                raw_confidence[process_index] = confidence_percent

                if same_counts[process_index] >= REQUIRED_SAMPLES:
                    stable_digits[process_index] = predicted_digit
            else:
                raw_digits[process_index] = predicted_digit
                raw_confidence[process_index] = confidence_percent
                same_counts[process_index] = 0
                stable_digits[process_index] = -1

            print(
                "CARD%d X=%d RAW=%d CONF=%d%% SAME=%d STABLE=%d" %
                (
                    process_index + 1,
                    rect[0] + rect[2] // 2,
                    predicted_digit,
                    confidence_percent,
                    same_counts[process_index],
                    stable_digits[process_index]
                )
            )

            del digit_112
            del output

    # Select only a card whose stable classification equals TARGET_DIGIT.
    target_rect = None
    best_target_score = -1000000

    for index in range(len(cards)):
        if stable_digits[index] != TARGET_DIGIT:
            continue

        rect = cards[index]

        if target_active:
            distance = (
                abs(rect_center_x(rect) - smooth_x) +
                abs(rect_center_y(rect) - smooth_y)
            )
            score = -distance
        else:
            score = raw_confidence[index] * 10 + rect[2] * rect[3] // 100

        if score > best_target_score:
            best_target_score = score
            target_rect = rect

    just_acquired = False
    just_lost = False
    target_state = "SEARCH"

    if not target_active:
        if target_rect:
            if (
                target_pending_rect is not None and
                rect_is_near(
                    target_rect,
                    rect_center_x(target_pending_rect),
                    rect_center_y(target_pending_rect),
                    45
                )
            ):
                target_pending_votes += 1
            else:
                target_pending_rect = target_rect
                target_pending_votes = 1
        else:
            target_pending_rect = None
            target_pending_votes = 0

        if (
            target_pending_rect is not None and
            target_pending_votes >= TARGET_VOTES_TO_ACQUIRE
        ):
            target_active = True
            just_acquired = True
            target_hold_frames = 0
            smooth_x = rect_center_x(target_pending_rect)
            smooth_y = rect_center_y(target_pending_rect)
            smooth_w = target_pending_rect[2]
            smooth_h = target_pending_rect[3]
            target_pending_rect = None
            target_pending_votes = 0
    else:
        if (
            target_rect is not None and
            rect_is_near(
                target_rect,
                smooth_x,
                smooth_y,
                MAX_TARGET_JUMP
            )
        ):
            smooth_x = (
                smooth_x * 3 + rect_center_x(target_rect)
            ) // 4
            smooth_y = (
                smooth_y * 3 + rect_center_y(target_rect)
            ) // 4
            smooth_w = (smooth_w * 3 + target_rect[2]) // 4
            smooth_h = (smooth_h * 3 + target_rect[3]) // 4
            target_hold_frames = 0
        else:
            target_hold_frames += 1

        if target_hold_frames > MAX_TARGET_HOLD_FRAMES:
            target_active = False
            just_lost = True
            target_hold_frames = 0
            smooth_w = 0
            smooth_h = 0
            target_pending_rect = None
            target_pending_votes = 0

    if just_acquired:
        print("ACQUIRED TARGET:", TARGET_DIGIT)

    if just_lost:
        print("LOST TARGET:", TARGET_DIGIT)

    if target_active:
        if target_hold_frames == 0:
            target_state = "TRACK"
            print(
                "TRACK TARGET=%d EX=%d EY=%d" %
                (
                    TARGET_DIGIT,
                    smooth_x - 160,
                    smooth_y - 120
                )
            )
        else:
            target_state = "HOLD"
            print(
                "HOLD TARGET=%d MISSED=%d/%d" %
                (
                    TARGET_DIGIT,
                    target_hold_frames,
                    MAX_TARGET_HOLD_FRAMES
                )
            )

    for index in range(len(cards)):
        rect = cards[index]
        img.draw_rectangle(
            rect, color=255, thickness=3
        )

        if stable_digits[index] >= 0:
            label = "N:%d" % stable_digits[index]
        elif raw_digits[index] >= 0:
            label = "?:%d" % raw_digits[index]
        else:
            label = "WAIT"

        img.draw_string(
            rect[0],
            rect[1],
            label,
            color=255,
            scale=2
        )

    if target_active:
        img.draw_rectangle(
            (
                smooth_x - smooth_w // 2,
                smooth_y - smooth_h // 2,
                smooth_w,
                smooth_h
            ),
            color=255,
            thickness=4
        )
        img.draw_cross(
            smooth_x,
            smooth_y,
            color=255,
            size=16
        )

    img.draw_cross(160, 120, color=150, size=10)
    img.draw_string(
        4,
        4,
        "%s T:%d C:%d" % (
            target_state,
            TARGET_DIGIT,
            len(cards)
        ),
        color=255,
        scale=2
    )
    lcd.display(img)
