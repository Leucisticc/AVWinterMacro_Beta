import pyautogui
import cv2
import numpy as np
from pathlib import Path

from Tools.screenHelpers import (
    _safe_screenshot,
    _screen_region_to_screenshot_region,
)

# Set to False to fall back to pyautogui.locateOnScreen (slower but available).
USE_FAST_IMAGE_DETECTION = True

_template_cache: dict[tuple[str, bool], np.ndarray | None] = {}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_image_path(img_path: str) -> str:
    """
    Resolve an image filename to an absolute path. Checks, in order:
      1. The path as-is (absolute or relative to cwd)
      2. <project_root>/<img_path>
      3. <project_root>/Resources/<img_path>
    """
    candidates = [
        Path(img_path),
        _PROJECT_ROOT / img_path,
        _PROJECT_ROOT / "Resources" / img_path,
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except Exception:
            continue
    return img_path


def _load_template_image(img_path: str, grayscale: bool = False):
    cache_key = (img_path, grayscale)
    if cache_key in _template_cache:
        return _template_cache[cache_key]

    template_path = _resolve_image_path(img_path)
    read_mode = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    template = cv2.imread(template_path, read_mode)
    _template_cache[cache_key] = template
    return template


def _capture_screen_for_match(grayscale: bool = False, screenshot=None):
    if screenshot is None:
        screenshot = _safe_screenshot()
    if screenshot is None:
        return None

    screen_img = np.array(screenshot)
    if grayscale:
        return cv2.cvtColor(screen_img, cv2.COLOR_RGB2GRAY)
    return cv2.cvtColor(screen_img, cv2.COLOR_RGB2BGR)


def _find_image_center_fast(
    img_path: str,
    confidence: float = 0.8,
    grayscale: bool = False,
    region=None,
    screenshot=None,
):
    template = _load_template_image(img_path, grayscale=grayscale)
    if template is None:
        return None, None, None

    screen_img = _capture_screen_for_match(grayscale=grayscale, screenshot=screenshot)
    if screen_img is None:
        return None, None, None

    search_region = _screen_region_to_screenshot_region(region, screenshot=screenshot)
    if search_region is None:
        rx = ry = 0
        crop = screen_img
    else:
        rx, ry, rw, rh = search_region
        crop = screen_img[ry:ry + rh, rx:rx + rw]
        if crop.size == 0:
            return None, None, None

    th, tw = template.shape[:2]
    if crop.shape[0] < th or crop.shape[1] < tw:
        return None, None, None

    result = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < confidence:
        return None, None, None

    center_x = rx + max_loc[0] + (tw // 2)
    center_y = ry + max_loc[1] + (th // 2)
    box = (rx + max_loc[0], ry + max_loc[1], tw, th)
    return int(center_x), int(center_y), box


def find_image_center(
    img_path: str,
    confidence: float = 0.8,
    grayscale: bool = False,
    region=None,
    screenshot=None,
):
    if USE_FAST_IMAGE_DETECTION:
        return _find_image_center_fast(
            img_path,
            confidence=confidence,
            grayscale=grayscale,
            region=region,
            screenshot=screenshot,
        )

    resolved_img_path = _resolve_image_path(img_path)
    search_region = _screen_region_to_screenshot_region(region)
    try:
        box = pyautogui.locateOnScreen(
            resolved_img_path,
            confidence=confidence,
            grayscale=grayscale,
            region=search_region,
        )
    except Exception as e:
        if e.__class__.__name__ == "ImageNotFoundException":
            return None, None, None
        raise

    if not box:
        return None, None, None

    cx, cy = pyautogui.center(box)
    return int(cx), int(cy), box
