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
WAVE_TEMPLATE_SCALES = (1.0, 0.5, 2.0, 0.75, 1.25, 1.5, 0.45, 0.55, 0.6, 0.65, 0.7)
WAVE_MATCH_THRESHOLD = 0.72
WAVE_HIT_DEDUPE_DISTANCE = 8


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


def _wave_candidate_scales(template_shape: tuple[int, int], image_shape: tuple[int, int]) -> tuple[float, ...]:
    """
    Return fixed scales plus scales inferred from the current crop size.
    Tight custom regions often need a scale between the hand-picked presets.
    """
    template_h, _ = template_shape
    image_h, _ = image_shape
    scales = set(WAVE_TEMPLATE_SCALES)

    if template_h > 0 and image_h > 0:
        fit_scale = image_h / template_h
        for multiplier in (0.75, 0.85, 0.95, 1.0, 1.05, 1.15, 1.25):
            scale = fit_scale * multiplier
            if 0.25 <= scale <= 2.5:
                scales.add(round(scale, 3))

    return tuple(sorted(scales, reverse=True))


def get_wave(
    offset: tuple[int, int] | None = None,
    region: tuple[int, int, int, int] | None = None,
    debug: bool = False,
) -> int:
    """Wave recognition using template matching only.

    Args:
        offset: Optional Roblox-window offset used with the default wave region.
        region: Optional absolute screenshot_region coords: (x, y, width, height).
            When provided, this takes precedence over offset.
        debug: Print crop size, best match, chosen hits, and final result.
    """
    try:
        if region is None:
            if offset is None:
                offset = _roblox_window_offset() or (0, 0)
            region = _wave_region_from_offset(offset)

        img = wt.screenshot_region(region)
        if img is None:
            if debug:
                print(f"[get_wave] screenshot failed region={region}")
            return -1

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, gray = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
        if debug:
            print(f"[get_wave] region={region} crop={gray.shape[1]}x{gray.shape[0]}")

        wave_hits: list[list[int | float]] = []
        best_debug = (0.0, None, None)

        for digit in range(10):
            tpath = _resource_path(f"WaveRecon/{digit}.png")
            template = cv2.imread(str(tpath), cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue

            _, template = cv2.threshold(template, 250, 255, cv2.THRESH_BINARY_INV)

            for scale in _wave_candidate_scales(template.shape[:2], gray.shape[:2]):
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
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val > best_debug[0]:
                    best_debug = (float(max_val), digit, scale)
                loc = np.where(res >= WAVE_MATCH_THRESHOLD)
                for pt in zip(*loc[::-1]):
                    wave_hits.append([int(pt[0]), digit, float(res[pt[1], pt[0]])])

        if not wave_hits:
            if debug:
                print(
                    f"[get_wave] no hits region={region} crop={gray.shape[1]}x{gray.shape[0]} "
                    f"best={best_debug[0]:.3f} digit={best_debug[1]} scale={best_debug[2]}"
                )
            return -1

        # Dedupe overlapping matches from different scales / nearby peaks.
        wave_hits.sort(key=lambda h: float(h[2]), reverse=True)
        chosen: list[list[int | float]] = []
        for hit in wave_hits:
            x = int(hit[0])
            if any(abs(x - int(c[0])) <= WAVE_HIT_DEDUPE_DISTANCE for c in chosen):
                continue
            chosen.append(hit)

        chosen.sort(key=lambda h: int(h[0]))
        wave_number = "".join(str(int(h[1])) for h in chosen)
        if debug:
            print(
                f"[get_wave] best={best_debug[0]:.3f} digit={best_debug[1]} "
                f"scale={best_debug[2]} chosen={chosen} wave_number={wave_number!r}"
            )
        if not wave_number or len(wave_number) > 3:
            if debug:
                print(f"[get_wave] invalid wave_number={wave_number!r} hits={chosen}")
            return -1

        value = int(wave_number)
        if not (WAVE_MIN <= value <= WAVE_MAX):
            if debug:
                print(f"[get_wave] out of range value={value} hits={chosen}")
            return -1
        if debug:
            print(f"[get_wave] result={value}")
        return value
    except Exception as e:
        if debug:
            print(f"[get_wave] error: {type(e).__name__}: {e}")
        return -1


def restart_match(fast=False):
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
    if fast:
        time.sleep(0.1)
    else:
        time.sleep(0.7)


if __name__ == "__main__":
    print("Wave read:", get_wave())
