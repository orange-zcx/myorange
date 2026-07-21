import sensor
import image
import lcd
import time
import math
import gc
from maix import KPU
from fpioa_manager import fm
from machine import UART

# K210 digit target anti-shake test.
# Stage 1 assumption: one standard digit card and a simple background.

MODEL_FLASH_ADDR = 0x300000
MODEL_SIZE = 550124

TARGET_DIGIT = 5             # Change this value from 0 to 9.
SEARCH_ROI = (20, 20, 280, 200)
FRAME_CX = 160
FRAME_CY = 120

MIN_VOTE_CONFIDENCE = 0.65
VOTE_WINDOW = 7
VOTES_TO_ACQUIRE = 4
MAX_HOLD_FRAMES = 8
MAX_TRACK_JUMP = 85
MAX_EXPOSURE_US = 12000
UART_SEND_INTERVAL_MS = 100

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

fm.register(7, fm.fpioa.UART1_TX, force=True)
uart = UART(
    UART.UART1,
    115200,
    8,
    None,
    1,
    timeout=1000,
    read_buf_len=4096
)
print("UART1 TX READY: GPIO7, 115200 8N1")

print("Loading MNIST model from Flash")
print("Address: 0x%X size: %d" % (MODEL_FLASH_ADDR, MODEL_SIZE))
print("Exposure: %d us" % sensor.get_exposure_us())
print("Target digit: %d" % TARGET_DIGIT)

kpu = KPU()
kpu.load_kmodel(MODEL_FLASH_ADDR, MODEL_SIZE)
print("MODEL LOAD OK")
print("Anti-shake: 4 votes in 7 frames, hold up to 8 missed frames")

threshold_value = 85
vote_history = [-1, -1, -1, -1, -1, -1, -1]
vote_index = 0

target_active = False
hold_frames = 0
smooth_x = FRAME_CX
smooth_y = FRAME_CY
smooth_w = 0
smooth_h = 0

clock = time.clock()
last_uart_send_ms = time.ticks_ms()


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

    candidate = None
    best_score = -1000000

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

        if target_active:
            distance = abs(b.cx() - smooth_x) + abs(b.cy() - smooth_y)
            score = b.pixels() + bh * 4 - distance * 8
        else:
            center_distance = (
                abs(b.cx() - FRAME_CX) +
                abs(b.cy() - FRAME_CY)
            )
            score = b.pixels() + bh * 4 - center_distance

        if score > best_score:
            candidate = b
            best_score = score

    model_digit = -1
    confidence = 0.0
    confidence_percent = 0
    current_vote = -1
    digit_112 = None
    continuity_ok = False

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
        model_digit = out.index(best_value)
        confidence = confidence_from_output(out, best_value)
        confidence_percent = int(confidence * 100 + 0.5)

        if confidence >= MIN_VOTE_CONFIDENCE:
            current_vote = model_digit

        if target_active:
            jump = (
                abs(candidate.cx() - smooth_x) +
                abs(candidate.cy() - smooth_y)
            )

            size_ok = True
            if smooth_w > 0 and smooth_h > 0:
                current_area = candidate.w() * candidate.h()
                smooth_area = smooth_w * smooth_h
                if current_area * 3 < smooth_area:
                    size_ok = False
                if current_area > smooth_area * 3:
                    size_ok = False

            continuity_ok = jump <= MAX_TRACK_JUMP and size_ok

        del digit_cut
        del out

    vote_history[vote_index] = current_vote
    vote_index += 1
    if vote_index >= VOTE_WINDOW:
        vote_index = 0

    target_votes = 0
    for vote in vote_history:
        if vote == TARGET_DIGIT:
            target_votes += 1

    state_text = "SEARCH"
    just_acquired = False
    just_lost = False

    if not target_active:
        if candidate and target_votes >= VOTES_TO_ACQUIRE:
            target_active = True
            just_acquired = True
            hold_frames = 0
            smooth_x = candidate.cx()
            smooth_y = candidate.cy()
            smooth_w = candidate.w()
            smooth_h = candidate.h()
    else:
        if candidate and continuity_ok:
            # 1/4 new position + 3/4 old position removes camera shake.
            smooth_x = (smooth_x * 3 + candidate.cx()) // 4
            smooth_y = (smooth_y * 3 + candidate.cy()) // 4
            smooth_w = (smooth_w * 3 + candidate.w()) // 4
            smooth_h = (smooth_h * 3 + candidate.h()) // 4
            hold_frames = 0
        else:
            hold_frames += 1

        if hold_frames > MAX_HOLD_FRAMES:
            target_active = False
            just_lost = True
            hold_frames = 0
            smooth_w = 0
            smooth_h = 0
            vote_history = [-1, -1, -1, -1, -1, -1, -1]

    if just_acquired:
        print("ACQUIRED target=%d votes=%d/7" % (
            TARGET_DIGIT, target_votes
        ))
        message = "A:%d\n" % TARGET_DIGIT
        uart.write(message)
        print("UART SEND:", message)

    if just_lost:
        print("LOST target=%d" % TARGET_DIGIT)
        message = "N:%d\n" % TARGET_DIGIT
        uart.write(message)
        print("UART SEND:", message)

    if target_active:
        error_x = smooth_x - FRAME_CX
        error_y = smooth_y - FRAME_CY
        target_size = smooth_w * smooth_h

        if hold_frames == 0:
            state_text = "TRACK"
            print(
                "TRACK target=%d ex=%d ey=%d size=%d votes=%d/7 model=%d conf=%d%%" %
                (
                    TARGET_DIGIT, error_x, error_y, target_size,
                    target_votes, model_digit, confidence_percent
                )
            )

            now_ms = time.ticks_ms()
            if time.ticks_diff(now_ms, last_uart_send_ms) >= UART_SEND_INTERVAL_MS:
                quality = target_votes * 100 // VOTE_WINDOW
                message = "P:%d,%d,%d,%d,%d\n" % (
                    TARGET_DIGIT, error_x, error_y, target_size, quality
                )
                uart.write(message)
                print("UART SEND:", message)
                last_uart_send_ms = now_ms
        else:
            state_text = "HOLD"
            print("HOLD target=%d missed=%d/%d" % (
                TARGET_DIGIT, hold_frames, MAX_HOLD_FRAMES
            ))

            if hold_frames == 1:
                message = "H:%d\n" % TARGET_DIGIT
                uart.write(message)
                print("UART SEND:", message)

        img.draw_cross(smooth_x, smooth_y, color=255, size=12)
        img.draw_rectangle(
            (
                smooth_x - smooth_w // 2,
                smooth_y - smooth_h // 2,
                smooth_w,
                smooth_h
            ),
            color=255,
            thickness=2
        )
    else:
        print("SEARCH target=%d model=%d conf=%d%% votes=%d/7" % (
            TARGET_DIGIT, model_digit, confidence_percent, target_votes
        ))

    # Draw after all image processing.
    img.draw_rectangle(SEARCH_ROI, color=160, thickness=1)
    img.draw_cross(FRAME_CX, FRAME_CY, color=180, size=10)

    if candidate and not target_active:
        img.draw_rectangle(candidate.rect(), color=110, thickness=1)

    if digit_112:
        digit_112.ai_to_pix()
        img.draw_image(digit_112, 204, 124)
        img.draw_rectangle((203, 123, 114, 114), color=180, thickness=1)
        del digit_112

    img.draw_string(
        4, 4,
        "%s T:%d V:%d/7" % (state_text, TARGET_DIGIT, target_votes),
        color=255,
        scale=2
    )

    lcd.display(img)
