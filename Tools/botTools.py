import os
import time
import pyautogui
import cv2
import numpy as np

from Tools.screenHelpers import _get_backing_scale

try:
    import mss as _mss_lib
    _mss = _mss_lib.mss()
except Exception:
    _mss = None


def _resource_path(relative_path: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Resources",
        relative_path
    )


def _grab_region(region: tuple) -> np.ndarray | None:
    """Grab a screen region using mss logical coords. Returns BGR numpy array."""
    x, y, w, h = region
    monitor = {"left": int(x), "top": int(y), "width": max(1, int(w)), "height": max(1, int(h))}
    if _mss is not None:
        try:
            shot = _mss.grab(monitor)
            arr = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
            return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
        except Exception:
            pass
    # fallback
    from PIL import Image
    img = pyautogui.screenshot(region=(x, y, w, h))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _locate_image(img_path: str, confidence: float, grayscale: bool, region: tuple | None = None):
    template_flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    template = cv2.imread(img_path, template_flag)
    if template is None:
        return None

    # Templates captured with cmd+shift+4 are at Retina (2×) resolution.
    # mss region capture uses logical coords and returns 1× pixels, so scale the template down.
    scale = _get_backing_scale()
    if scale != 1.0:
        th, tw = template.shape[:2]
        template = cv2.resize(template, (max(1, int(tw / scale)), max(1, int(th / scale))), interpolation=cv2.INTER_AREA)

    if region is None:
        sw, sh = pyautogui.size()
        region = (0, 0, sw, sh)

    haystack_bgr = _grab_region(region)
    if haystack_bgr is None or haystack_bgr.size == 0:
        return None

    haystack = cv2.cvtColor(haystack_bgr, cv2.COLOR_BGR2GRAY) if grayscale else haystack_bgr

    th, tw = template.shape[:2]
    if haystack.shape[0] < th or haystack.shape[1] < tw:
        return None

    result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < confidence:
        return None

    # Coordinates are already in logical screen space (mss uses logical coords)
    rx, ry, _, _ = region
    return (int(rx + max_loc[0]), int(ry + max_loc[1]), int(tw), int(th))


def does_exist(imageDirectory: str, confidence: float, grayscale: bool, region: tuple | None = None) -> bool:
    try:
        return _locate_image(_resource_path(imageDirectory), confidence=confidence, grayscale=grayscale, region=region) is not None
    except Exception:
        return False


def click_image(imageDirectory, confidence, grayscale, offset=(0, 0), region=None):
    try:
        loc = _locate_image(_resource_path(imageDirectory), confidence=confidence, grayscale=grayscale, region=region)
        if loc is None:
            return False

        left, top, width, height = loc
        cx = int(left + width // 2)
        cy = int(top + height // 2)
        ox, oy = offset
        click(cx + ox, cy + oy)
        return True

    except Exception as e:
        print(f"click_image error: {type(e).__name__}: {e!r}")
        return False


def click(x: int, y: int, delay: float | None = None, nudge: bool = True) -> None:
    if delay is None:
        delay = 0.1

    pyautogui.moveTo(x, y)
    if nudge:
        pyautogui.moveRel(0, 1)
        pyautogui.moveRel(0, -1)
    time.sleep(delay)
    pyautogui.click()
