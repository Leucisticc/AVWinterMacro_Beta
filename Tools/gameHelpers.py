import os
import time
import subprocess
import pyautogui
from pathlib import Path
from pynput.keyboard import Controller

from Tools import botTools as bt
from Tools import winTools as wt
from Tools.imageHelpers import _resolve_image_path

keyboard_controller = Controller()


# -------------------------
# Process Control
# -------------------------

def kill():
    os._exit(0)


# -------------------------
# Mouse / Click
# -------------------------

def click(x, y=None, delay=None, right_click=False, dont_move=False):
    """
    macOS-safe click. Accepts click(x, y) or click((x, y)).
    """
    if y is None:
        x, y = x
    if delay is None:
        delay = 0.3
    if not dont_move:
        pyautogui.moveTo(x, y)
    time.sleep(delay)
    if right_click:
        pyautogui.rightClick()
    else:
        pyautogui.click()


def click_image_center(
    img_path: str,
    confidence: float = 0.8,
    grayscale: bool = False,
    offset=(0, 0),
    region=None,
    delay: float = 0.1,
    right_click: bool = False,
    retries: int = 2,
    retry_delay: float = 0.05,
):
    resolved = _resolve_image_path(img_path)

    for attempt in range(max(1, retries)):
        try:
            loc = bt._locate_image(resolved, confidence=confidence, grayscale=grayscale, region=region)
        except Exception:
            loc = None

        if loc is not None:
            if bt.appSettings.get_bool("USE_FAST_IMAGE_DETECTION", "USE_MSS", default=False):
                left, top, width, height = loc
                cx = int(left + width // 2)
                cy = int(top + height // 2)
            else:
                cx, cy = pyautogui.center(loc)
                cx, cy = bt._retina_to_screen(cx, cy)

            ox, oy = offset if offset is not None else (0, 0)
            click(cx + int(ox), cy + int(oy), delay=delay, right_click=right_click)
            return True

        if attempt < retries - 1:
            time.sleep(retry_delay)

    return False


# -------------------------
# Keyboard
# -------------------------

def tap(key, hold=0.04, post_delay=0.03):
    """pynput primary; pyautogui fallback for games that ignore injected keys."""
    try:
        keyboard_controller.press(key)
        time.sleep(hold)
        keyboard_controller.release(key)
    except Exception:
        pyautogui.press(str(key))
    time.sleep(post_delay)


def chord(keys=("a", "s", "d", "f", "g"), hold=0.03):
    for k in keys:
        keyboard_controller.press(k)
    time.sleep(hold)
    for k in reversed(keys):
        keyboard_controller.release(k)


def spam_chord_for_duration(
    keys=("[", "]", ";", "'", ","), duration=6.0, hold=0.02, gap=0.005
):
    end_time = time.perf_counter() + duration
    while time.perf_counter() < end_time:
        chord(keys, hold=hold)
        if gap > 0:
            time.sleep(gap)


# -------------------------
# Game Helpers
# -------------------------

def wait_start(region=(767, 189, 127, 83), delay: int = 1):
    """Poll for the VoteStart button. Returns True when found, None on timeout."""
    for _ in range(90):
        try:
            print("Looking for start screen.")
            if bt.does_exist("VoteStart.png", confidence=0.7, grayscale=False, region=region):
                print("✅ Start screen detected")
                return True
        except Exception as e:
            print(f"e {e}")
        time.sleep(delay)


def quick_rts():
    """Return to spawn (fast)."""
    for loc in [(232, 873), (1153, 503), (1217, 267)]:
        click(loc[0], loc[1], delay=0.1)
        time.sleep(0.2)


def slow_rts():
    """Return to spawn (slow)."""
    for loc in [(232, 873), (1153, 503), (1217, 267)]:
        click(loc[0], loc[1], delay=1)
        time.sleep(0.2)


# -------------------------
# Window Management
# -------------------------

def _osascript(script: str) -> bool:
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def focus_roblox():
    _osascript('tell application "Roblox" to activate')
    time.sleep(0.2)


def ensure_roblox_window_positioned():
    target_left, target_top = 200, 100
    target_width, target_height = 1100, 800

    try:
        window = wt.get_window("Roblox")
        if window is None:
            print("[Window] Roblox window not found; could not verify/position window.")
            return False

        left = int(getattr(window, "left", -1))
        top = int(getattr(window, "top", -1))
        width = int(getattr(window, "width", -1))
        height = int(getattr(window, "height", -1))

        if left == target_left and top == target_top and width == target_width and height == target_height:
            return True

        wt.move_window(window, target_left, target_top)
        wt.resize_window(window, target_width, target_height)
        time.sleep(0.2)

        check_window = wt.get_window("Roblox") or window
        new_left = int(getattr(check_window, "left", -1))
        new_top = int(getattr(check_window, "top", -1))
        new_width = int(getattr(check_window, "width", -1))
        new_height = int(getattr(check_window, "height", -1))

        if new_left == target_left and new_top == target_top and new_width == target_width and new_height == target_height:
            print("[Window] Roblox window was not positioned correctly; corrected window position.")
            return True

        print(
            f"[Window] Roblox window was not positioned correctly; correction failed "
            f"(x={new_left}, y={new_top}, w={new_width}, h={new_height})."
        )
        return False
    except Exception as e:
        print(f"[Window] Roblox window was not positioned correctly; correction failed: {e}")
        return False


# -------------------------
# Webhook Helpers
# -------------------------

def _roblox_window_screenshot_for_webhook():
    try:
        roblox_window = wt.get_window("Roblox")
        if roblox_window is None:
            return None
        return wt.screen_shot_memory(roblox_window)
    except Exception as e:
        print(f"[Webhook] Roblox window screenshot failed: {e}")
        return None
