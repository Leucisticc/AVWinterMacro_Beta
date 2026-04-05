import os
import sys
import time

import cv2
import numpy as np

try:
    from Tools import botTools as bt
    from Tools import winTools as wt
except ModuleNotFoundError:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from Tools import botTools as bt
    from Tools import winTools as wt


WAVE_MIN = 0
WAVE_MAX = 170

# Roblox-window-relative bbox: (left, top, right, bottom)
# Extended 15px to the right so 3-digit waves are not clipped.
WAVE_REGION_REL_BBOX = (326, 48, 388, 79)
WAVE_TEMPLATE_SCALES = (1.0, 0.5, 2.0, 0.75, 1.25, 1.5)
WAVE_MATCH_THRESHOLD = 0.72


def _resource_path(relative_path: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Resources",
        relative_path,
    )

def _wave_region_from_offset(offset: tuple[int, int]) -> tuple[int, int, int, int]:
    """
    Build screenshot_region() coords from a Roblox-window offset.
    Returns (x, y, width, height).
    """
    ox, oy = int(offset[0]), int(offset[1])
    l, t, r, b = WAVE_REGION_REL_BBOX
    left = l + ox
    top = t + oy
    right = r + ox
    bottom = b + oy
    return (left, top, max(1, right - left), max(1, bottom - top))


def _roblox_window_offset() -> tuple[int, int] | None:
    try:
        w = wt.get_window("Roblox")
        if w is None:
            return None
        return (int(w.left), int(w.top))
    except Exception:
        return None


def get_wave(offset: tuple[int, int] | None = None) -> int:
    """Wave recognition using template matching only."""
    try:
        if offset is None:
            offset = _roblox_window_offset() or (0, 0)

        region = _wave_region_from_offset(offset)
        img = wt.screenshot_region(region)
        if img is None:
            return -1

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, gray = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)

        wave_hits: list[list[int | float]] = []

        for digit in range(10):
            tpath = _resource_path(f"WaveRecon/{digit}.png")
            template = cv2.imread(str(tpath), cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue

            _, template = cv2.threshold(template, 250, 255, cv2.THRESH_BINARY_INV)

            for scale in WAVE_TEMPLATE_SCALES:
                t = template
                if scale != 1.0:
                    th0, tw0 = template.shape[:2]
                    nw = max(1, int(round(tw0 * scale)))
                    nh = max(1, int(round(th0 * scale)))
                    t = cv2.resize(
                        template,
                        (nw, nh),
                        interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC,
                    )

                th, tw = t.shape[:2]
                gh, gw = gray.shape[:2]
                if th > gh or tw > gw:
                    continue

                res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
                loc = np.where(res >= WAVE_MATCH_THRESHOLD)
                for pt in zip(*loc[::-1]):
                    wave_hits.append([int(pt[0]), digit, float(res[pt[1], pt[0]])])

        if not wave_hits:
            return -1

        # Dedupe overlapping matches from different scales / nearby peaks.
        wave_hits.sort(key=lambda h: float(h[2]), reverse=True)
        chosen: list[list[int | float]] = []
        for hit in wave_hits:
            x = int(hit[0])
            if any(abs(x - int(c[0])) <= 3 for c in chosen):
                continue
            chosen.append(hit)

        chosen.sort(key=lambda h: int(h[0]))
        wave_number = "".join(str(int(h[1])) for h in chosen)
        if not wave_number or len(wave_number) > 3:
            return -1

        value = int(wave_number)
        if not (WAVE_MIN <= value <= WAVE_MAX):
            return -1
        return value

    except Exception:
        return -1


def restart_match():
    """Clicks through the UI to restart a match."""
    bt.click(227, 868)
    time.sleep(0.8)
    bt.click(1150, 454)
    time.sleep(0.8)
    bt.click(681, 565)
    time.sleep(1.5)
    bt.click(726, 560)
    time.sleep(0.7)
    bt.click(1212, 254)
    time.sleep(0.7)


if __name__ == "__main__":
    print("Wave read:", get_wave())
