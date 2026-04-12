import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pyautogui

try:
    from Tools import winTools as wt
except ModuleNotFoundError:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from Tools import winTools as wt


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = PROJECT_ROOT / "Resources"
DEBUG_DIR = RESOURCES_DIR / "debug_shots"

REGION_MODE = "screen"  # "screen" or "roblox"
CONFIDENCE = 0.7

TEMPLATES = (
    ("Failed.png", False, (384, 262, 103, 42)),
    ("Failed.png", True, (384, 262, 103, 42)),
    ("Winter/DetectLoss.png", False, (314, 316, 213, 111)),
    ("Winter/DetectLoss.png", True, (314, 316, 213, 111)),
    ("Winter/DetectLoss2.png", False, (314, 316, 213, 111)),
    ("Winter/DetectLoss2.png", True, (314, 316, 213, 111)),
)


def _resource_path(relative_path: str) -> Path:
    return RESOURCES_DIR / relative_path


def _get_frontmost_window_macos():
    script = r'''
tell application "System Events"
    set frontProc to first application process whose frontmost is true
    set appName to name of frontProc
    tell frontProc
        if (count of windows) is 0 then
            return appName & "|NO_WINDOW"
        end if
        set {xPos, yPos} to position of front window
        set {winW, winH} to size of front window
        return appName & "|" & xPos & "|" & yPos & "|" & winW & "|" & winH
    end tell
end tell
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            print("[detect-loss test] osascript error:", (result.stderr or "").strip())
            return None

        raw = (result.stdout or "").strip()
        if not raw or raw.endswith("|NO_WINDOW"):
            return None

        parts = raw.split("|")
        if len(parts) != 5:
            print("[detect-loss test] unexpected osascript output:", raw)
            return None

        title, left, top, width, height = parts
        return SimpleNamespace(
            title=title,
            left=int(left),
            top=int(top),
            width=int(width),
            height=int(height),
        )
    except Exception as e:
        print("[detect-loss test] frontmost window fallback failed:", e)
        return None


def _get_roblox_window_or_fallback():
    w = wt.get_window("Roblox")
    if w is not None:
        return w

    print("[detect-loss test] wt.get_window('Roblox') failed, trying frontmost-window fallback...")
    w = _get_frontmost_window_macos()
    if w is None:
        return None

    title = str(getattr(w, "title", "") or "")
    if "roblox" not in title.lower():
        print(f"[detect-loss test] frontmost window is not Roblox: {title!r}")
        print("[detect-loss test] Focus Roblox and run again.")
        return None
    return w


def _resolve_region(region):
    mode = str(REGION_MODE).strip().lower()
    if mode not in {"screen", "roblox"}:
        raise ValueError("REGION_MODE must be 'screen' or 'roblox'.")

    x, y, w, h = (int(v) for v in region)
    if mode == "screen":
        return (x, y, w, h), None

    window = _get_roblox_window_or_fallback()
    if window is None:
        raise RuntimeError("Roblox window not found. Focus Roblox and try again.")

    return (
        int(window.left + x),
        int(window.top + y),
        w,
        h,
    ), window


def _safe_full_screenshot():
    last_error = None
    for _ in range(3):
        try:
            img = pyautogui.screenshot()
            return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            last_error = e
            time.sleep(0.12)
    raise RuntimeError(f"full screenshot failed: {last_error}")


def _load_template(relative_path: str, grayscale: bool):
    flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    template = cv2.imread(str(_resource_path(relative_path)), flag)
    if template is None:
        raise RuntimeError(f"failed to load template: {relative_path}")
    return template


def _match_template(template, haystack, grayscale: bool):
    if grayscale:
        if haystack.ndim == 3:
            haystack = cv2.cvtColor(haystack, cv2.COLOR_BGR2GRAY)
    elif haystack.ndim == 2:
        haystack = cv2.cvtColor(haystack, cv2.COLOR_GRAY2BGR)

    th, tw = template.shape[:2]
    hh, hw = haystack.shape[:2]
    if th > hh or tw > hw:
        return None

    result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return {
        "score": float(max_val),
        "loc": max_loc,
        "size": (tw, th),
    }


def _annotate(image, match, label):
    annotated = image.copy()
    if match is None:
        return annotated

    x, y = match["loc"]
    w, h = match["size"]
    cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 0, 255), 2)
    cv2.putText(
        annotated,
        label,
        (max(0, x), max(20, y - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )
    return annotated


def main():
    time.sleep(1)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    full_img = _safe_full_screenshot()
    window = None

    if str(REGION_MODE).strip().lower() == "roblox":
        _, window = _resolve_region((314, 316, 213, 111))

    print(f"Mode: {REGION_MODE}")
    if window is not None:
        print(
            "Roblox window: "
            f"title={getattr(window, 'title', '')!r} "
            f"left={getattr(window, 'left', '?')} "
            f"top={getattr(window, 'top', '?')} "
            f"width={getattr(window, 'width', '?')} "
            f"height={getattr(window, 'height', '?')}"
        )
    print("")

    best_result = None
    for template_name, grayscale, region in TEMPLATES:
        region, current_window = _resolve_region(region)
        region_img = wt.screenshot_region(region)
        if region_img is None or region_img.size == 0:
            print(f"{template_name} [{'gray' if grayscale else 'color'}] | region={region} | capture failed")
            continue

        template = _load_template(template_name, grayscale=grayscale)
        region_match = _match_template(template, region_img, grayscale=grayscale)
        full_match = _match_template(template, full_img, grayscale=grayscale)

        region_score = region_match["score"] if region_match else None
        full_score = full_match["score"] if full_match else None
        passed = region_score is not None and region_score >= CONFIDENCE

        mode_name = "gray" if grayscale else "color"
        print(
            f"{template_name} [{mode_name}] | "
            f"region={region} | "
            f"region_score={region_score!s} | full_score={full_score!s} | "
            f"passes_region={passed}"
        )

        if region_match is not None:
            annotated = _annotate(
                region_img,
                region_match,
                f"{Path(template_name).name} {region_score:.3f}",
            )
            out_path = DEBUG_DIR / (
                f"detect_loss_match_{Path(template_name).stem}_{mode_name}_{stamp}.png"
            )
            cv2.imwrite(str(out_path), annotated)

        if best_result is None or (
            region_score is not None and region_score > best_result["score"]
        ):
            best_result = {
                "template": template_name,
                "grayscale": grayscale,
                "region": region,
                "score": region_score if region_score is not None else float("-inf"),
            }

    print("")
    if best_result is not None:
        print(
            "Best region match: "
            f"{best_result['template']} "
            f"[{'gray' if best_result['grayscale'] else 'color'}] "
            f"region={best_result['region']} "
            f"score={best_result['score']:.3f}"
        )
    print(f"Threshold used by detect_loss: {CONFIDENCE}")
    print("If the best region score is below the threshold, the region or template is the problem.")


if __name__ == "__main__":
    main()
