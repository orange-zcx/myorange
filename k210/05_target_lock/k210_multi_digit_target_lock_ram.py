import sensor
import image
import lcd
import time
import math
import gc
from maix import KPU

# Multi-digit specified-target lock using an in-RAM reference.
# At startup show only TARGET_DIGIT in the center.
# After REFERENCE LEARNED, add the other digit cards.

MODEL_FLASH_ADDR = 0x300000
MODEL_SIZE = 550124

TARGET_DIGIT = 5
LEARN_ROI = (80, 40, 160, 160)
SEARCH_ROI = (10, 10, 300, 220)
FRAME_CX = 160
FRAME_CY = 120
MAX_CANDIDATES = 3

LEARN_GOOD_FRAMES = 10
MIN_LEARN_CONFIDENCE = 0.80

MIN_MODEL_CONFIDENCE = 0.60
MIN_TEMPLATE_SIMILARITY = 0.45
STRONG_TEMPLATE_SIMILARITY = 0.68
MIN_TEMPLATE_MARGIN = 0.06

VOTES_TO_ACQUIRE = 4
MAX_PENDING_MISSES = 2
MAX_HOLD_FRAMES = 8
MAX_PENDING_JUMP = 65
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

kpu = KPU()
kpu.load_kmodel(MODEL_FLASH_ADDR, MODEL_SIZE)

print("MODEL LOAD OK")
print("Target digit: %d" % TARGET_DIGIT)
print("STEP 1: show only target %d in center" % TARGET_DIGIT)

clock = time.clock()


def square_crop(rect, max_side=180):
    cx = rect[0] + rect[2] // 2
    cy = rect[1] + rect[3] // 2
    side = rect[2] if rect[2] > rect[3] else rect[3]

    side = side + side // 3
    if side < 48:
        side = 48
    if side > max_side:
        side = max_side

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


def center_x(rect):
    return rect[0] + rect[2] // 2


def center_y(rect):
    return rect[1] + rect[3] // 2


def same_spatial_object(rect_a, rect_b, max_jump):
    if rect_a is None or rect_b is None:
        return False

    jump = (
        abs(center_x(rect_a) - center_x(rect_b)) +
        abs(center_y(rect_a) - center_y(rect_b))
    )

    if jump > max_jump:
        return False

    area_a = rect_a[2] * rect_a[3]
    area_b = rect_b[2] * rect_b[3]

    if area_a * 3 < area_b:
        return False
    if area_a > area_b * 3:
        return False

    return True


def find_center_candidate(img, threshold):
    blobs = img.find_blobs(
        [(0, threshold)],
        roi=LEARN_ROI,
        pixels_threshold=60,
        area_threshold=80,
        merge=False
    )

    candidate = None
    best_score = -100000

    for blob in blobs:
        width = blob.w()
        height = blob.h()
        area = width * height

        if area <= 0:
            continue

        density = blob.pixels() * 100 // area
        dx = abs(blob.cx() - FRAME_CX)
        dy = abs(blob.cy() - FRAME_CY)

        if width < 5 or height < 28:
            continue
        if width > 112 or height > 148:
            continue
        if dx > 55 or dy > 58:
            continue
        if density < 10:
            continue
        if width > 105 and height > 105:
            continue

        score = (
            blob.pixels() + height * 4 -
            dx * 5 - dy * 4
        )

        if score > best_score:
            best_score = score
            candidate = blob

    return candidate


