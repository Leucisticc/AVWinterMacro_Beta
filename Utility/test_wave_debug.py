import os
import subprocess
import time
from types import SimpleNamespace
import cv2

from Tools import avMethods as avM
from Tools import winTools as wt

DEBUG_DIR = os.path.join("Resources", "debug_shots")


def _bbox_to_pyautogui_region(bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """
    Convert (left, top, right, bottom) -> (x, y, width, height)
    for wt.screenshot_region().
    """
    left, top, right, bottom = bbox
    return (int(left), int(top), max(1, int(right - left)), max(1, int(bottom - top)))


def _get_frontmost_window_macos():
    """
    Fallback for macOS when pygetwindow is unreliable.
    Returns a simple object with title/left/top/width/height or None.
    """
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
            print("[wave test] osascript error:", (result.stderr or "").strip())
            return None

        raw = (result.stdout or "").strip()
        if not raw or raw.endswith("|NO_WINDOW"):
            return None

        parts = raw.split("|")
        if len(parts) != 5:
            print("[wave test] unexpected osascript output:", raw)
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
        print("[wave test] frontmost window fallback failed:", e)
        return None


def _get_roblox_window_or_fallback():
    w = wt.get_window("Roblox")
    if w is not None:
        return w

    print("[wave test] wt.get_window('Roblox') failed, trying frontmost-window fallback...")
    w = _get_frontmost_window_macos()
    if w is None:
        return None

    title = str(getattr(w, "title", "") or "")
    if "roblox" not in title.lower():
        print(f"[wave test] frontmost window is not Roblox: {title!r}")
        print("[wave test] Focus the Roblox window and run again.")
        return None
    return w


def test():
    time.sleep(2)
    w = _get_roblox_window_or_fallback()
    if w is None:
        raise RuntimeError(
            "Roblox window not found. Focus Roblox and ensure Accessibility permissions are enabled for Terminal/Python."
        )

    off = (int(w.left), int(w.top))
    print("window:", w)
    print("offset:", off)

    # Matches the region used by Tools/avMethods.py (bbox style)
    region_bbox = (326 + off[0], 48 + off[1], 373 + off[0], 79 + off[1])
    img = wt.screenshot_region(_bbox_to_pyautogui_region(region_bbox))
    if img is None:
        raise RuntimeError("Failed to capture wave region screenshot.")

    os.makedirs(DEBUG_DIR, exist_ok=True)
    out_path = os.path.join(DEBUG_DIR, "wave_region_test.png")
    cv2.imwrite(out_path, img)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    thresh_path = os.path.join(DEBUG_DIR, "wave_region_threshold.png")
    cv2.imwrite(thresh_path, thresh)

    # Save full-window screenshot with region outline for visual verification.
    full_region_bbox = (int(w.left), int(w.top), int(w.left + w.width), int(w.top + w.height))
    full_img = wt.screenshot_region(_bbox_to_pyautogui_region(full_region_bbox))
    if full_img is not None:
        rx1, ry1 = region_bbox[0] - int(w.left), region_bbox[1] - int(w.top)
        rx2, ry2 = region_bbox[2] - int(w.left), region_bbox[3] - int(w.top)
        cv2.rectangle(full_img, (rx1, ry1), (rx2, ry2), (0, 0, 255), 2)
        cv2.putText(
            full_img,
            "Wave Region",
            (max(0, rx1), max(15, ry1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )
        full_out_path = os.path.join(DEBUG_DIR, "wave_region_context.png")
        cv2.imwrite(full_out_path, full_img)
    else:
        full_out_path = None

    wave = avM.get_wave(off)
    print("wave:", wave)
    print("region(abs):", region_bbox)
    print("saved:", out_path)
    print("saved:", thresh_path)
    if full_out_path:
        print("saved:", full_out_path)

test()
