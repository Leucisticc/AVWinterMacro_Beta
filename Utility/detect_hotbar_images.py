import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Tools.screenHelpers import _get_backing_scale
from Tools.botTools import _grab_region

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
    scale = _get_backing_scale()
    if scale != 1.0:
        th, tw = template.shape[:2]
        template = cv2.resize(
            template,
            (max(1, int(tw / scale)), max(1, int(th / scale))),
            interpolation=cv2.INTER_AREA,
        )
    return template


def match_template_in_region(template, region: tuple, confidence: float):
    grab = _grab_region(region)
    if grab is None or grab.size == 0:
        return None

    th, tw = template.shape[:2]
    if grab.shape[0] < th or grab.shape[1] < tw:
        return None

    result = cv2.matchTemplate(grab, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < confidence:
        return None

    rx, ry, _, _ = region
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
    detections = []
    for template_path in resolve_template_paths():
        template = load_template(template_path)
        confidence = template_confidence(template_path)
        match = match_template_in_region(template, region, confidence)
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
    templates = resolve_template_paths()

    slot_detections = []
    for index, slot_region in enumerate(slot_regions, start=1):
        best_match = None

        for template_path in templates:
            template = load_template(template_path)
            confidence = template_confidence(template_path)
            match = match_template_in_region(template, slot_region, confidence)
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


def detect_unit_in_slot(slot_region: tuple, units: list[str], confidence: float = 0.8):
    """
    Check a list of unit names against a single slot region.
    Returns the best match dict (unit, score, box) or None.
    """
    best_match = None
    for unit in units:
        template_path = PROJECT_ROOT / "Resources" / "Winter" / f"{unit}_hb.png"
        if not template_path.is_file():
            continue
        template = load_template(template_path)
        match = match_template_in_region(template, slot_region, confidence)
        if match is None:
            continue
        if best_match is None or match["score"] > best_match["score"]:
            best_match = {"unit": unit, "score": match["score"], "box": match["box"]}

    return best_match


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
