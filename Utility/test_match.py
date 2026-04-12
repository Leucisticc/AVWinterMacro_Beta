"""
Image match + pixel color debugger.

Modes (set MODE below):
  "match" — template match test (default)
  "pixel" — report the exact RGB mss reads at PIXEL_POS
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pyautogui
from PIL import Image

try:
    import mss as _mss_lib
    _mss = _mss_lib.mss()
except Exception:
    _mss = None

# ── config ────────────────────────────────────────────────────────────────────
MODE          = "bt"              # "match" or "pixel"

# match mode
TEMPLATE_NAME = "VoteStart.png"
REGION        = (767, 189, 127, 83)  # exact region used in Winter_Event.py
CONFIDENCE    = 0.7
GRAYSCALE     = False

# pixel mode
PIXEL_POS     = (765, 791)           # screen-space (x, y)
PIXEL_EXPECT  = (2, 0, 0)           # expected RGB
PIXEL_TOL     = 20
PIXEL_SAMPLE  = 0                    # sample_half (0 = single pixel, 1 = 3×3 median)
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR      = Path(__file__).resolve().parent
RESOURCES_DIR = BASE_DIR / "Resources"
TEMPLATE_PATH = RESOURCES_DIR / TEMPLATE_NAME
DEBUG_DIR     = BASE_DIR / "Resources" / "debug_shots"
DEBUG_DIR.mkdir(exist_ok=True)


def take_full_screenshot() -> Image.Image | None:
    if _mss is not None:
        monitor = _mss.monitors[0]
        shot = _mss.grab(monitor)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    return pyautogui.screenshot()


def scale_region_to_screenshot(region, screenshot: Image.Image):
    """Convert screen-space region to screenshot-pixel region."""
    sw, sh = pyautogui.size()
    iw, ih = screenshot.size
    sx, sy = iw / sw, ih / sh
    x, y, w, h = region
    return (int(x * sx), int(y * sy), max(1, int(w * sx)), max(1, int(h * sy)))


def retina_scale(screenshot: Image.Image):
    sw, sh = pyautogui.size()
    iw, ih = screenshot.size
    return iw / sw, ih / sh


def run_test():
    print(f"Template : {TEMPLATE_PATH}")
    print(f"Region   : {REGION}  (screen-space)")
    print(f"Grayscale: {GRAYSCALE}")
    print()

    # ── load template ─────────────────────────────────────────────────────────
    if not TEMPLATE_PATH.exists():
        print(f"ERROR: template not found at {TEMPLATE_PATH}")
        sys.exit(1)

    read_mode = cv2.IMREAD_GRAYSCALE if GRAYSCALE else cv2.IMREAD_COLOR
    template = cv2.imread(str(TEMPLATE_PATH), read_mode)
    print(f"Template size (raw) : {template.shape[1]}×{template.shape[0]} px")

    # Detect backing scale and downscale template to match mss logical resolution
    try:
        from AppKit import NSScreen
        backing_scale = float(NSScreen.mainScreen().backingScaleFactor())
    except Exception:
        backing_scale = 1.0
    print(f"Backing scale : {backing_scale}×")
    if backing_scale != 1.0:
        th_raw, tw_raw = template.shape[:2]
        new_w = max(1, int(tw_raw / backing_scale))
        new_h = max(1, int(th_raw / backing_scale))
        template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)
        print(f"Template size (scaled to mss): {template.shape[1]}×{template.shape[0]} px")

    # ── capture screen ────────────────────────────────────────────────────────
    screenshot = take_full_screenshot()
    if screenshot is None:
        print("ERROR: screenshot failed")
        sys.exit(1)

    screen_w, screen_h = pyautogui.size()
    ss_w, ss_h = screenshot.size
    rx, ry = ss_w / screen_w, ss_h / screen_h
    print(f"Screen size   : {screen_w}×{screen_h} (logical points)")
    print(f"Screenshot    : {ss_w}×{ss_h} px  →  retina scale {rx:.2f}×{ry:.2f}")

    # ── crop region ───────────────────────────────────────────────────────────
    ss_region = scale_region_to_screenshot(REGION, screenshot)
    print(f"Region (screen)     : {REGION}")
    print(f"Region (screenshot) : {ss_region}")

    screen_arr = np.array(screenshot)
    full_bgr = cv2.cvtColor(screen_arr, cv2.COLOR_RGB2GRAY if GRAYSCALE else cv2.COLOR_RGB2BGR)

    rx_ss, ry_ss, rw_ss, rh_ss = ss_region
    crop = full_bgr[ry_ss:ry_ss + rh_ss, rx_ss:rx_ss + rw_ss]
    print(f"Crop size           : {crop.shape[1]}×{crop.shape[0]} px")

    # ── save debug images ─────────────────────────────────────────────────────
    crop_path    = str(DEBUG_DIR / "debug_crop.png")
    template_out = str(DEBUG_DIR / "debug_template.png")
    cv2.imwrite(crop_path, crop)
    cv2.imwrite(template_out, template)
    print()
    print(f"Saved  {crop_path}")
    print(f"       └─ what mss captured for the region")
    print(f"Saved  {template_out}")
    print(f"       └─ the template being matched")

    # ── match ─────────────────────────────────────────────────────────────────
    th, tw = template.shape[:2]
    if crop.shape[0] < th or crop.shape[1] < tw:
        # Suggest a region that fits the template, centred on the original region
        ox, oy, ow, oh = REGION
        pad_x = max(0, tw - ow)
        pad_y = max(0, th - oh)
        suggested = (ox - pad_x // 2, oy - pad_y // 2, ow + pad_x, oh + pad_y)
        print()
        print(f"ERROR: crop ({crop.shape[1]}×{crop.shape[0]}) is smaller than "
              f"template ({tw}×{th}) — match impossible.")
        print(f"       Suggested region (fits template): {suggested}")
        sys.exit(1)

    result = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    print()
    print(f"Best confidence : {max_val:.4f}  (threshold = {CONFIDENCE})")
    print(f"Match location  : {max_loc}  (within the crop)")
    if max_val >= CONFIDENCE:
        print("RESULT: ✅  MATCH FOUND")
    else:
        print("RESULT: ❌  NO MATCH")
        if max_val >= CONFIDENCE * 0.75:
            print("       Confidence is close — try lowering the threshold or using grayscale=True.")
        else:
            print("       Confidence is low — the region likely doesn't contain the template right now,")
            print("       or the template was captured at a different scale/resolution.")


def run_pixel_test():
    x, y = PIXEL_POS
    size = max(1, PIXEL_SAMPLE * 2 + 1)
    monitor = {"left": x - PIXEL_SAMPLE, "top": y - PIXEL_SAMPLE, "width": size, "height": size}

    print(f"Pixel pos    : {PIXEL_POS}")
    print(f"Sample area  : {size}×{size}  (sample_half={PIXEL_SAMPLE})")
    print(f"Expected RGB : {PIXEL_EXPECT}  tol={PIXEL_TOL}")
    print()

    if _mss is None:
        print("ERROR: mss not available")
        sys.exit(1)

    shot = _mss.grab(monitor)
    arr = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
    rgb = arr[:, :, [2, 1, 0]]
    med = np.median(rgb.reshape(-1, 3), axis=0).astype(int)
    seen = (int(med[0]), int(med[1]), int(med[2]))

    r, g, b = seen
    er, eg, eb = PIXEL_EXPECT
    matches = abs(r - er) <= PIXEL_TOL and abs(g - eg) <= PIXEL_TOL and abs(b - eb) <= PIXEL_TOL

    print(f"mss raw grab : {shot.width}×{shot.height} px")
    print(f"Seen RGB     : {seen}")
    print(f"Delta        : ({abs(r-er)}, {abs(g-eg)}, {abs(b-eb)})")
    print()
    if matches:
        print("RESULT: ✅  MATCH  — pixel_matches_at would return True")
    else:
        print("RESULT: ❌  NO MATCH  — pixel_matches_at would return False")
        print(f"       Closest channel delta exceeds tol={PIXEL_TOL}")
        print(f"       To match this color use: pixel_matches_at({x},{y},{seen},tol={PIXEL_TOL})")


def run_bt_test():
    """Call bt.does_exist exactly as Winter_Event.py does and report what happens."""
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from Tools import botTools as bt

    print(f"Template : {TEMPLATE_NAME}")
    print(f"Region   : {REGION}")
    print(f"Confidence: {CONFIDENCE}  Grayscale: {GRAYSCALE}")
    print()

    # Patch _locate_image to print internals (mirrors _grab_region approach)
    _orig = bt._locate_image
    def _debug_locate(img_path, confidence, grayscale, region=None):
        import cv2, numpy as np
        import pyautogui
        from Tools.screenHelpers import _get_backing_scale
        print(f"  img_path         : {img_path}")

        template_flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
        raw = cv2.imread(img_path, template_flag)
        if raw is None:
            print(f"  ERROR: cv2.imread returned None — file not found")
            return None
        print(f"  template (raw)   : {raw.shape[1]}×{raw.shape[0]}")

        scale = _get_backing_scale()
        print(f"  backing scale    : {scale}×")
        if scale != 1.0:
            th_r, tw_r = raw.shape[:2]
            raw = cv2.resize(raw, (max(1, int(tw_r/scale)), max(1, int(th_r/scale))), interpolation=cv2.INTER_AREA)
            print(f"  template (scaled): {raw.shape[1]}×{raw.shape[0]}")

        if region is None:
            sw, sh = pyautogui.size()
            region = (0, 0, sw, sh)
        grab = bt._grab_region(region)
        if grab is None:
            print(f"  ERROR: _grab_region returned None")
            return None
        print(f"  region           : {region}")
        print(f"  grab size        : {grab.shape[1]}×{grab.shape[0]} px")

        haystack = cv2.cvtColor(grab, cv2.COLOR_BGR2GRAY) if grayscale else grab
        th, tw = raw.shape[:2]
        if haystack.shape[0] < th or haystack.shape[1] < tw:
            print(f"  ERROR: grab ({grab.shape[1]}×{grab.shape[0]}) smaller than template ({tw}×{th})")
            return None
        result = cv2.matchTemplate(haystack, raw, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        print(f"  confidence       : {max_val:.4f}  (threshold={confidence})")
        print(f"  RESULT: {'✅ MATCH' if max_val >= confidence else '❌ NO MATCH'}")

        # Save the live grab and scaled template so you can visually compare them
        grab_out = str(DEBUG_DIR / "bt_live_grab.png")
        tmpl_out = str(DEBUG_DIR / "bt_live_template.png")
        cv2.imwrite(grab_out, grab)
        cv2.imwrite(tmpl_out, raw)
        print(f"  Saved grab      → {grab_out}")
        print(f"  Saved template  → {tmpl_out}")

        return _orig(img_path, confidence, grayscale, region)

    bt._locate_image = _debug_locate
    result = bt.does_exist(TEMPLATE_NAME, confidence=CONFIDENCE, grayscale=GRAYSCALE, region=REGION)
    print()
    print(f"bt.does_exist returned: {result}")


if __name__ == "__main__":
    if MODE == "pixel":
        run_pixel_test()
    elif MODE == "bt":
        run_bt_test()
    else:
        run_test()
