import os
import subprocess
import sys
import time
from datetime import datetime
from types import SimpleNamespace

import cv2
import mss
import numpy as np

try:
    from Tools import winTools as wt
except ModuleNotFoundError:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from Tools import winTools as wt

DEBUG_DIR = os.path.join("Resources", "debug_shots")
REGION_MODE = "screen"  # "screen" or "roblox"
INPUT_REGION = (368,257,120,49) #(470, 771, 570, 118)  # (left, top, width, height)


def _xywh_to_bbox(region: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, w, h = region
    return (int(x), int(y), int(x + w), int(y + h))


def _bbox_to_xywh(bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    return (int(left), int(top), max(1, int(right - left)), max(1, int(bottom - top)))


def _get_frontmost_window_macos():
    script = r'''
tell application "System Events"
    set frontProc to first application process whose frontmost is true
    set appName to name of frontProc
    tell frontProc
        if (count of windows) is 0 then
            return appName & "|NO_WINDOW"
        end if
        set {xPos, yPos} to position of front window
        set {winW, winH} to size of front window
        return appName & "|" & xPos & "|" & yPos & "|" & winW & "|" & winH
    end tell
end tell
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            print("[region test] osascript error:", (result.stderr or "").strip())
            return None

        raw = (result.stdout or "").strip()
        if not raw or raw.endswith("|NO_WINDOW"):
            return None

        parts = raw.split("|")
        if len(parts) != 5:
            print("[region test] unexpected osascript output:", raw)
            return None

        title, left, top, width, height = parts
        return SimpleNamespace(
            title=title,
            left=int(left),
            top=int(top),
            width=int(width),
            height=int(height),
        )
    except Exception as e:
        print("[region test] frontmost window fallback failed:", e)
        return None


def _get_roblox_window_or_fallback():
    w = wt.get_window("Roblox")
    if w is not None:
        return w

    print("[region test] wt.get_window('Roblox') failed, trying frontmost-window fallback...")
    w = _get_frontmost_window_macos()
    if w is None:
        return None

    title = str(getattr(w, "title", "") or "")
    if "roblox" not in title.lower():
        print(f"[region test] frontmost window is not Roblox: {title!r}")
        print("[region test] Focus the Roblox window and run again.")
        return None
    return w


def _validate_config() -> tuple[str, tuple[int, int, int, int]]:
    mode = str(REGION_MODE).strip().lower()
    if mode not in {"screen", "roblox"}:
        raise ValueError("REGION_MODE must be 'screen' or 'roblox'.")

    if len(INPUT_REGION) != 4:
        raise ValueError("INPUT_REGION must be a 4-item tuple: (left, top, width, height).")

    left, top, width, height = (int(v) for v in INPUT_REGION)
    if width <= 0 or height <= 0:
        raise ValueError("INPUT_REGION width and height must be positive.")
    return mode, (left, top, width, height)


def test_capture_region(region: tuple[int, int, int, int]):
    captures = {
        "wt": wt.screenshot_region(region),
        "mss": None,
    }

    try:
        x, y, w, h = region
        monitor = {
            "left": int(x),
            "top": int(y),
            "width": max(1, int(w)),
            "height": max(1, int(h)),
        }
        with mss.mss() as sct:
            shot = sct.grab(monitor)
        captures["mss"] = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
    except Exception as e:
        print(f"[region test] mss capture error for {region}: {e}")

    return captures


def test():
    time.sleep(1)
    mode, input_region = _validate_config()

    offset = (0, 0)
    window = None
    if mode == "roblox":
        window = _get_roblox_window_or_fallback()
        if window is None:
            raise RuntimeError(
                "Roblox window not found. Focus Roblox and ensure Accessibility permissions are enabled for Terminal/Python."
            )
        offset = (int(window.left), int(window.top))

    abs_region = (
        int(input_region[0] + offset[0]),
        int(input_region[1] + offset[1]),
        int(input_region[2]),
        int(input_region[3]),
    )
    abs_bbox = _xywh_to_bbox(abs_region)
    captures = test_capture_region(abs_region)
    img = captures["wt"]
    mss_img = captures["mss"]
    if img is None and mss_img is None:
        raise RuntimeError("Failed to capture region screenshot.")

    os.makedirs(DEBUG_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    crop_path = None
    mss_crop_path = None
    if img is not None:
        crop_path = os.path.join(DEBUG_DIR, f"region_capture_{stamp}.png")
        cv2.imwrite(crop_path, img)
    if mss_img is not None:
        mss_crop_path = os.path.join(DEBUG_DIR, f"region_capture_mss_{stamp}.png")
        cv2.imwrite(mss_crop_path, mss_img)

    context_path = None
    mss_context_path = None
    if window is not None:
        window_bbox = (
            int(window.left),
            int(window.top),
            int(window.left + window.width),
            int(window.top + window.height),
        )
        context_captures = test_capture_region(_bbox_to_xywh(window_bbox))
        context_img = context_captures["wt"]
        mss_context_img = context_captures["mss"]
        if context_img is not None:
            rx1 = abs_bbox[0] - int(window.left)
            ry1 = abs_bbox[1] - int(window.top)
            rx2 = abs_bbox[2] - int(window.left)
            ry2 = abs_bbox[3] - int(window.top)
            cv2.rectangle(context_img, (rx1, ry1), (rx2, ry2), (0, 0, 255), 2)
            cv2.putText(
                context_img,
                "Captured Region",
                (max(0, rx1), max(15, ry1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1,
                cv2.LINE_AA,
            )
            context_path = os.path.join(DEBUG_DIR, f"region_capture_context_{stamp}.png")
            cv2.imwrite(context_path, context_img)
        if mss_context_img is not None:
            rx1 = abs_bbox[0] - int(window.left)
            ry1 = abs_bbox[1] - int(window.top)
            rx2 = abs_bbox[2] - int(window.left)
            ry2 = abs_bbox[3] - int(window.top)
            cv2.rectangle(mss_context_img, (rx1, ry1), (rx2, ry2), (255, 128, 0), 2)
            cv2.putText(
                mss_context_img,
                "Captured Region (mss)",
                (max(0, rx1), max(15, ry1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 128, 0),
                1,
                cv2.LINE_AA,
            )
            mss_context_path = os.path.join(DEBUG_DIR, f"region_capture_context_mss_{stamp}.png")
            cv2.imwrite(mss_context_path, mss_context_img)

    print("mode:", mode)
    print("input region:", input_region)
    print("offset:", offset)
    print("region(abs xywh):", abs_region)
    print("region(abs bbox):", abs_bbox)
    if crop_path:
        print("saved:", crop_path)
    if mss_crop_path:
        print("saved:", mss_crop_path)
    if context_path:
        print("saved:", context_path)
    if mss_context_path:
        print("saved:", mss_context_path)


test()
