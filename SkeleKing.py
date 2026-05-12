import time
import tkinter as tk

import cv2
import mss
import numpy as np
import pyautogui
from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Controller
from Tools import gameHelpers as gh

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


# Screen-space region containing only the minigame board.
# CAPTURE_REGION = (612, 580, 276, 75)
CAPTURE_REGION = (612, 630, 276, 75)

# Local y inside CAPTURE_REGION where notes should be hit.
HIT_LINE_Y = 50
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

# When True, a lane taps only once when it first becomes detected.
# When False, a lane can tap again while still detected after LANE_COOLDOkWN_SECONDS.
TAP_ON_DETECTION_START_ONLY = True

# Number of frames used to learn each lane's normal brightness.
CALIBRATION_FRAMES = 40

# When True, use SAVED_BASELINE below instead of recalibrating on startup.
USE_SAVED_BASELINE = True

# Saved lane brightness values from a known good run.
# SAVED_BASELINE = {
#     "a": 64.4,
#     "s": 56.2,
#     "d": 55.3,
#     "f": 55.9,
#     "g": 59.2,
# }

SAVED_BASELINE = {
    "a": 75.7,
    "s": 69.4,
    "d": 69.5,
    "f": 69.7,
    "g": 74.4,
}

# Sleep between loops. Set to 0.0 for max speed.d
LOOP_SLEEP_SECONDS = 0.0

# Optional preview.
SHOW_DEBUG_PREVIEW = True
DEBUG_WINDOW_NAME = "SkeleKing Debug"

# Press N to toggle active scanning and K to exit the script.
TOGGLE_KEY = "n"
KILL_KEY = "k"
POSITION_KEY = "p"
CAPTURE_CALIBRATION_KEY = "c"

# Lane x values are absolute screen coordinates.
LANES = [
    {"name": "a", "key": "a", "x": 638},
    {"name": "s", "key": "s", "x": 694},
    {"name": "d", "key": "d", "x": 750},
    {"name": "f", "key": "f", "x": 806},
    {"name": "g", "key": "g", "x": 861},
]


keyboard_controller = Controller()
running = True
macro_enabled = False
pending_enable = False
pending_focus_roblox = False
pending_capture_calibration_hotkey = False
capture_calibration_active = False
capture_calibration_points: list[tuple[str, int, int]] = []
capture_config_version = 0
tk_root = None
region_overlay = None
listener = None

CAPTURE_CALIBRATION_STEPS = [
    ("a", "center of the A key lane at the hit line"),
    ("s", "center of the S key lane at the hit line"),
    ("d", "center of the D key lane at the hit line"),
    ("f", "center of the F key lane at the hit line"),
    ("g", "center of the G key lane at the hit line"),
]


