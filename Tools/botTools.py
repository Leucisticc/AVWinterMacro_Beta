import os
import time
import pyautogui
import cv2
import numpy as np

from Tools import appSettings
from Tools import winTools as wt

def _resource_path(relative_path: str) -> str:
    """
    Builds an absolute path to: <project_root>/Resources/<relative_path>
    Where this file is expected to live in something like: <project_root>/Tools/...
    """
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Resources",
        relative_path
    )

def _retina_to_screen(x, y):
    sw, sh = pyautogui.size()
    img = pyautogui.screenshot()
    iw, ih = img.size

    scale_x = sw / iw
    scale_y = sh / ih

    return int(x * scale_x), int(y * scale_y)

def _screen_region_to_screenshot_region(region):
    """
    Convert a screen-space region (x, y, w, h) to screenshot-space region
    used by locateOnScreen on macOS Retina.
    """
    if region is None:
        return None

    x, y, w, h = region
    sw, sh = pyautogui.size()
    img = pyautogui.screenshot()
    iw, ih = img.size

    # screen (points) -> screenshot pixels
    scale_x = iw / sw
    scale_y = ih / sh

    sx = int(x * scale_x)
    sy = int(y * scale_y)
    swidth = max(1, int(w * scale_x))
    sheight = max(1, int(h * scale_y))
    return (sx, sy, swidth, sheight)


def _locate_on_screen_fast(img_path: str, confidence: float, grayscale: bool, region: tuple | None = None):
    template_flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    template = cv2.imread(img_path, template_flag)
    if template is None:
        return None

    if region is None:
        sw, sh = pyautogui.size()
        region = (0, 0, int(sw), int(sh))

    screen_img = wt.screenshot_region(region)
    if screen_img is None or screen_img.size == 0:
        return None

    if grayscale:
        haystack = cv2.cvtColor(screen_img, cv2.COLOR_BGR2GRAY)
    else:
        haystack = screen_img

    th, tw = template.shape[:2]
    hh, hw = haystack.shape[:2]
    if th > hh or tw > hw:
        return None

    result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < confidence:
        return None

    rx, ry, _, _ = region
    return (int(rx + max_loc[0]), int(ry + max_loc[1]), int(tw), int(th))


def _locate_image(img_path: str, confidence: float, grayscale: bool, region: tuple | None = None):
    if appSettings.get_bool("USE_FAST_IMAGE_DETECTION", "USE_MSS", default=False):
        return _locate_on_screen_fast(
            img_path,
            confidence=confidence,
            grayscale=grayscale,
            region=region,
        )

    search_region = _screen_region_to_screenshot_region(region)
    if search_region is None:
        return pyautogui.locateOnScreen(
            img_path,
            grayscale=grayscale,
            confidence=confidence,
        )

    return pyautogui.locateOnScreen(
        img_path,
        grayscale=grayscale,
        confidence=confidence,
        region=search_region,
    )

def does_exist(imageDirectory: str, confidence: float, grayscale: bool, region: tuple | None = None) -> bool:
    try:
        img_path = _resource_path(imageDirectory)
        check = _locate_image(img_path, confidence=confidence, grayscale=grayscale, region=region)
        return check is not None

    except Exception:
        return False

def click_image(imageDirectory, confidence, grayscale, offset=(0, 0), region=None):
    try:
        img_path = _resource_path(imageDirectory)
        loc = _locate_image(img_path, confidence=confidence, grayscale=grayscale, region=region)

        if loc is None:
            return False

        if appSettings.get_bool("USE_FAST_IMAGE_DETECTION", "USE_MSS", default=False):
            left, top, width, height = loc
            cx = int(left + (width // 2))
            cy = int(top + (height // 2))
        else:
            cx, cy = pyautogui.center(loc)

            # Retina fix is only needed for pyautogui locateOnScreen.
            cx, cy = _retina_to_screen(cx, cy)

        ox, oy = offset

        click(cx + ox, cy + oy)

        return True

    except Exception as e:
        if type(e).__name__ == "ImageNotFoundException":
            return False
        print(f"click_image error: {type(e).__name__}: {e!r}")
        return False

def click(x: int, y: int, delay: float | None = None, nudge: bool = True) -> None:
    """
    macOS-safe click at coordinate (x, y)
    """
    if delay is None:
        delay = 0.1

    pyautogui.moveTo(x, y)
    if nudge:
        # tiny move can help some apps register hover (Roblox included)
        pyautogui.moveRel(0, 1)
        pyautogui.moveRel(0, -1)
    time.sleep(delay)
    pyautogui.click()
