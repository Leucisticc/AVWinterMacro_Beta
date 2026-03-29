import time

import cv2
import mss
import numpy as np
import pyautogui
from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Controller


pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


# Screen-space region containing only the minigame board.
# CAPTURE_REGION = (612, 250, 276, 502)
CAPTURE_REGION = (612, 580, 276, 75)

# Local y inside CAPTURE_REGION where notes should be hit.
HIT_LINE_Y = 35

# Size of the sampled box around the hit line for each lane.
SAMPLE_BOX_WIDTH = 18
SAMPLE_BOX_HEIGHT = 28

# Detection threshold: press when current brightness falls below this
# fraction of the lane's calibrated baseline brightness.
DISAPPEAR_RATIO = 0.98

# Alternative threshold for "any change" mode. Fires when the brightness
# differs from baseline by at least this fraction.
CHANGE_RATIO = 0.02

# Detection mode:
# "disappear" = trigger only when brightness drops below DISAPPEAR_RATIO
# "change" = trigger when brightness changes either darker or brighter
DETECTION_MODE = "change"

# How often the same lane may fire again.
LANE_COOLDOWN_SECONDS = 0.055

# Number of frames used to learn each lane's normal brightness.
CALIBRATION_FRAMES = 40

# When True, use SAVED_BASELINE below instead of recalibrating on startup.
USE_SAVED_BASELINE = True

# Saved lane brightness values from a known good run.
SAVED_BASELINE = {
    "a": 64.4,
    "s": 56.2,
    "d": 55.3,
    "f": 55.9,
    "g": 59.2,
}

# Sleep between loops. Set to 0.0 for max speed.d
LOOP_SLEEP_SECONDS = 0.0

# Optional preview.
SHOW_DEBUG_PREVIEW = False

# Press N to toggle active scanning and K to exit the script.
TOGGLE_KEY = "n"
KILL_KEY = "k"

# Lane x values are local to CAPTURE_REGION.
LANES = [
    {"name": "a", "key": "a", "x": 25},
    {"name": "s", "key": "s", "x": 80},
    {"name": "d", "key": "d", "x": 137},
    {"name": "f", "key": "f", "x": 193},
    {"name": "g", "key": "g", "x": 248},
]


keyboard_controller = Controller()
running = True
macro_enabled = False
pending_enable = False


def kill():
    global running
    running = False


def on_press(key):
    global macro_enabled, pending_enable
    try:
        if not hasattr(key, "char") or not key.char:
            return

        pressed = key.char.lower()
        if pressed == KILL_KEY:
            kill()
        elif pressed == TOGGLE_KEY:
            if macro_enabled:
                macro_enabled = False
                pending_enable = False
                print("Macro paused.")
            else:
                pending_enable = True
                print("Macro enable requested. Calibrating on next loop.")
    except Exception:
        pass


listener = pynput_keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()


def tap(key: str, hold: float = 0.03):
    try:
        keyboard_controller.press(key)
        time.sleep(hold)
        keyboard_controller.release(key)
    except Exception:
        pyautogui.press(str(key))


