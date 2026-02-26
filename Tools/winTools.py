# Tools/winTools.py (macOS-friendly version)
# NOTE: This keeps the same function names your project expects.

import os
import io
import subprocess
from datetime import datetime
from types import SimpleNamespace

import pyautogui
import numpy as np
import cv2

# Optional window listing (flaky on macOS, so keep graceful fallbacks)
try:
    import pygetwindow as gw
except Exception:
    gw = None


# =========================
# Window helpers (best-effort on macOS)
# =========================

def get_window(title: str):
    """
    Finds the first window whose title contains `title`.
    Returns a pygetwindow Window or None.
    """
    try:
        if gw is None:
            return _get_window_macos_fallback(title)

        titles = gw.getAllTitles() or []
        hit = next((t for t in titles if title in t), None)
        if hit and hasattr(gw, "getWindowsWithTitle"):
            wins = gw.getWindowsWithTitle(hit)
            return wins[0] if wins else None

        # Some macOS pygetwindow builds do not expose getWindowsWithTitle.
        # Fall back to active window if it looks like the target.
        if hasattr(gw, "getActiveWindow"):
            active = gw.getActiveWindow()
            if active is not None:
                active_title = str(getattr(active, "title", "") or "")
                if title.lower() in active_title.lower():
                    return active

        return _get_window_macos_fallback(title)

    except Exception as e:
        print(f"Window not found: {e}")
        return _get_window_macos_fallback(title)


def _get_window_macos_fallback(title: str):
    """
    macOS fallback using System Events. Returns an object with title/left/top/width/height.
    Matches the minimum shape expected by screenshot helpers.
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
            return None

        raw = (result.stdout or "").strip()
        if not raw or raw.endswith("|NO_WINDOW"):
            return None

        parts = raw.split("|")
        if len(parts) != 5:
            return None

        app_name, left, top, width, height = parts
        if title.lower() not in app_name.lower():
            return None

        return SimpleNamespace(
            title=app_name,
            left=int(left),
            top=int(top),
            width=int(width),
            height=int(height),
            box=(int(left), int(top), int(width), int(height)),
        )
    except Exception:
        return None


def activate_window(window) -> bool:
    """Attempts to focus a window (best-effort)."""
    try:
        if window is None:
            return False
        window.activate()
        return True
    except Exception as e:
        print(f"Could not activate window: {e}")
        return False


def kill_window(window) -> bool:
    """
    Attempts to kill a window's process if PID is available.
    On macOS, processId may not exist depending on backend.
    """
    try:
        if window is None:
            return False

        pid = getattr(window, "processId", None) or getattr(window, "process_id", None)
        if not pid:
            print("kill_window: window has no processId on this platform.")
            return False

        subprocess.run(["kill", "-9", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    except Exception as e:
        print(f"kill_window failed: {e}")
        return False


def move_window(window, x: int, y: int) -> None:
    """Best-effort window move (often blocked by macOS permissions)."""
    try:
        if window is None:
            return
        window.moveTo(x, y)
    except Exception as e:
        print(f"move_window error: {e}")


def resize_window(window, x: int, y: int) -> None:
    """Best-effort window resize (often blocked by macOS permissions)."""
    try:
        if window is None:
            return
        window.resizeTo(x, y)
    except Exception as e:
        print(f"resize_window error: {e}")


def get_winSize(window):
    """Returns (width, height) or None."""
    try:
        if window is None:
            return None
        return window.size
    except Exception as e:
        print(f"get_winSize error: {e}")
        return None


# =========================
# Screenshots (macOS)
# =========================

def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _screenshots_dir() -> str:
    d = os.path.join(_project_root(), "Screenshots")
    os.makedirs(d, exist_ok=True)
    return d


def screenshot_window(window=None, name: str | None = None, retImg: bool = False):
    """
    Screenshots a window region if we can read window bounds,
    otherwise screenshots full screen.

    Saves into <project_root>/Screenshots/<name>.
    Returns PIL Image if retImg=True else None.
    """
    try:
        if name is None:
            time_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            title = getattr(window, "title", "window") if window else "screen"
            name = f"{title}-{time_stamp}.png"

        fullPath = os.path.join(_screenshots_dir(), name)

        # If we have a window with bounds, try to region-capture.
        if window:
            left = getattr(window, "left", None)
            top = getattr(window, "top", None)
            width = getattr(window, "width", None)
            height = getattr(window, "height", None)

            if None not in (left, top, width, height):
                img = pyautogui.screenshot(region=(left, top, width, height))
            else:
                img = pyautogui.screenshot()
        else:
            img = pyautogui.screenshot()

        img.save(fullPath)

        if retImg:
            return img
        return None

    except Exception as e:
        print(f"screenshot_window error: {e}")
        return None


def screen_shot_memory(window=None):
    """
    Returns PNG bytes (BytesIO) of a window region (if bounds available),
    else full screen. Uses pyautogui.screenshot() for mac consistency.
    """
    try:
        if window:
            left = getattr(window, "left", None)
            top = getattr(window, "top", None)
            width = getattr(window, "width", None)
            height = getattr(window, "height", None)

            if None not in (left, top, width, height):
                img = pyautogui.screenshot(region=(left, top, width, height))
            else:
                img = pyautogui.screenshot()
        else:
            img = pyautogui.screenshot()

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"screen_shot_memory error: {e}")
        return None


def screenshot_region(region: tuple[int, int, int, int]):
    """
    region = (x, y, width, height)  ✅ pyautogui-style
    Returns: NumPy array in BGR (OpenCV-friendly)
    """
    try:
        x, y, w, h = region
        pil_img = pyautogui.screenshot(region=(x, y, w, h))  # PIL RGB
        img_np = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return img_np
    except Exception as e:
        print(f"Region {region} screenshot error: {e}")
        return None


def clear_screenshot_cache():
    """Deletes everything in <project_root>/Screenshots."""
    try:
        screen_path = _screenshots_dir()
        for fname in os.listdir(screen_path):
            fp = os.path.join(screen_path, fname)
            if os.path.isfile(fp):
                os.remove(fp)
    except Exception as e:
        print(f"clear_screenshot_cache error: {e}")