def learn_reference():
    threshold = 85
    good_frames = 0

    while True:
        gc.collect()
        img = sensor.snapshot()

        hist = img.get_histogram(roi=LEARN_ROI)
        dark = hist.get_percentile(0.03).value()
        light = hist.get_percentile(0.80).value()
        measured = dark + ((light - dark) * 38 // 100)

        if measured < 45:
            measured = 45
        elif measured > 145:
            measured = 145
        threshold = (threshold * 3 + measured) // 4

        candidate = find_center_candidate(img, threshold)
        status = "LEARN T:%d %d/%d" % (
            TARGET_DIGIT, good_frames, LEARN_GOOD_FRAMES
        )

        if candidate:
            crop_rect = square_crop(candidate.rect(), 156)
            digit_cut = img.cut(
                crop_rect[0], crop_rect[1],
                crop_rect[2], crop_rect[3]
            )
            digit_112 = digit_cut.resize(112, 112)
            digit_112.invert()
            digit_112.strech_char(1)
            digit_112.pix_to_ai()

            output = kpu.run_with_output(digit_112, getlist=True)
            best_value = max(output)
            model_digit = output.index(best_value)
            confidence = confidence_from_output(output, best_value)
            confidence_percent = int(confidence * 100 + 0.5)

            if (model_digit == TARGET_DIGIT and
                    confidence >= MIN_LEARN_CONFIDENCE):
                good_frames += 1
            else:
                good_frames = 0

            status = "T:%d P:%d C:%d %d/%d" % (
                TARGET_DIGIT,
                model_digit,
                confidence_percent,
                good_frames,
                LEARN_GOOD_FRAMES
            )
            print(status)

            digit_112.ai_to_pix()

            img.draw_rectangle(
                candidate.rect(), color=255, thickness=2
            )
            img.draw_cross(
                candidate.cx(), candidate.cy(),
                color=255, size=10
            )
            img.draw_image(digit_112, 204, 124)
            img.draw_rectangle(
                (203, 123, 114, 114),
                color=180, thickness=1
            )

            if good_frames >= LEARN_GOOD_FRAMES:
                reference = image.Image(
                    size=(112, 112),
                    copy_to_fb=False
                )
                reference.to_grayscale()
                reference.draw_image(digit_112, 0, 0)

                img.draw_string(
                    4, 30,
                    "REFERENCE LEARNED",
                    color=255, scale=2
                )
                lcd.display(img)

                print("==============================")
                print("REFERENCE LEARNED IN RAM")
                print("STEP 2: add other digit cards")
                print("==============================")

                del digit_cut
                del digit_112
                del output

                time.sleep_ms(1500)
                return reference

            del digit_cut
            del digit_112
            del output
        else:
            good_frames = 0
            print("LEARN: NO DIGIT")

        img.draw_rectangle(LEARN_ROI, color=180, thickness=2)
        img.draw_string(4, 4, status, color=255, scale=2)
        lcd.display(img)


target_template = learn_reference()

print("SEARCH STARTED")
print("Add 2 and 8; only target 5 may lock")

threshold_value = 85

target_active = False
hold_frames = 0
smooth_x = FRAME_CX
smooth_y = FRAME_CY
smooth_w = 0
smooth_h = 0

pending_rect = None
pending_votes = 0
pending_misses = 0


def passes_target_rules(detection):
    model_digit = detection[0]
    confidence = detection[1]
    similarity = detection[3]

    model_agrees = (
        model_digit == TARGET_DIGIT and
        confidence >= MIN_MODEL_CONFIDENCE
    )
    strong_template = similarity >= STRONG_TEMPLATE_SIMILARITY

    return (
        similarity >= MIN_TEMPLATE_SIMILARITY and
        (model_agrees or strong_template)
    )


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

    for blob in blobs:
        width = blob.w()
        height = blob.h()
        area = width * height

        if area <= 0:
            continue

        density = blob.pixels() * 100 // area

        if width < 5 or height < 24:
            continue
        if width > 145 or height > 185:
            continue
        if density < 9:
            continue
        if width > 125 and height > 125:
            continue

        score = blob.pixels() + height * 4
        inserted = False

        for index in range(len(candidate_items)):
            if score > candidate_items[index][0]:
                candidate_items.insert(index, (score, blob))
                inserted = True
                break

        if not inserted:
            candidate_items.append((score, blob))

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

        similarity_result = digit_112.get_similarity(
            target_template
        )
        similarity = similarity_result.mean()
        similarity_percent = int(similarity * 100)

        digit_112.pix_to_ai()
        output = kpu.run_with_output(
            digit_112, getlist=True
        )
        best_value = max(output)
        model_digit = output.index(best_value)
        confidence = confidence_from_output(
            output, best_value
        )
        confidence_percent = int(confidence * 100 + 0.5)

        detections.append(
            (
                model_digit,
                confidence,
                confidence_percent,
                similarity,
                similarity_percent,
                rect
            )
        )

        del digit_cut
        del digit_112
        del output

    best_detection = None
    best_similarity = -2.0
    second_similarity = -2.0

    for detection in detections:
        similarity = detection[3]

        if similarity > best_similarity:
            second_similarity = best_similarity
            best_similarity = similarity
            best_detection = detection
        elif similarity > second_similarity:
            second_similarity = similarity

    if best_detection:
        if second_similarity <= -1.5:
            similarity_margin = 2.0
        else:
            similarity_margin = (
                best_similarity - second_similarity
            )
    else:
        similarity_margin = 0.0

    search_verified = False

    if best_detection:
        search_verified = (
            passes_target_rules(best_detection) and
            (
                similarity_margin >= MIN_TEMPLATE_MARGIN or
                best_similarity >= STRONG_TEMPLATE_SIMILARITY
            )
        )

    just_acquired = False
    just_lost = False
    state_text = "SEARCH"

    if not target_active:
        if search_verified:
            current_rect = best_detection[5]

            if same_spatial_object(
                    current_rect,
                    pending_rect,
                    MAX_PENDING_JUMP):
                pending_votes += 1
            else:
                pending_rect = current_rect
                pending_votes = 1

            pending_misses = 0
        else:
            pending_misses += 1

            if pending_misses > MAX_PENDING_MISSES:
                pending_rect = None
                pending_votes = 0
                pending_misses = 0

        if pending_votes >= VOTES_TO_ACQUIRE and pending_rect:
            target_active = True
            just_acquired = True
            hold_frames = 0
            smooth_x = center_x(pending_rect)
            smooth_y = center_y(pending_rect)
            smooth_w = pending_rect[2]
            smooth_h = pending_rect[3]
            pending_rect = None
            pending_votes = 0
            pending_misses = 0
    else:
        track_detection = None
        nearest_distance = 1000000

        for detection in detections:
            if not passes_target_rules(detection):
                continue

            rect = detection[5]
            old_rect = (
                smooth_x - smooth_w // 2,
                smooth_y - smooth_h // 2,
                smooth_w,
                smooth_h
            )

            if not same_spatial_object(
                    rect, old_rect, MAX_TRACK_JUMP):
                continue

            distance = (
                abs(center_x(rect) - smooth_x) +
                abs(center_y(rect) - smooth_y)
            )

            if distance < nearest_distance:
                nearest_distance = distance
                track_detection = detection

        if track_detection:
            rect = track_detection[5]
            smooth_x = (
                smooth_x * 3 + center_x(rect)
            ) // 4
            smooth_y = (
                smooth_y * 3 + center_y(rect)
            ) // 4
            smooth_w = (smooth_w * 3 + rect[2]) // 4
            smooth_h = (smooth_h * 3 + rect[3]) // 4
            hold_frames = 0
        else:
            hold_frames += 1

        if hold_frames > MAX_HOLD_FRAMES:
            target_active = False
            just_lost = True
            hold_frames = 0
            smooth_w = 0
            smooth_h = 0
            pending_rect = None
            pending_votes = 0
            pending_misses = 0

    if just_acquired:
        print("ACQUIRED target=%d" % TARGET_DIGIT)

    if just_lost:
        print("LOST target=%d" % TARGET_DIGIT)

    for detection in detections:
        model_digit = detection[0]
        confidence_percent = detection[2]
        similarity_percent = detection[4]
        rect = detection[5]

        img.draw_rectangle(rect, color=100, thickness=1)

        label_y = rect[1] - 12
        if label_y < 0:
            label_y = 0

        img.draw_string(
            rect[0],
            label_y,
            "M%d C%d S%d" % (
                model_digit,
                confidence_percent,
                similarity_percent
            ),
            color=180,
            scale=1
        )

    if target_active:
        error_x = smooth_x - FRAME_CX
        error_y = smooth_y - FRAME_CY

        if hold_frames == 0:
            state_text = "TRACK"
            print("TRACK target=%d ex=%d ey=%d" % (
                TARGET_DIGIT, error_x, error_y
            ))
        else:
            state_text = "HOLD"
            print("HOLD target=%d missed=%d/%d" % (
                TARGET_DIGIT,
                hold_frames,
                MAX_HOLD_FRAMES
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
        img.draw_cross(
            smooth_x, smooth_y,
            color=255, size=14
        )
    else:
        best_sim_percent = int(best_similarity * 100)
        margin_percent = int(similarity_margin * 100)

        print(
            "SEARCH T=%d bestS=%d margin=%d ok=%d votes=%d/%d" %
            (
                TARGET_DIGIT,
                best_sim_percent,
                margin_percent,
                1 if search_verified else 0,
                pending_votes,
                VOTES_TO_ACQUIRE
            )
        )

        if pending_rect:
            img.draw_rectangle(
                pending_rect,
                color=220,
                thickness=2
            )

    img.draw_rectangle(
        SEARCH_ROI, color=140, thickness=1
    )
    img.draw_cross(
        FRAME_CX, FRAME_CY,
        color=160, size=10
    )
    img.draw_string(
        4,
        4,
        "%s T:%d V:%d/%d" % (
            state_text,
            TARGET_DIGIT,
            pending_votes,
            VOTES_TO_ACQUIRE
        ),
        color=255,
        scale=2
    )

    lcd.display(img)
