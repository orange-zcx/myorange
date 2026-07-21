import sensor
import image
import lcd
import time
import gc

# Memory-light specified target lock using a 4x4 stroke signature.
# Lower D score means the candidate is more similar to the learned target.

TARGET_NAME = 5

LEARN_ROI = (80, 40, 160, 160)
SEARCH_ROI = (10, 10, 300, 220)
FRAME_CX = 160
FRAME_CY = 120
MAX_CANDIDATES = 3

GRID_SIZE = 4
CELL_SIZE = 28
SIGNATURE_LENGTH = 16
LEARN_STABLE_FRAMES = 8

MAX_AVERAGE_DIFFERENCE = 26
STRONG_AVERAGE_DIFFERENCE = 12
MIN_DIFFERENCE_MARGIN = 5

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

exposure = sensor.get_exposure_us()
if exposure > MAX_EXPOSURE_US:
    exposure = MAX_EXPOSURE_US
sensor.set_auto_exposure(False, exposure_us=exposure)

lcd.init()
lcd.rotation(0)

print("4x4 STROKE SIGNATURE TARGET LOCK")
print("STEP 1: show only target %d in center" % TARGET_NAME)

clock = time.clock()


def center_x(rect):
    return rect[0] + rect[2] // 2


def center_y(rect):
    return rect[1] + rect[3] // 2


def same_object(rect_a, rect_b, max_jump):
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


def square_crop(rect, max_side=180):
    cx = center_x(rect)
    cy = center_y(rect)
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


def normalize_candidate(img, rect, max_side=180):
    crop = square_crop(rect, max_side)
    cut = img.cut(crop[0], crop[1], crop[2], crop[3])
    normalized = cut.resize(112, 112)
    del cut

    normalized.invert()
    normalized.strech_char(1)
    return normalized


def stroke_signature(normalized):
    signature = []

    for grid_y in range(GRID_SIZE):
        for grid_x in range(GRID_SIZE):
            roi = (
                grid_x * CELL_SIZE,
                grid_y * CELL_SIZE,
                CELL_SIZE,
                CELL_SIZE
            )
            statistics = normalized.get_statistics(roi=roi)
            signature.append(statistics.mean())

    return signature


def signature_difference(signature_a, signature_b):
    total = 0

    for index in range(SIGNATURE_LENGTH):
        total += abs(signature_a[index] - signature_b[index])

    return total // SIGNATURE_LENGTH


