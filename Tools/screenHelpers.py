import time
import pyautogui
import numpy as np
from PIL import Image

try:
    import mss as _mss_lib
    _mss = _mss_lib.mss()
except Exception:
    _mss_lib = None
    _mss = None

_retina_scale: tuple[float, float] | None = None
_backing_scale: float | None = None


def _get_backing_scale() -> float:
    """Return the macOS Retina backing scale factor (e.g. 2.0 on Retina, 1.0 otherwise).
    cmd+shift+4 screenshots are at this scale; mss captures at logical (1×) resolution."""
    global _backing_scale
    if _backing_scale is not None:
        return _backing_scale
    try:
        from AppKit import NSScreen
        _backing_scale = float(NSScreen.mainScreen().backingScaleFactor())
    except Exception:
        _backing_scale = 1.0
    return _backing_scale


def _safe_screenshot(retries: int = 3, retry_delay: float = 0.12):
    """
    Best-effort full-screen capture. Uses mss when available (faster on macOS
    Retina); falls back to pyautogui. Returns a PIL RGB Image or None.
    """
    last_error = None
    for _ in range(max(1, retries)):
        try:
            if _mss is not None:
                monitor = _mss.monitors[0]
                shot = _mss.grab(monitor)
                return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            return pyautogui.screenshot()
        except Exception as e:
            last_error = e
            time.sleep(retry_delay)
    print(f"[screenshot] failed after retries: {last_error}")
    return None


def _seen_pixel_from_screenshot(img, x: int, y: int, sample_half: int = 1):
    """Map pyautogui coords -> screenshot pixel coords and return median RGB."""
    sw, sh = pyautogui.size()
    iw, ih = img.size
    sx = iw / sw
    sy = ih / sh

    xp = int(x * sx)
    yp = int(y * sy)

    w, h = img.size
    left = max(0, xp - sample_half)
    top = max(0, yp - sample_half)
    right = min(w - 1, xp + sample_half)
    bottom = min(h - 1, yp + sample_half)

    arr = np.array(img)
    patch = arr[top:bottom + 1, left:right + 1, :3]

    if patch.size == 0:
        return (0, 0, 0)

    med = np.median(patch, axis=(0, 1)).astype(int)
    return (int(med[0]), int(med[1]), int(med[2]))


def pixel_color_seen(x: int, y: int, sample_half: int = 1, screenshot=None):
    """
    Return the RGB color seen at a pyautogui point using coordinate-to-screenshot
    scaling and median sampling.
    """
    img = screenshot if screenshot is not None else _safe_screenshot()
    if img is None:
        return None
    return _seen_pixel_from_screenshot(img, x, y, sample_half=sample_half)


def pixel_matches_seen(
    x: int, y: int, rgb: tuple[int, int, int], tol: int = 20, sample_half: int = 1,
    screenshot=None,
) -> bool:
    seen = pixel_color_seen(x, y, sample_half=sample_half, screenshot=screenshot)
    if seen is None:
        return False
    r, g, b = seen
    return abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol


def pixel_color_at(x: int, y: int, sample_half: int = 1) -> tuple[int, int, int] | None:
    """
    Read pixel color using a tiny mss region grab — no full screenshot needed.
    Coordinates are screen-space points (same as pyautogui). Falls back to
    pixel_color_seen if mss is unavailable.
    """
    if _mss is None:
        return pixel_color_seen(x, y, sample_half=sample_half)
    size = max(1, sample_half * 2 + 1)
    monitor = {"left": x - sample_half, "top": y - sample_half, "width": size, "height": size}
    try:
        shot = _mss.grab(monitor)
        arr = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
        rgb = arr[:, :, [2, 1, 0]]  # BGRA → RGB
        med = np.median(rgb.reshape(-1, 3), axis=0).astype(int)
        return (int(med[0]), int(med[1]), int(med[2]))
    except Exception as e:
        print(f"[pixel_color_at] error: {e}")
        return None


def pixel_matches_at(
    x: int, y: int, rgb: tuple[int, int, int], tol: int = 20, sample_half: int = 1
) -> bool:
    """pixel_matches_seen but uses a tiny region grab instead of a full screenshot."""
    seen = pixel_color_at(x, y, sample_half=sample_half)
    if seen is None:
        return False
    r, g, b = seen
    return abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol


def _retina_to_screen_coords_from_image(x: int, y: int, img) -> tuple[int, int]:
    """Convert screenshot-space coords to screen-space coords using a captured image."""
    if img is None:
        return int(x), int(y)
    sw, sh = pyautogui.size()
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return int(x), int(y)
    scale_x = sw / iw
    scale_y = sh / ih
    return int(x * scale_x), int(y * scale_y)


def _get_retina_scale() -> tuple[float, float]:
    """Return (scale_x, scale_y), cached after the first call."""
    global _retina_scale
    if _retina_scale is not None:
        return _retina_scale
    img = _safe_screenshot()
    if img is None:
        return (1.0, 1.0)
    sw, sh = pyautogui.size()
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return (1.0, 1.0)
    _retina_scale = (sw / iw, sh / ih)
    return _retina_scale


def _retina_to_screen_coords(x: int, y: int) -> tuple[int, int]:
    sx, sy = _get_retina_scale()
    return int(x * sx), int(y * sy)


def _screen_region_to_screenshot_region(
    region, screenshot=None
) -> tuple[int, int, int, int] | None:
    """
    Convert a screen-space region (x, y, w, h) to screenshot-space region
    used by locateOnScreen on macOS Retina. Accepts an optional pre-taken
    screenshot to avoid an extra capture.
    """
    if region is None:
        return None

    x, y, w, h = region
    img = screenshot if screenshot is not None else _safe_screenshot()
    if img is None:
        return region

    sw, sh = pyautogui.size()
    iw, ih = img.size
    if sw <= 0 or sh <= 0:
        return region

    sx = iw / sw
    sy = ih / sh
    return (int(x * sx), int(y * sy), max(1, int(w * sx)), max(1, int(h * sy)))
