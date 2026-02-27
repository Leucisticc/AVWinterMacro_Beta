import os
import time
import pyautogui

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

def does_exist(imageDirectory: str, confidence: float, grayscale: bool, region: tuple | None = None) -> bool:
    try:
        img_path = _resource_path(imageDirectory)
        search_region = _screen_region_to_screenshot_region(region)

        if search_region is None:
            check = pyautogui.locateOnScreen(img_path, grayscale=grayscale, confidence=confidence)
        else:
            check = pyautogui.locateOnScreen(
                img_path,
                grayscale=grayscale,
                confidence=confidence,
                region=search_region,
            )

        return check is not None

    except Exception:
        return False

def click_image(imageDirectory, confidence, grayscale, offset=(0, 0), region=None):
    try:
        img_path = _resource_path(imageDirectory)
        search_region = _screen_region_to_screenshot_region(region)

        loc = pyautogui.locateOnScreen(
            img_path,
            grayscale=grayscale,
            confidence=confidence,
            region=search_region
        )

        if loc is None:
            return False

        cx, cy = pyautogui.center(loc)

        # ⭐ Retina fix here
        cx, cy = _retina_to_screen(cx, cy)

        ox, oy = offset

        # ⭐ use YOUR stable click
        click(cx + ox, cy + oy)

        return True

    except Exception as e:
        print("click_image error:", e)
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