def update_threshold(img, roi, old_threshold):
    histogram = img.get_histogram(roi=roi)
    dark = histogram.get_percentile(0.03).value()
    light = histogram.get_percentile(0.80).value()
    measured = dark + ((light - dark) * 38 // 100)

    if measured < 45:
        measured = 45
    elif measured > 145:
        measured = 145

    return (old_threshold * 3 + measured) // 4


def collect_candidates(img, roi, threshold, maximum):
    blobs = img.find_blobs(
        [(0, threshold)],
        roi=roi,
        pixels_threshold=60,
        area_threshold=80,
        merge=False
    )

    items = []

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

        for index in range(len(items)):
            if score > items[index][0]:
                items.insert(index, (score, blob.rect()))
                inserted = True
                break

        if not inserted:
            items.append((score, blob.rect()))

        if len(items) > maximum:
            items.pop()

    return items


def learn_signature():
    threshold = 85
    stable_frames = 0
    last_rect = None
    signature_sum = [0] * SIGNATURE_LENGTH

    while True:
        gc.collect()
        img = sensor.snapshot()
        threshold = update_threshold(
            img, LEARN_ROI, threshold
        )

        candidates = collect_candidates(
            img, LEARN_ROI, threshold, 3
        )

        chosen_rect = None
        best_score = -100000

        for item in candidates:
            rect = item[1]
            dx = abs(center_x(rect) - FRAME_CX)
            dy = abs(center_y(rect) - FRAME_CY)
            score = item[0] - dx * 5 - dy * 4

            if score > best_score:
                best_score = score
                chosen_rect = rect

        status = "LEARN T:%d %d/%d" % (
            TARGET_NAME,
            stable_frames,
            LEARN_STABLE_FRAMES
        )

        if chosen_rect:
            if same_object(
                    chosen_rect, last_rect, 35):
                stable_frames += 1
            else:
                stable_frames = 1
                signature_sum = [0] * SIGNATURE_LENGTH

            last_rect = chosen_rect
            normalized = normalize_candidate(
                img, chosen_rect, 156
            )
            signature = stroke_signature(normalized)

            for index in range(SIGNATURE_LENGTH):
                signature_sum[index] += signature[index]

            status = "LEARN T:%d %d/%d" % (
                TARGET_NAME,
                stable_frames,
                LEARN_STABLE_FRAMES
            )
            print(status)

            img.draw_rectangle(
                chosen_rect, color=255, thickness=2
            )
            img.draw_cross(
                center_x(chosen_rect),
                center_y(chosen_rect),
                color=255,
                size=10
            )
            img.draw_image(normalized, 204, 124)
            img.draw_rectangle(
                (203, 123, 114, 114),
                color=180,
                thickness=1
            )

            if stable_frames >= LEARN_STABLE_FRAMES:
                reference_signature = []

                for index in range(SIGNATURE_LENGTH):
                    reference_signature.append(
                        signature_sum[index] //
                        stable_frames
                    )

                print("==============================")
                print("SIGNATURE LEARNED")
                print(reference_signature)
                print("STEP 2: add other digit cards")
                print("==============================")

                img.draw_string(
                    4, 30,
                    "SIGNATURE LEARNED",
                    color=255,
                    scale=2
                )
                lcd.display(img)

                del normalized
                del signature
                time.sleep_ms(1200)
                return reference_signature

            del normalized
            del signature
        else:
            stable_frames = 0
            last_rect = None
            signature_sum = [0] * SIGNATURE_LENGTH
            print("LEARN: NO TARGET")

        img.draw_rectangle(
            LEARN_ROI, color=180, thickness=2
        )
        img.draw_string(
            4, 4, status, color=255, scale=2
        )
        lcd.display(img)


reference_signature = learn_signature()
gc.collect()

print("SEARCH STARTED")
print("D score: lower is more similar")

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

while True:
    gc.collect()
    img = sensor.snapshot()
    threshold_value = update_threshold(
        img, SEARCH_ROI, threshold_value
    )

    candidate_items = collect_candidates(
        img,
        SEARCH_ROI,
        threshold_value,
        MAX_CANDIDATES
    )

    # detection tuple: average signature difference, rectangle
    detections = []

    for item in candidate_items:
        rect = item[1]
        normalized = normalize_candidate(img, rect)
        signature = stroke_signature(normalized)
        difference = signature_difference(
            signature, reference_signature
        )

        detections.append((difference, rect))

        del normalized
        del signature

    best_detection = None
    best_difference = 1000000
    second_difference = 1000000

    for detection in detections:
        difference = detection[0]

        if difference < best_difference:
            second_difference = best_difference
            best_difference = difference
            best_detection = detection
        elif difference < second_difference:
            second_difference = difference

    if best_detection:
        if second_difference >= 999999:
            difference_margin = 1000
        else:
            difference_margin = (
                second_difference - best_difference
            )
    else:
        difference_margin = 0

    search_verified = False

    if best_detection:
        search_verified = (
            best_difference <= MAX_AVERAGE_DIFFERENCE and
            (
                difference_margin >= MIN_DIFFERENCE_MARGIN or
                best_difference <= STRONG_AVERAGE_DIFFERENCE
            )
        )

    just_acquired = False
    just_lost = False
    state_text = "SEARCH"

    if not target_active:
        if search_verified:
            current_rect = best_detection[1]

            if same_object(
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

        old_rect = (
            smooth_x - smooth_w // 2,
            smooth_y - smooth_h // 2,
            smooth_w,
            smooth_h
        )

        for detection in detections:
            difference = detection[0]
            rect = detection[1]

            if difference > MAX_AVERAGE_DIFFERENCE:
                continue
            if not same_object(
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
            rect = track_detection[1]
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
        print("ACQUIRED target=%d" % TARGET_NAME)

    if just_lost:
        print("LOST target=%d" % TARGET_NAME)

    for detection in detections:
        difference = detection[0]
        rect = detection[1]

        img.draw_rectangle(
            rect, color=100, thickness=1
        )

        label_y = rect[1] - 12
        if label_y < 0:
            label_y = 0

        img.draw_string(
            rect[0],
            label_y,
            "D%d" % difference,
            color=180,
            scale=1
        )

    if target_active:
        error_x = smooth_x - FRAME_CX
        error_y = smooth_y - FRAME_CY

        if hold_frames == 0:
            state_text = "TRACK"
            print("TRACK T=%d ex=%d ey=%d" % (
                TARGET_NAME, error_x, error_y
            ))
        else:
            state_text = "HOLD"
            print("HOLD T=%d missed=%d/%d" % (
                TARGET_NAME,
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
            smooth_x,
            smooth_y,
            color=255,
            size=14
        )
    else:
        print(
            "SEARCH T=%d bestD=%d margin=%d ok=%d votes=%d/%d" %
            (
                TARGET_NAME,
                best_difference,
                difference_margin,
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
        SEARCH_ROI,
        color=140,
        thickness=1
    )
    img.draw_cross(
        FRAME_CX,
        FRAME_CY,
        color=160,
        size=10
    )
    img.draw_string(
        4,
        4,
        "%s T:%d V:%d/%d" % (
            state_text,
            TARGET_NAME,
            pending_votes,
            VOTES_TO_ACQUIRE
        ),
        color=255,
        scale=2
    )

    lcd.display(img)
