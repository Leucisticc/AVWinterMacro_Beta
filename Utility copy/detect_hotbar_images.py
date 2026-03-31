import argparse
import time
from pathlib import Path

import cv2
import numpy as np
import pyautogui


PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOTBAR_REGION = (470, 771, 570, 118)
HOTBAR_SLOT_REGIONS = (
    (469, 782, 94, 89),
    (562, 780, 95, 90),
    (656, 776, 94, 95),
    (748, 780, 97, 91),
    (843, 780, 95, 93),
    (938, 777, 95, 91),
)
DEFAULT_CONFIDENCE = 0.8
MIRKO_CONFIDENCE = 0.8

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


def safe_screenshot(retries: int = 3, retry_delay: float = 0.12):
    last_error = None
    for _ in range(max(1, retries)):
        try:
            return pyautogui.screenshot()
        except Exception as e:
            last_error = e
            time.sleep(retry_delay)
    raise RuntimeError(f"screenshot failed after retries: {last_error}")


def screen_region_to_screenshot_region(region, screenshot):
    x, y, w, h = region
    sw, sh = pyautogui.size()
    iw, ih = screenshot.size
    if sw <= 0 or sh <= 0 or iw <= 0 or ih <= 0:
        return region

    sx = iw / sw
    sy = ih / sh
    return (int(x * sx), int(y * sy), max(1, int(w * sx)), max(1, int(h * sy)))


def resolve_template_paths():
    roots = [
        PROJECT_ROOT / "Resources" / "Winter",
        PROJECT_ROOT / "Winter",
    ]

    templates = []
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*_hb.png")):
            if path.name in seen:
                continue
            seen.add(path.name)
            templates.append(path)
    return templates


def load_template(path: Path):
    template = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if template is None:
        raise RuntimeError(f"failed to read template: {path}")
    return template


def match_template_in_hotbar(template, screenshot_bgr, search_region, confidence: float):
    rx, ry, rw, rh = search_region
    crop = screenshot_bgr[ry:ry + rh, rx:rx + rw]
    if crop.size == 0:
        return None

    th, tw = template.shape[:2]
    if crop.shape[0] < th or crop.shape[1] < tw:
        return None

    result = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < confidence:
        return None

    return {
        "score": float(max_val),
        "box": (rx + max_loc[0], ry + max_loc[1], tw, th),
    }


def template_confidence(path: Path) -> float:
    stem = path.stem.lower()
    if stem in {"mirko_hb", "bunny_hb"}:
        return MIRKO_CONFIDENCE
    return DEFAULT_CONFIDENCE


def detect_hotbar_images(region):
    screenshot = safe_screenshot()
    screenshot_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    search_region = screen_region_to_screenshot_region(region, screenshot)

    detections = []
    for template_path in resolve_template_paths():
        template = load_template(template_path)
        confidence = template_confidence(template_path)
        match = match_template_in_hotbar(template, screenshot_bgr, search_region, confidence)
        if match is None:
            continue
        detections.append(
            {
                "name": template_path.stem.replace("_hb", ""),
                "template": str(template_path.relative_to(PROJECT_ROOT)),
                "confidence": confidence,
                "score": match["score"],
                "box": match["box"],
            }
        )

    detections.sort(key=lambda item: item["score"], reverse=True)
    return detections


def detect_hotbar_images_per_slot(slot_regions):
    screenshot = safe_screenshot()
    screenshot_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    templates = resolve_template_paths()

    slot_detections = []
    for index, slot_region in enumerate(slot_regions, start=1):
        search_region = screen_region_to_screenshot_region(slot_region, screenshot)
        best_match = None

        for template_path in templates:
            template = load_template(template_path)
            confidence = template_confidence(template_path)
            match = match_template_in_hotbar(template, screenshot_bgr, search_region, confidence)
            if match is None:
                continue

            candidate = {
                "slot": index,
                "slot_region": slot_region,
                "name": template_path.stem.replace("_hb", ""),
                "template": str(template_path.relative_to(PROJECT_ROOT)),
                "confidence": confidence,
                "score": match["score"],
                "box": match["box"],
            }
            if best_match is None or candidate["score"] > best_match["score"]:
                best_match = candidate

        slot_detections.append(best_match)

    return slot_detections


def print_detections(detections, region):
    print(f"Hotbar region: {region}")
    if not detections:
        print("No hotbar images detected.")
        return

    print(f"Detected {len(detections)} hotbar image(s):")
    for item in detections:
        left, top, width, height = item["box"]
        print(
            f"- {item['name']}: score={item['score']:.3f}, threshold={item['confidence']:.2f}, "
            f"box=({left}, {top}, {width}, {height}), template={item['template']}"
        )


def print_slot_detections(detections):
    print("Hotbar mode: per-slot")
    for index, item in enumerate(detections, start=1):
        region = HOTBAR_SLOT_REGIONS[index - 1]
        if item is None:
            print(f"- slot {index}: no hotbar image detected, region={region}")
            continue

        left, top, width, height = item["box"]
        print(
            f"- slot {index}: {item['name']} score={item['score']:.3f}, "
            f"threshold={item['confidence']:.2f}, region={region}, "
            f"box=({left}, {top}, {width}, {height}), template={item['template']}"
        )


def parse_args():
    parser = argparse.ArgumentParser(description="Detect Winter hotbar images in the hotbar region.")
    parser.add_argument("--x", type=int, default=HOTBAR_REGION[0])
    parser.add_argument("--y", type=int, default=HOTBAR_REGION[1])
    parser.add_argument("--w", type=int, default=HOTBAR_REGION[2])
    parser.add_argument("--h", type=int, default=HOTBAR_REGION[3])
    parser.add_argument(
        "--per-slot",
        action="store_true",
        help="Detect the best hotbar image in each of the six slot regions instead of scanning the full hotbar.",
    )
    parser.add_argument("--watch", action="store_true", help="Repeat detection until stopped.")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between scans in watch mode.")
    return parser.parse_args()


def main():
    args = parse_args()
    region = (args.x, args.y, args.w, args.h)

    if not args.watch:
        if args.per_slot:
            print_slot_detections(detect_hotbar_images_per_slot(HOTBAR_SLOT_REGIONS))
        else:
            print_detections(detect_hotbar_images(region), region)
        return

    mode_label = "per-slot" if args.per_slot else "full-hotbar"
    print(f"Watching hotbar in {mode_label} mode. Press Ctrl+C to stop.")
    while True:
        print()
        if args.per_slot:
            print_slot_detections(detect_hotbar_images_per_slot(HOTBAR_SLOT_REGIONS))
        else:
            print_detections(detect_hotbar_images(region), region)
        time.sleep(max(0.1, args.interval))


if __name__ == "__main__":
    main()