class RegionOverlay:
    _ALPHA = 0.18
    _FILL = "#4488ff"
    _OUTLINE = "#88ccff"

    def __init__(self, root, on_region_selected):
        self.root = root
        self.on_region_selected = on_region_selected
        self.active = False
        self._win = None
        self._cnv = None
        self._rect = None
        self._start = None
        self._ox = 0
        self._oy = 0

    def open(self):
        if self.active:
            self._close()

        self.active = True
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        win.wm_attributes("-alpha", self._ALPHA)
        win.configure(bg="black")
        win.geometry(f"{sw}x{sh}+0+0")
        win.update()
        self._ox = win.winfo_rootx()
        self._oy = win.winfo_rooty()
        self._win = win

        cnv = tk.Canvas(
            win,
            width=sw,
            height=sh,
            bg="black",
            highlightthickness=0,
            cursor="crosshair",
        )
        cnv.pack()
        cnv.bind("<Button-1>", self._press)
        cnv.bind("<B1-Motion>", self._drag)
        cnv.bind("<ButtonRelease-1>", self._release)
        cnv.bind("<Escape>", lambda _: self._close())
        cnv.focus_set()
        self._cnv = cnv

        print("[Capture Setup] Click and drag the note/key capture region. Release to confirm. Esc cancels.")

    def _press(self, event):
        self._start = (event.x, event.y)

    def _drag(self, event):
        if self._start is None:
            return

        if self._rect:
            self._cnv.delete(self._rect)

        sx, sy = self._start
        self._rect = self._cnv.create_rectangle(
            sx,
            sy,
            event.x,
            event.y,
            outline=self._OUTLINE,
            width=2,
            fill=self._FILL,
            stipple="gray25",
        )

    def _release(self, event):
        if self._start is None:
            return

        x1 = self._start[0] + self._ox
        y1 = self._start[1] + self._oy
        x2 = event.x + self._ox
        y2 = event.y + self._oy
        left = min(x1, x2)
        top = min(y1, y2)
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        self._close()

        if width <= 0 or height <= 0:
            print("[Capture Setup] Region was empty; try again with C.")
            return

        self.on_region_selected((int(left), int(top), int(width), int(height)))

    def _close(self):
        self.active = False
        self._start = None
        if self._win:
            self._win.destroy()
            self._win = None
        self._cnv = None
        self._rect = None


def kill():
    global running
    running = False


def _print_next_capture_calibration_step():
    if len(capture_calibration_points) >= len(CAPTURE_CALIBRATION_STEPS):
        return

    _, description = CAPTURE_CALIBRATION_STEPS[len(capture_calibration_points)]
    print(f"[Capture Setup] Move your mouse to the {description}, then press {CAPTURE_CALIBRATION_KEY.upper()}.")


def _finish_capture_calibration():
    global HIT_LINE_Y, capture_calibration_active, capture_config_version

    points = {name: (x, y) for name, x, y in capture_calibration_points}
    left = CAPTURE_REGION[0]
    top = CAPTURE_REGION[1]

    lane_y_values = []
    for lane in LANES:
        lane_x, lane_y = points[lane["name"]]
        lane["x"] = int(lane_x)
        lane_y_values.append(lane_y - top)

    HIT_LINE_Y = int(round(sum(lane_y_values) / max(1, len(lane_y_values))))
    capture_config_version += 1
    capture_calibration_active = False

    lane_lines = "\n".join(
        f'    {{"name": "{lane["name"]}", "key": "{lane["key"]}", "x": {lane["x"]}}},'
        for lane in LANES
    )
    print("[Capture Setup] Complete. Live capture values updated.")
    print("[Capture Setup] Copy these into SkeleKing.py if they look correct:")
    print(f"CAPTURE_REGION = {CAPTURE_REGION}")
    print(f"HIT_LINE_Y = {HIT_LINE_Y}")
    print("LANES = [")
    print(lane_lines)
    print("]")