def _sample_bounds(center_x: int, frame_shape: tuple[int, int, int]) -> tuple[int, int, int, int]:
    frame_h, frame_w = frame_shape[:2]
    half_w = max(2, SAMPLE_BOX_WIDTH // 2)
    half_h = max(2, SAMPLE_BOX_HEIGHT // 2)
    left = max(0, int(center_x) - half_w)
    right = min(frame_w, int(center_x) + half_w)
    top = max(0, int(HIT_LINE_Y) - half_h)
    bottom = min(frame_h, int(HIT_LINE_Y) + half_h)
    return left, top, right, bottom


def _lane_brightness(gray_frame: np.ndarray, lane: dict) -> float:
    left, top, right, bottom = _sample_bounds(lane["x"], gray_frame.shape)
    sample = gray_frame[top:bottom, left:right]
    if sample.size == 0:
        return 0.0
    return float(np.mean(sample))


def _calibrate(sct: mss.mss, region: dict) -> dict[str, float]:
    sums = {lane["name"]: 0.0 for lane in LANES}

    print(f"Calibrating for {CALIBRATION_FRAMES} frames. Keep the board idle.")
    for _ in range(CALIBRATION_FRAMES):
        shot = sct.grab(region)
        frame = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for lane in LANES:
            sums[lane["name"]] += _lane_brightness(gray, lane)
        time.sleep(0.01)

    baseline = {
        lane["name"]: sums[lane["name"]] / max(1, CALIBRATION_FRAMES)
        for lane in LANES
    }
    print("Baseline brightness:", {k: round(v, 1) for k, v in baseline.items()})
    return baseline


def _load_baseline(sct: mss.mss, region: dict) -> dict[str, float]:
    if USE_SAVED_BASELINE:
        baseline = {
            lane["name"]: float(SAVED_BASELINE.get(lane["name"], 0.0))
            for lane in LANES
        }
        print("Using saved baseline:", {k: round(v, 1) for k, v in baseline.items()})
        return baseline

    return _calibrate(sct, region)


def _draw_debug_overlay(frame: np.ndarray, baseline: dict[str, float], current: dict[str, float]) -> np.ndarray:
    out = frame.copy()
    cv2.line(out, (0, HIT_LINE_Y), (out.shape[1], HIT_LINE_Y), (255, 255, 255), 2)

    for lane in LANES:
        left, top, right, bottom = _sample_bounds(lane["x"], out.shape)
        base = baseline.get(lane["name"], 1.0)
        now = current.get(lane["name"], 0.0)
        ratio = now / base if base > 0 else 0.0
        if DETECTION_MODE == "change":
            delta_ratio = abs(now - base) / base if base > 0 else 0.0
            active = delta_ratio >= CHANGE_RATIO
        else:
            active = ratio <= DISAPPEAR_RATIO
        color = (0, 0, 255) if active else (0, 255, 0)

        cv2.rectangle(out, (left, top), (right, bottom), color, 2)
        cv2.putText(
            out,
            f'{lane["key"]} {ratio:.2f}',
            (max(0, left - 6), max(15, top - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            color,
            1,
            cv2.LINE_AA,
        )

    return out


def run():
    global running, macro_enabled, pending_enable

    region = {
        "left": int(CAPTURE_REGION[0]),
        "top": int(CAPTURE_REGION[1]),
        "width": int(CAPTURE_REGION[2]),
        "height": int(CAPTURE_REGION[3]),
    }
    last_fire_at = {lane["name"]: 0.0 for lane in LANES}

    print("Skele King macro running.")
    print(f"Region: {CAPTURE_REGION}")
    print(f"Hit line: y={HIT_LINE_Y}")
    print(f"Detection mode: {DETECTION_MODE}")
    print(f"Disappear ratio threshold: {DISAPPEAR_RATIO}")
    print(f"Change ratio threshold: {CHANGE_RATIO}")
    print(f"Use saved baseline: {USE_SAVED_BASELINE}")
    print(f"Press {TOGGLE_KEY.upper()} to start/pause.")
    print(f"Press {KILL_KEY.upper()} to stop.")

    with mss.mss() as sct:
        baseline = {
            lane["name"]: float(SAVED_BASELINE.get(lane["name"], 0.0))
            for lane in LANES
        } if USE_SAVED_BASELINE else {}

        while running:
            if pending_enable:
                baseline = _load_baseline(sct, region)
                macro_enabled = True
                pending_enable = False
                print("Macro enabled.")

            started = time.perf_counter()
            shot = sct.grab(region)
            frame = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            now = time.perf_counter()
            brightness_now: dict[str, float] = {}

            for lane in LANES:
                level = _lane_brightness(gray, lane)
                brightness_now[lane["name"]] = level

                if not macro_enabled:
                    continue

                base = baseline.get(lane["name"], 0.0)
                if base <= 1.0:
                    continue

                ratio = level / base
                if DETECTION_MODE == "change":
                    delta_ratio = abs(level - base) / base
                    if delta_ratio < CHANGE_RATIO:
                        continue
                else:
                    if ratio > DISAPPEAR_RATIO:
                        continue

                if now - last_fire_at[lane["name"]] < LANE_COOLDOWN_SECONDS:
                    continue

                tap(lane["key"])
                last_fire_at[lane["name"]] = now

            if SHOW_DEBUG_PREVIEW:
                preview = _draw_debug_overlay(frame, baseline, brightness_now)
                cv2.imshow("SkeleKing Debug", preview)
                if (cv2.waitKey(1) & 0xFF) == 27:
                    running = False
                    break

            elapsed = time.perf_counter() - started
            remaining = LOOP_SLEEP_SECONDS - elapsed
            if remaining > 0:
                time.sleep(remaining)

    if SHOW_DEBUG_PREVIEW:
        cv2.destroyAllWindows()

    print("Skele King macro stopped.")


if __name__ == "__main__":
    run()