def _spread_lanes_across_capture_region():
    global HIT_LINE_Y

    _, _, width, height = CAPTURE_REGION
    lane_count = max(1, len(LANES))
    half_sample_width = max(2, SAMPLE_BOX_WIDTH // 2)

    for index, lane in enumerate(LANES):
        lane_center = int(round(width * ((index + 0.5) / lane_count)))
        lane_center = max(half_sample_width, min(width - half_sample_width, lane_center))
        lane["x"] = int(CAPTURE_REGION[0] + lane_center)

    HIT_LINE_Y = max(2, min(height - 2, int(round(height * 0.5))))


def _set_calibrated_capture_region(region: tuple[int, int, int, int]):
    global CAPTURE_REGION, capture_calibration_active, capture_calibration_points, capture_config_version

    CAPTURE_REGION = region
    _spread_lanes_across_capture_region()
    capture_calibration_active = True
    capture_calibration_points = []
    capture_config_version += 1
    print(f"[Capture Setup] Region selected: CAPTURE_REGION = {CAPTURE_REGION}")
    print("[Capture Setup] Seeded lane boxes evenly across the new region.")
    _print_next_capture_calibration_step()


def _handle_capture_calibration_hotkey():
    global capture_calibration_active, capture_calibration_points

    if not capture_calibration_active:
        if region_overlay is None:
            print("[Capture Setup] Region overlay is not ready yet.")
            return

        print("[Capture Setup] Started.")
        region_overlay.open()
        return

    step_name, description = CAPTURE_CALIBRATION_STEPS[len(capture_calibration_points)]
    x, y = pyautogui.position()
    capture_calibration_points.append((step_name, int(x), int(y)))
    print(f"[Capture Setup] Recorded {description}: ({int(x)}, {int(y)})")

    if len(capture_calibration_points) >= len(CAPTURE_CALIBRATION_STEPS):
        _finish_capture_calibration()
    else:
        _print_next_capture_calibration_step()


def on_press(key):
    global macro_enabled, pending_enable, pending_focus_roblox, pending_capture_calibration_hotkey
    try:
        if not hasattr(key, "char") or not key.char:
            return

        pressed = key.char.lower()
        if pressed == KILL_KEY:
            kill()
        elif pressed == POSITION_KEY:
            gh.ensure_roblox_window_positioned()
        elif pressed == CAPTURE_CALIBRATION_KEY:
            pending_capture_calibration_hotkey = True
        elif pressed == TOGGLE_KEY:
            if macro_enabled:
                macro_enabled = False
                pending_enable = False
                print("Macro paused.")
            else:
                pending_focus_roblox = True
                pending_enable = True
                print("Macro enable requested. Calibrating on next loop.")
    except Exception:
        pass


def tap(key: str, hold: float = 0.03):
    try:
        pyautogui.keyDown(str(key))
        time.sleep(hold)
        pyautogui.keyUp(str(key))
    except Exception:
        pyautogui.press(str(key))


def _sample_bounds(center_x: int, frame_shape: tuple[int, int, int]) -> tuple[int, int, int, int]:
    frame_h, frame_w = frame_shape[:2]
    region_w = max(1, int(CAPTURE_REGION[2]))
    region_h = max(1, int(CAPTURE_REGION[3]))
    scale_x = frame_w / region_w
    scale_y = frame_h / region_h
    center_x_px = int(round(center_x * scale_x))
    hit_line_y_px = int(round(HIT_LINE_Y * scale_y))
    half_w = max(2, int(round((SAMPLE_BOX_WIDTH * scale_x) / 2)))
    half_h = max(2, int(round((SAMPLE_BOX_HEIGHT * scale_y) / 2)))
    left = max(0, center_x_px - half_w)
    right = min(frame_w, center_x_px + half_w)
    top = max(0, hit_line_y_px - half_h)
    bottom = min(frame_h, hit_line_y_px + half_h)
    return left, top, right, bottom


def _lane_brightness(gray_frame: np.ndarray, lane: dict) -> float:
    left, top, right, bottom = _sample_bounds(_lane_local_x(lane), gray_frame.shape)
    sample = gray_frame[top:bottom, left:right]
    if sample.size == 0:
        return 0.0
    return float(np.mean(sample))


def _lane_local_x(lane: dict) -> int:
    return int(lane["x"] - CAPTURE_REGION[0])


def _capture_region_dict() -> dict[str, int]:
    return {
        "left": int(CAPTURE_REGION[0]),
        "top": int(CAPTURE_REGION[1]),
        "width": int(CAPTURE_REGION[2]),
        "height": int(CAPTURE_REGION[3]),
    }


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
    scale_y = out.shape[0] / max(1, int(CAPTURE_REGION[3]))
    hit_line_y_px = int(round(HIT_LINE_Y * scale_y))
    cv2.line(out, (0, hit_line_y_px), (out.shape[1], hit_line_y_px), (255, 255, 255), 2)

    for lane in LANES:
        left, top, right, bottom = _sample_bounds(_lane_local_x(lane), out.shape)
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
    global running, macro_enabled, pending_enable, pending_focus_roblox, pending_capture_calibration_hotkey, tk_root, region_overlay, listener

    tk_root = tk.Tk()
    tk_root.withdraw()
    region_overlay = RegionOverlay(tk_root, _set_calibrated_capture_region)

    listener = pynput_keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()

    region = _capture_region_dict()
    seen_capture_config_version = capture_config_version
    last_fire_at = {lane["name"]: 0.0 for lane in LANES}
    lane_was_detected = {lane["name"]: False for lane in LANES}

    print("Skele King macro running.")
    print(f"Region: {CAPTURE_REGION}")
    print(f"Hit line: y={HIT_LINE_Y}")
    print(f"Detection mode: {DETECTION_MODE}")
    print(f"Disappear ratio threshold: {DISAPPEAR_RATIO}")
    print(f"Change ratio threshold: {CHANGE_RATIO}")
    print(f"Tap on detection start only: {TAP_ON_DETECTION_START_ONLY}")
    print(f"Use saved baseline: {USE_SAVED_BASELINE}")
    print(f"Press {TOGGLE_KEY.upper()} to start/pause.")
    print(f"Press {POSITION_KEY.upper()} to position Roblox.")
    print(f"Press {CAPTURE_CALIBRATION_KEY.upper()} to calibrate capture region and lane x values.")
    print(f"Press {KILL_KEY.upper()} to stop.")

    with mss.mss() as sct:
        baseline = {
            lane["name"]: float(SAVED_BASELINE.get(lane["name"], 0.0))
            for lane in LANES
        } if USE_SAVED_BASELINE else {}

        while running:
            try:
                tk_root.update()
            except tk.TclError:
                running = False
                break

            if pending_capture_calibration_hotkey:
                pending_capture_calibration_hotkey = False
                _handle_capture_calibration_hotkey()

            if pending_focus_roblox:
                pending_focus_roblox = False
                gh.focus_roblox()

            if seen_capture_config_version != capture_config_version:
                region = _capture_region_dict()
                seen_capture_config_version = capture_config_version
                last_fire_at = {lane["name"]: 0.0 for lane in LANES}
                lane_was_detected = {lane["name"]: False for lane in LANES}
                print(f"Capture region updated live: {CAPTURE_REGION}, hit line y={HIT_LINE_Y}")

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
                    lane_was_detected[lane["name"]] = False
                    continue

                ratio = level / base
                detected = False
                if DETECTION_MODE == "change":
                    delta_ratio = abs(level - base) / base
                    detected = delta_ratio >= CHANGE_RATIO
                else:
                    detected = ratio <= DISAPPEAR_RATIO

                if not detected:
                    lane_was_detected[lane["name"]] = False
                    continue

                if TAP_ON_DETECTION_START_ONLY and lane_was_detected[lane["name"]]:
                    continue

                if now - last_fire_at[lane["name"]] < LANE_COOLDOWN_SECONDS:
                    continue

                tap(lane["key"])
                last_fire_at[lane["name"]] = now
                lane_was_detected[lane["name"]] = True

            if SHOW_DEBUG_PREVIEW:
                preview = _draw_debug_overlay(frame, baseline, brightness_now)
                cv2.imshow(DEBUG_WINDOW_NAME, preview)
                if (cv2.waitKey(1) & 0xFF) == 27:
                    running = False
                    break

            elapsed = time.perf_counter() - started
            remaining = LOOP_SLEEP_SECONDS - elapsed
            if remaining > 0:
                time.sleep(remaining)

    if SHOW_DEBUG_PREVIEW:
        cv2.destroyAllWindows()

    if listener is not None:
        listener.stop()

    if tk_root is not None:
        try:
            tk_root.destroy()
        except tk.TclError:
            pass

    print("Skele King macro stopped.")

if __name__ == "__main__":
    run()