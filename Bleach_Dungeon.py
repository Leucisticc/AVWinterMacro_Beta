import time
import pyautogui
import os
import sys
import webhook
import subprocess
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from threading import Thread
from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Controller
from Tools import botTools as bt
from Tools import winTools as wt
from Tools import avMethods as avM

failed_runs = 0
failed_matches = 0
loss_detection_active = False
loss_detected = False

#Editable settings
ainz_unit = 'rei' # Change to your units name as you would search for it
TWO_WB = True
ENABLE_PERIODIC_LOSS_CHECKER = True # Checks periodically if you have lost
LOSS_CHECK_INTERVAL_SECONDS = 20.0  # How many seconds it waits before checking again
MAX_NEGATIVE_MODIFIERS = 2 # Change this to make it more or less defficult



AINZ_SPELLS = False
COINS_PER_WIN = 150
VOTE_START_POS = (840,228)
CLOSE_POS = (602,380)
FOCUS_BOSS = (252,573)
ABILITY_POS = (650,450)
AUTO_ABILITY_POS = (701,449)
REPLAY_POS = (590,710) #(697,712)
REPLAY_IMG = "Replay.png"

MODIFIER_MATCH_CONFIDENCE = 0.6
MODIFIER_SELECTION_REGION = (228,271,1045,360)
MODIFIER_CARD_REGIONS: list[tuple[int, int, int, int]] = [
    (250, 315, 289, 210),
    (589, 328, 311, 208),
    (954, 331, 313, 213),
]
USE_CARD_MODIFIER_SELECTOR = True
USE_FAST_MODIFIER_CARD_SELECTOR = True
MODIFIER_SELECTION_TIMEOUT = 6.0

MODIFIERS = {
    "harvest": {
        "label": "Harvest",
        "image": "Bleach_Dungeon/Harvest.png",
        "alignment": "positive",
    },
    "fisticuffs": {
        "label": "Fisticuffs",
        "image": "Bleach_Dungeon/Fisticuffs.png",
        "alignment": "positive",
    },
    "damage": {
        "label": "Damage",
        "image": "Bleach_Dungeon/Damage.png",
        "alignment": "positive",
    },
    "cooldown": {
        "label": "Cooldown",
        "image": "Bleach_Dungeon/Cooldown.png",
        "alignment": "positive",
    },
    "slayer": {
        "label": "Slayer",
        "image": "Bleach_Dungeon/Slayer.png",
        "alignment": "positive",
    },
    "common": {
        "label": "Common",
        "image": "Bleach_Dungeon/Common.png",
        "alignment": "positive",
    },
    "uncommon": {
        "label": "Uncommon",
        "image": "Bleach_Dungeon/Uncommon.png",
        "alignment": "positive",
    },
    "press": {
        "label": "Press It",
        "image": "Bleach_Dungeon/Press.png",
        "alignment": "positive",
    },
    "champions": {
        "label": "Champions",
        "image": "Bleach_Dungeon/Champions.png",
        "alignment": "positive",
    },
    "dodge": {
        "label": "Dodge",
        "image": "Bleach_Dungeon/Dodge.png",
        "alignment": "negative",
    },
    "fast": {
        "label": "Fast",
        "image": "Bleach_Dungeon/Fast.png",
        "alignment": "negative",
    },
    "range": {
        "label": "Range",
        "image": "Bleach_Dungeon/Range.png",
        "alignment": "positive",
    },
    "planningahead": {
        "label": "Planning Ahead",
        "image": "Bleach_Dungeon/PlanningAhead.png",
        "alignment": "positive",
    },
    "strong": {
        "label": "Strong",
        "image": "Bleach_Dungeon/Strong.png",
        "alignment": "negative",
    },
}

POSITIVE_MODIFIERS = [name for name, data in MODIFIERS.items() if data["alignment"] == "positive"]
NEGATIVE_MODIFIERS = [name for name, data in MODIFIERS.items() if data["alignment"] == "negative"]
MODIFIER_TEMPLATE_CACHE: dict[str, dict] = {}

# Edit these lists to change what the bot prefers at each point in the run.
MODIFIER_PRIORITY_BY_PHASE = {
    "early": ["harvest", "champions", "uncommon", "common", "damage", "press", "range", "slayer", "cooldown", "dodge", "fast", "strong", "planningahead"],
    "late": ["harvest", "champions", "dodge", "strong", "uncommon", "common", "press", "damage", "slayer", "cooldown", "range", "fast", "planningahead"],
}

MODIFIER_PHASE_BY_WAVE = {
    "early": range(0, 21),
    "late": range(21, 31),
}

UNITS = {
    "ainzunit": {"name": "Reimu", "hotbar": (1000, 835), "pos": (1062, 570)},
    "hb6": {"name": "Nami", "hotbar": (1000, 835), "pos": (696, 275)},
    "hb5": {"name": "Ghost", "hotbar": (900, 835), "positions": [(1100,581), (740, 521)]},
    "ainz": {"name": "Ainz", "hotbar": (800, 835), "pos": (899, 627)},
    "hb3": {"name": "Rukia", "hotbar": (700, 835), "pos": (853, 577)},
    "hb2": {"name": "WB", "hotbar": (600, 835), "positions": [(768, 484), (1059, 663)]},
    "hb1": {"name": "Alucard", "hotbar": (500, 835), "pos": (949, 606)},
}

keyboard_controller = Controller()
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

#Stop Functions
def kill():
    os._exit(0)
    
def on_press(key):
    try:
        if hasattr(key, "char") and key.char and key.char.lower() == "k":
            kill()
    except Exception:
        pass

def write_text(text, interval=0.5):
    for char in text:
        keyboard_controller.press(char)
        keyboard_controller.release(char)
        time.sleep(interval)


def restart_script():
    try:
        args = list(sys.argv)
        if "--stopped" in args:
            args.remove("--stopped")
        if "--restart" in args:
            args.remove("--restart")

        sys.stdout.flush()
        subprocess.Popen([sys.executable, *args])
        os._exit(0)
    except Exception as e:
        print(f"[Restart] relaunch error: {e}")
        
listener = pynput_keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()



# AV Functions
def chord(keys=("a", "s", "d", "f", "g"), hold=0.03):
    for k in keys:
        keyboard_controller.press(k)
    time.sleep(hold)
    for k in reversed(keys):
        keyboard_controller.release(k)

def spam_chord_for_duration(keys=("[", "]", ";", "'", ","), duration=6.0, hold=0.02, gap=0.005):
    end_time = time.perf_counter() + duration
    while time.perf_counter() < end_time:
        chord(keys, hold=hold)
        if gap > 0:
            time.sleep(gap)
            
def _seen_pixel_from_screenshot(img, x: int, y: int, sample_half: int = 1):
    # Map pyautogui coords -> screenshot pixel coords using THIS screenshot
    sw, sh = pyautogui.size()
    iw, ih = img.size
    sx = iw / sw
    sy = ih / sh

    xp = int(x * sx)
    yp = int(y * sy)

    w, h = img.size
    left = max(0, xp - sample_half)
    top = max(0, yp - sample_half)
    right = min(w - 1, xp + sample_half)
    bottom = min(h - 1, yp + sample_half)

    px = []
    for yy in range(top, bottom + 1):
        for xx in range(left, right + 1):
            p = img.getpixel((xx, yy))
            if isinstance(p, tuple) and len(p) >= 3:
                px.append((p[0], p[1], p[2]))

    if not px:
        return (0, 0, 0)

    # median per channel
    rs = sorted(p[0] for p in px)
    gs = sorted(p[1] for p in px)
    bs = sorted(p[2] for p in px)
    mid = len(px) // 2
    return (rs[mid], gs[mid], bs[mid])

def _safe_screenshot(retries: int = 3, retry_delay: float = 0.12):
    """
    Best-effort screenshot helper for macOS capture flakiness.
    Returns a PIL image or None.
    """
    for _ in range(max(1, retries)):
        try:
            return pyautogui.screenshot()
        except Exception as e:
            last_error = e
            time.sleep(retry_delay)
    print(f"[screenshot] failed after retries: {last_error}")
    return None

def _resolve_image_path(img_path: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Resources",
        img_path,
    )

def _retina_to_screen_coords(x: int, y: int) -> tuple[int, int]:
    sw, sh = pyautogui.size()
    img = _safe_screenshot()
    if img is None:
        return int(x), int(y)

    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return int(x), int(y)

    scale_x = sw / iw
    scale_y = sh / ih
    return int(x * scale_x), int(y * scale_y)

def _screen_region_to_screenshot_region(region):
    if region is None:
        return None

    x, y, w, h = region
    img = _safe_screenshot()
    if img is None:
        return region

    sw, sh = pyautogui.size()
    iw, ih = img.size
    if sw <= 0 or sh <= 0:
        return region

    sx = iw / sw
    sy = ih / sh
    return (int(x * sx), int(y * sy), max(1, int(w * sx)), max(1, int(h * sy)))

def find_image_center(img_path: str, confidence: float = 0.8, grayscale: bool = False, region=None):
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

def click_image_center(
    img_path: str,
    confidence: float = 0.8,
    grayscale: bool = False,
    offset=(0, 0),
    region=None,
    delay: float = 0.1,
    right_click: bool = False,
    retries: int = 2,
    retry_delay: float = 0.05,
):
    last_error = None
    cx = cy = None
    for _ in range(max(1, retries)):
        try:
            cx, cy, _ = find_image_center(
                img_path,
                confidence=confidence,
                grayscale=grayscale,
                region=region,
            )
            if cx is not None and cy is not None:
                break
        except Exception as e:
            last_error = e
            break
        time.sleep(retry_delay)

    if cx is None or cy is None:
        if last_error is not None:
            resolved_img_path = _resolve_image_path(img_path)
            if not Path(resolved_img_path).is_file():
                print(f"[click_image_center] image file not found: {img_path}")
            else:
                print(f"[click_image_center] locate failed for {img_path}: {last_error}")
        return False

    cx, cy = _retina_to_screen_coords(cx, cy)
    ox, oy = offset if offset is not None else (0, 0)
    click(cx + int(ox), cy + int(oy), delay=delay, right_click=right_click)
    return True

def pixel_matches_seen(x: int, y: int, rgb: tuple[int, int, int], tol: int = 20, sample_half: int = 1) -> bool:
    img = _safe_screenshot()
    if img is None:
        return False
    r, g, b = _seen_pixel_from_screenshot(img, x, y, sample_half=sample_half)
    return (abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol)

def click(x, y=None, delay=None, right_click=False, dont_move=False):
    # Allow click((x, y)) and click(x, y)
    if y is None:
        x, y = x

    if delay is None:
        delay = 0.3

    if not dont_move:
        pyautogui.moveTo(x, y)

    time.sleep(delay)

    if right_click:
        pyautogui.rightClick()
    else:
        pyautogui.click()

def tap(key, hold=0.04, post_delay=0.03):
    # pynput is primary; pyautogui is fallback for games that ignore injected keys.
    try:
        keyboard_controller.press(key)
        time.sleep(hold)
        keyboard_controller.release(key)
    except Exception:
        pyautogui.press(str(key))
    time.sleep(post_delay)

def get_modifier(name: str) -> dict:
    modifier = MODIFIERS.get(name.lower())
    if modifier is None:
        raise ValueError(f"Unknown modifier: {name}")
    return modifier

def is_positive_modifier(name: str) -> bool:
    return get_modifier(name)["alignment"] == "positive"

def is_negative_modifier(name: str) -> bool:
    return get_modifier(name)["alignment"] == "negative"

def set_modifier_priority(phase: str, ordered_modifiers: list[str]) -> None:
    unknown = [name for name in ordered_modifiers if name.lower() not in MODIFIERS]
    if unknown:
        raise ValueError(f"Unknown modifiers in priority list: {unknown}")
    MODIFIER_PRIORITY_BY_PHASE[phase] = [name.lower() for name in ordered_modifiers]

def get_modifier_phase(wave: int | None = None, fallback: str = "early") -> str:
    if wave is None or wave < 0:
        return fallback

    for phase, wave_range in MODIFIER_PHASE_BY_WAVE.items():
        if wave in wave_range:
            return phase
    return fallback

def get_modifier_priority(phase: str | None = None, wave: int | None = None) -> list[str]:
    selected_phase = phase or get_modifier_phase(wave)
    if selected_phase not in MODIFIER_PRIORITY_BY_PHASE:
        raise ValueError(f"Unknown modifier phase: {selected_phase}")
    return MODIFIER_PRIORITY_BY_PHASE[selected_phase]

def get_current_modifier_wave(previous_wave: int | None) -> int | None:
    if previous_wave is None or previous_wave < 0:
        return None

    return previous_wave + 1

def _screenshot_to_screen_coords(x: int, y: int, img_size: tuple[int, int]) -> tuple[int, int]:
    sw, sh = pyautogui.size()
    iw, ih = img_size
    if iw <= 0 or ih <= 0:
        return int(x), int(y)

    scale_x = sw / iw
    scale_y = sh / ih
    return int(x * scale_x), int(y * scale_y)

def _load_modifier_templates():
    if MODIFIER_TEMPLATE_CACHE:
        return MODIFIER_TEMPLATE_CACHE

    for modifier_name, modifier in MODIFIERS.items():
        template_path = _resolve_image_path(modifier["image"])
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            print(f"[modifier] failed to load template: {modifier['image']}")
            continue

        MODIFIER_TEMPLATE_CACHE[modifier_name] = {
            "modifier": modifier,
            "template": template,
            "width": template.shape[1],
            "height": template.shape[0],
        }

    return MODIFIER_TEMPLATE_CACHE

def _capture_modifier_screen():
    screenshot = _safe_screenshot()
    if screenshot is None:
        return None
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

def _detect_modifier_in_region_fast(screen_img, region) -> tuple[str, dict, tuple[int, int], float] | None:
    search_region = _screen_region_to_screenshot_region(region)
    if search_region is None:
        return None

    rx, ry, rw, rh = search_region
    crop = screen_img[ry:ry + rh, rx:rx + rw]
    if crop.size == 0:
        return None

    best_match = None
    for modifier_name, template_data in _load_modifier_templates().items():
        template = template_data["template"]
        th, tw = template.shape[:2]
        if crop.shape[0] < th or crop.shape[1] < tw:
            continue

        result = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < MODIFIER_MATCH_CONFIDENCE:
            continue

        center = (
            rx + max_loc[0] + (tw // 2),
            ry + max_loc[1] + (th // 2),
        )
        if best_match is None or max_val > best_match[3]:
            best_match = (
                modifier_name,
                template_data["modifier"],
                center,
                max_val,
            )

    return best_match

def find_visible_modifier(
    phase: str | None = None,
    wave: int | None = None,
    negative_count: int = 0,
    max_negative_modifiers: int = MAX_NEGATIVE_MODIFIERS,
):
    for modifier_name in get_modifier_priority(phase=phase, wave=wave):
        if is_negative_modifier(modifier_name) and negative_count >= max_negative_modifiers:
            continue

        modifier = get_modifier(modifier_name)
        if bt.does_exist(
            modifier["image"],
            confidence=MODIFIER_MATCH_CONFIDENCE,
            grayscale=False,
            region=MODIFIER_SELECTION_REGION,
        ):
            return modifier_name, modifier
    return None, None

def select_modifier(
    phase: str | None = None,
    wave: int | None = None,
    negative_count: int = 0,
    max_negative_modifiers: int = MAX_NEGATIVE_MODIFIERS,
) -> str | None:
    priority_modifiers = get_modifier_priority(phase=phase, wave=wave)

    exit_index = len(priority_modifiers) - 2 if len(priority_modifiers) > 3 else None

    print("> Cycling through modifiers.")

    for allow_negative_overflow in (False, True):
        if allow_negative_overflow:
            print("No eligible modifiers found. Falling back to highest-priority visible modifier.")

        for index, modifier_name in enumerate(priority_modifiers):
            if exit_index is not None and index >= exit_index:
                if allow_negative_overflow:
                    break
                print("No modifiers detected by the final 3 priority entries. Assuming selection screen is gone.")
                return None

            modifier = get_modifier(modifier_name)
            if (
                not allow_negative_overflow
                and is_negative_modifier(modifier_name)
                and negative_count >= max_negative_modifiers
            ):
                print(f"Modifier visible but skipped: {modifier['label']} (negative cap reached).")
                continue

            if click_modifier(modifier_name):
                print(
                    f"Selected modifier: {modifier['label']}\n"
                    f"({modifier['alignment']}, phase={phase or get_modifier_phase(wave)})"
                )
                return modifier_name
            # print(f"Modifier not visible: {modifier['label']}")
    return None

def click_modifier(modifier_name: str) -> bool:
    modifier = get_modifier(modifier_name)
    clicked = click_image_center(
        modifier["image"],
        confidence=MODIFIER_MATCH_CONFIDENCE,
        grayscale=False,
        region=MODIFIER_SELECTION_REGION,
        delay=0.1,
        retries=1,
        retry_delay=0.05,
    )
    if not clicked:
        return False

    # print(f"Clicked {modifier['label']}.")
    time.sleep(0.12)
    return True

def detect_modifier_in_region(region) -> tuple[str, dict, tuple[int, int]] | None:
    for modifier_name, modifier in MODIFIERS.items():
        cx, cy, _ = find_image_center(
            modifier["image"],
            confidence=MODIFIER_MATCH_CONFIDENCE,
            grayscale=False,
            region=region,
        )
        if cx is None or cy is None:
            continue
        return modifier_name, modifier, (cx, cy)
    return None

def select_modifier_from_cards_fast(
    phase: str | None = None,
    wave: int | None = None,
    negative_count: int = 0,
    max_negative_modifiers: int = MAX_NEGATIVE_MODIFIERS,
) -> str | None:
    if len(MODIFIER_CARD_REGIONS) != 3:
        return select_modifier(
            phase=phase,
            wave=wave,
            negative_count=negative_count,
            max_negative_modifiers=max_negative_modifiers,
        )

    time.sleep(1.5)
    screen_img = _capture_modifier_screen()
    if screen_img is None:
        return None

    priority_modifiers = get_modifier_priority(phase=phase, wave=wave)
    visible_cards = []

    for index, region in enumerate(MODIFIER_CARD_REGIONS, start=1):
        detected = _detect_modifier_in_region_fast(screen_img, region)
        if detected is None:
            print(f"Modifier card {index}: no known modifier detected.")
            continue

        modifier_name, modifier, center, score = detected
        visible_cards.append((modifier_name, modifier, center))
        print(f"Modifier card {index}: detected {modifier['label']} ({score:.2f}).")

    if not visible_cards:
        print("No visible modifier cards detected in the configured regions.")
        return None

    print("Detected modifiers:", ", ".join(card_modifier["label"] for _, card_modifier, _ in visible_cards))

    for allow_negative_overflow in (False, True):
        if allow_negative_overflow:
            print("No eligible modifiers found. Falling back to highest-priority visible modifier.")

        for modifier_name in priority_modifiers:
            if (
                not allow_negative_overflow
                and is_negative_modifier(modifier_name)
                and negative_count >= max_negative_modifiers
            ):
                continue

            for visible_name, visible_modifier, center in visible_cards:
                if visible_name != modifier_name:
                    continue

                cx, cy = _screenshot_to_screen_coords(center[0], center[1], (screen_img.shape[1], screen_img.shape[0]))
                click(cx, cy, delay=0.1)
                time.sleep(0.12)
                print(
                    f"Selected modifier: {visible_modifier['label']} "
                    f"({visible_modifier['alignment']}, phase={phase or get_modifier_phase(wave)})\n"
                )
                return visible_name

    print("Visible modifiers found, but none matched the current eligible priority list.")
    return None

def select_modifier_from_cards(
    phase: str | None = None,
    wave: int | None = None,
    negative_count: int = 0,
    max_negative_modifiers: int = MAX_NEGATIVE_MODIFIERS,
) -> str | None:
    if USE_FAST_MODIFIER_CARD_SELECTOR:
        return select_modifier_from_cards_fast(
            phase=phase,
            wave=wave,
            negative_count=negative_count,
            max_negative_modifiers=max_negative_modifiers,
        )

    if len(MODIFIER_CARD_REGIONS) != 3:
        return select_modifier(
            phase=phase,
            wave=wave,
            negative_count=negative_count,
            max_negative_modifiers=max_negative_modifiers,
        )

    priority_modifiers = get_modifier_priority(phase=phase, wave=wave)
    visible_cards = []

    for index, region in enumerate(MODIFIER_CARD_REGIONS, start=1):
        detected = detect_modifier_in_region(region)
        if detected is None:
            print(f"Modifier card {index}: no known modifier detected.")
            continue

        modifier_name, modifier, center = detected
        visible_cards.append((modifier_name, modifier, center))
        print(f"Modifier card {index}: detected {modifier['label']}.")

    if not visible_cards:
        print("No visible modifier cards detected in the configured regions.")
        return None

    print("Detected modifiers:", ", ".join(card_modifier["label"] for _, card_modifier, _ in visible_cards))

    for allow_negative_overflow in (False, True):
        if allow_negative_overflow:
            print("No eligible modifiers found. Falling back to highest-priority visible modifier.")

        for modifier_name in priority_modifiers:
            if (
                not allow_negative_overflow
                and is_negative_modifier(modifier_name)
                and negative_count >= max_negative_modifiers
            ):
                continue

            for visible_name, visible_modifier, center in visible_cards:
                if visible_name != modifier_name:
                    continue

                cx, cy = _retina_to_screen_coords(center[0], center[1])
                click(cx, cy, delay=0.1)
                time.sleep(0.12)
            print(
                f"Selected modifier: {visible_modifier['label']} "
                f"({visible_modifier['alignment']}, phase={phase or get_modifier_phase(wave)})\n"
            )
            return visible_name

    print("Visible modifiers found, but none matched the current eligible priority list.")
    return None

def choose_modifier(
    phase: str | None = None,
    wave: int | None = None,
    negative_count: int = 0,
    max_negative_modifiers: int = MAX_NEGATIVE_MODIFIERS,
) -> str | None:
    if USE_CARD_MODIFIER_SELECTOR and len(MODIFIER_CARD_REGIONS) == 3:
        return select_modifier_from_cards(
            phase=phase,
            wave=wave,
            negative_count=negative_count,
            max_negative_modifiers=max_negative_modifiers,
        )

    return select_modifier(
        phase=phase,
        wave=wave,
        negative_count=negative_count,
        max_negative_modifiers=max_negative_modifiers,
    )

def wait_for_safe_action_wave(phase: str = "early", delay: float = 0.5) -> int | None:
    while True:
        wave = avM.get_wave()
        # print(wave)

        if wave == -1:
            choose_modifier(phase=phase)
            time.sleep(2)
            continue

        if wave is not None and wave >= 0 and (wave + 1) % 3 == 0:
            time.sleep(delay)
            continue

        if wave is not None:
            return wave

        time.sleep(delay)

        time.sleep(delay)


def do_action(action, *args, post_delay: float = 0.5, wait_phase: str = "early", wait_after: bool = True, **kwargs):
    action(*args, **kwargs)
    time.sleep(post_delay)
    if wait_after:
        return wait_for_safe_action_wave(phase=wait_phase)
    return None


def place_unit(
    unit,
    click_delay=0.6,
    step_delay=0.4,
    close=False,
):
    place_attempts = 15
    white_ui = (235, 235, 235)
    confirm_pixel = (604, 380)
    retry_confirm_delay = 0.2
    placed = False
    time.sleep(0.2)
    click(unit["hotbar"], delay=click_delay)
    time.sleep(step_delay)
    click(unit["pos"], delay=click_delay)
    time.sleep(step_delay)

    for attempt in range(place_attempts):
        if attempt > 0:
            time.sleep(retry_confirm_delay)
            if pixel_matches_seen(confirm_pixel[0], confirm_pixel[1], white_ui, tol=25, sample_half=2):
                placed = True
                break

            if bt.does_exist("Winter/UnitExists.png", confidence=0.8, grayscale=True):
                placed = True
                break

            print(f"[place_unit] hotbar click (retry {attempt}): {unit['name']}")
            click(unit["hotbar"], delay=0.12)
            time.sleep(0.12)
            click(unit["pos"], delay=0.51)
            time.sleep(0.09)

        if pixel_matches_seen(confirm_pixel[0], confirm_pixel[1], white_ui, tol=25, sample_half=2):
            placed = True
            break

        if bt.does_exist("Winter/UnitExists.png", confidence=0.8, grayscale=True):
            placed = True
            break

        if attempt == place_attempts - 1:
            print(f"[place_unit] timed out placing {unit['name']}")
            break

        tap('q')
        time.sleep(0.15)
        click(unit["pos"], delay=0.1)
        time.sleep(0.30)

        if bt.does_exist("Winter/UnitExists.png", confidence=0.8, grayscale=True):
            placed = True
            break

        if pixel_matches_seen(confirm_pixel[0], confirm_pixel[1], white_ui, tol=25, sample_half=2):
            placed = True
            break

    if placed:
        print(f"Placed Unit: {unit['name']}")

    if close:
        click(CLOSE_POS, delay=0.1)


def place_unit_at(unit, pos_index=0, **kwargs):
    unit_data = dict(unit)
    unit_data["pos"] = unit["positions"][pos_index]
    return place_unit(unit_data, **kwargs)

def click_vote_start(max_attempts: int = 5, delay: float = 0.6) -> bool:
    for attempt in range(1, max_attempts + 1):
        if bt.click_image("VoteStart.png", confidence=0.7, grayscale=False, region=(767, 189, 127, 83)):
            # print(f"Clicked Vote Start on attempt {attempt}.")
            return True

        click(VOTE_START_POS, delay=0.5)
        time.sleep(delay)

        if not bt.does_exist("VoteStart.png", confidence=0.7, grayscale=False, region=(767, 189, 127, 83)):
            print(f"Vote Start no longer visible after attempt {attempt}.")
            return True

    print("Vote Start click failed after retries.")
    return False

def handle_wave_zero_fisticuffs(delay: float = 1.0) -> None:
    while True:
        if click_modifier("fisticuffs"):
            print("Selected start modifier: Fisticuffs")
            time.sleep(0.5)
            click_vote_start()
            time.sleep(0.3)
            click(VOTE_START_POS)
            return

        print("Fisticuffs not visible. Restarting match.")
        click(744,503,delay=0.5)
        time.sleep(3)
        click(838,229,delay=0.5)
        time.sleep(4)
        avM.restart_match()
        time.sleep(delay)

def should_handle_modifier_wave(modifier_panel_open: bool, handled_waves: set[int]) -> bool:
    return modifier_panel_open and -1 not in handled_waves

def handle_modifier_selection(
    wave: int,
    modifier_panel_open: bool,
    phase_wave: int | None,
    negative_count: int,
    handled_waves: set[int],
    timeout: float = MODIFIER_SELECTION_TIMEOUT,
) -> int:
    if not should_handle_modifier_wave(modifier_panel_open, handled_waves):
        return negative_count

    handled_waves.add(wave)
    deadline = time.time() + timeout

    while time.time() < deadline:
        selected = choose_modifier(wave=phase_wave, negative_count=negative_count)
        if selected is not None:
            if is_negative_modifier(selected):
                negative_count += 1
                print(f"Negative modifiers selected: {negative_count}/{MAX_NEGATIVE_MODIFIERS}")

            time.sleep(0.4)
            return negative_count

        time.sleep(0.1)

    print(f"Modifier selection timed out on wave {wave}. Continuing run.")
    return negative_count

def wait_start(delay: int | None = None):
    i = 0
    if delay is None:
        delay = 1

    target = (99, 214, 63)

    while i < 90:
        i += 1
        try:
            # seen = pixel_color_seen(816, 231, sample_half=2)  # 5x5 median
            # print(f"Looking for start screen: Seen = {seen}")
            print(f"Looking for start screen.")

            if bt.does_exist("VoteStart.png", confidence=0.7, grayscale=False, region=(767, 189, 127,83)): 
                print("✅ Start screen detected")
                return True

        except Exception as e:
            print(f"e {e}")

        time.sleep(delay)

def quick_rts(): # Returns to spawn
    locations =[(232, 873), (1153, 503), (1217, 267)]
    for loc in locations:
        click(loc[0], loc[1], delay =0.1)
        time.sleep(0.2)
        
def slow_rts(): # Returns to spawn
    locations =[(232, 873), (1153, 503), (1217, 267)]
    for loc in locations:
        click(loc[0], loc[1], delay =1)
        time.sleep(0.2)

def shift_scroll(amount: int, post_delay: float = 0.1):
    pyautogui.keyDown("shift")
    try:
        time.sleep(0.05)
        pyautogui.scroll(amount)
        time.sleep(0.05)
    finally:
        pyautogui.keyUp("shift")
    time.sleep(post_delay)
    
def goToStart():
    print("Heading to location.")
    click(744,503, delay=0.5)
    time.sleep(3)
    quick_rts()
    time.sleep(1)
    click(1083, 291, right_click=True)
    time.sleep(3.3)
    click(1082,526, right_click=True)
    time.sleep(4)
    click(944,452, right_click=True)
    time.sleep(4)
    
    
    tap('right', hold=1)

def ainz_setup_spells():
    # spell_clicks = [
    #     (646, 513),
    #     (758, 462),
    #     (779, 500),
    #     (503, 400),
    #     (682, 462),
    #     (779, 439),
    #     (503, 400),
    #     (597, 463),
    #     (779, 439),
    #     (959, 645),
    # ]
    spell_clicks = [
        (646, 513),
        (682, 462),
        (779, 500),
        (503, 400),
        (597, 462),
        (779, 439),
        (959, 645),
    ]
    # Ends after the spell confirm click at (959, 645).
    click(UNITS["ainz"]["pos"])
    time.sleep(0.5)
    for index, pos in enumerate(spell_clicks):
        if AINZ_SPELLS and index < len(spell_clicks):
            continue
        click(pos[0], pos[1], delay=0.1)
        time.sleep(0.5)

def upgrade(unit, close: bool = False, click_delay: float = 0.1, post_delay: float = 0.3):
    click(unit["pos"], delay=click_delay)
    time.sleep(post_delay)
    tap('z')
    time.sleep(post_delay)
    print(f"Upgraded Unit: {unit['name']}")
    if close:
        click(CLOSE_POS, delay=0.1)

def place_ainz_unit():
    unit_clicks = [
        (650, 586),
        (688, 679),
        (481, 379),
        (495, 456),
        (618, 521),
        UNITS["ainzunit"]["pos"],
    ]

    click(UNITS["ainz"]["pos"])
    time.sleep(0.5)
    print("Placing Ainz Unit")

    for index, pos in enumerate(unit_clicks):
        click(pos[0], pos[1], delay=0.1)
        time.sleep(1)
        if index == 2:
            time.sleep(0.5)
            write_text(ainz_unit)
            time.sleep(0.5)
    
    if ainz_unit == 'rei':
            for i in range(2):
                tap('r')
                time.sleep(0.8)

def fully_upgrade(ability=False):
    print("Waiting for max upgrade.")
    click(UNITS["hb1"]["pos"])
    while not bt.does_exist("Unit_Maxed.png", confidence=0.7,grayscale=False):
        wait_for_safe_action_wave()
        time.sleep(5)
    
    if ability:
        click(AUTO_ABILITY_POS, delay=0.5)
    time.sleep(1)
    click(CLOSE_POS, delay=0.5)
        
def go_to_lobby():
    print("Going back to lobby.")
    time.sleep(1)
    click(1184,293,delay=0.8)
    time.sleep(1)
    click(218,878,delay=0.8)
    time.sleep(0.5)
    click(1180,587,delay=0.2)
    time.sleep(1)
    click(789,502,delay=0.8)
    time.sleep(0.5)
    click(677,568,delay=0.8)
    time.sleep(10)
    while not bt.does_exist("AreaIcon.png", confidence=0.7, grayscale=False):
        click(1086,318,delay=0.5)
        time.sleep(1)
        
    click(1180,587)
    
    
def wait_for_wave_30_and_modifiers(
    negative_count: int,
    handled_modifier_waves: set[int],
    delay: float = 0.5,
    timeout: float = 900.0,
) -> int:
    end_time = time.time() + timeout
    last_wave_pending = False
    final_modifier_pending = False
    final_wave_delay_applied = False
    last_non_modifier_wave = None

    while time.time() < end_time:
        current_wave = None
        try:
            current_wave = avM.get_wave()
            if current_wave != -1:
                handled_modifier_waves.discard(-1)
                last_non_modifier_wave = current_wave
                if current_wave == 29:
                    last_wave_pending = True

            modifier_panel_open = (
                current_wave == -1
                and last_non_modifier_wave is not None
                and last_non_modifier_wave >= 0
                and last_non_modifier_wave % 3 == 2
            )
            phase_wave = get_current_modifier_wave(last_non_modifier_wave)

            negative_count = handle_modifier_selection(
                wave=current_wave,
                modifier_panel_open=modifier_panel_open,
                phase_wave=phase_wave,
                negative_count=negative_count,
                handled_waves=handled_modifier_waves,
            )

            if modifier_panel_open and last_wave_pending and last_non_modifier_wave == 29:
                final_modifier_pending = True

            if (
                final_modifier_pending
                and current_wave == 30
                and not final_wave_delay_applied
            ):
                print("Final modifier handled on wave 30. Waiting 10 seconds before checking end state.")
                time.sleep(10)
                final_wave_delay_applied = True
                final_modifier_pending = False
                return negative_count

            if current_wave == 30 and not final_wave_delay_applied:
                return negative_count
                
        except Exception as e:
            print(f"modifier wait error: {e}")

        if current_wave is not None and current_wave >= 0:
            if current_wave % 3 == 1:
                sleep_delay = 10
            elif current_wave % 3 == 2:
                sleep_delay = 5
            else:
                sleep_delay = delay
        else:
            sleep_delay = delay

        time.sleep(sleep_delay)

    print("Timed out waiting for wave 30/modifier flow. Continuing to end check.")
    return negative_count


def wait_end(total_runs, negative_count: int, delay: float = 0.5, timeout: float = 180.0):
    global failed_runs
    global failed_matches
    global loss_detected
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            if loss_detected:
                print("❌ Periodic failure detected")
                return "fail", total_runs, negative_count
            if bt.does_exist("Victory.png", confidence=0.7, grayscale=False): #Won
                print("✅ Win detected")
                failed_runs = 0
                return "win", total_runs, negative_count
            elif bt.does_exist("Failed.png",confidence=0.7, grayscale=False): #Failed
                print("❌ Failure detected")
                return "fail", total_runs, negative_count
        except Exception as e:
            print(f"replay detect error: {e}")

        time.sleep(delay)

    print("❌ Replay button NOT detected (timeout)")
    return "timeout", total_runs, negative_count


def periodic_loss_checker():
    global loss_detected

    print(f"[Loss Checker] Active. Interval: {LOSS_CHECK_INTERVAL_SECONDS}s")
    while True:
        if not ENABLE_PERIODIC_LOSS_CHECKER or not loss_detection_active or loss_detected:
            time.sleep(1)
            continue

        try:
            if bt.does_exist("Failed.png", confidence=0.7, grayscale=False):
                loss_detected = True
                print("❌ Periodic failure checker found Failed.png")
                click(REPLAY_POS, delay=0.3)
                time.sleep(0.2)
                click(REPLAY_POS, delay=0.3)
                time.sleep(0.2)
                restart_script()
        except Exception as e:
            print(f"[Loss Checker] detect error: {e}")

        time.sleep(LOSS_CHECK_INTERVAL_SECONDS)

def _roblox_window_screenshot_for_webhook():
    try:
        roblox_window = wt.get_window("Roblox")
        if roblox_window is None:
            return None
        return wt.screen_shot_memory(roblox_window)
    except Exception as e:
        print(f"[Webhook] Roblox window screenshot failed: {e}")
        return None

def send_run_webhook(session_start: datetime, wins: int, losses: int, alert_text: str | None = None):
    runtime = str(datetime.now() - session_start).split(".")[0]
    rewards = wins * COINS_PER_WIN
    screenshot = _roblox_window_screenshot_for_webhook()
    webhook.send_webhook(
        run_time=runtime,
        task_name="Bleach Dungeon",
        win=wins,
        lose=losses,
        rewards=rewards,
        img=screenshot,
        alert_text=alert_text,
    )

def ensure_roblox_window_positioned():
    target_left, target_top = 200, 100
    target_width, target_height = 1100, 800

    try:
        window = wt.get_window("Roblox")
        if window is None:
            print("[Window] Roblox window not found; could not verify/position window.")
            return False

        left = int(getattr(window, "left", -1))
        top = int(getattr(window, "top", -1))
        width = int(getattr(window, "width", -1))
        height = int(getattr(window, "height", -1))

        already_positioned = (
            left == target_left and
            top == target_top and
            width == target_width and
            height == target_height
        )
        if already_positioned:
            return True

        wt.move_window(window, target_left, target_top)
        wt.resize_window(window, target_width, target_height)
        time.sleep(0.2)

        check_window = wt.get_window("Roblox") or window
        new_left = int(getattr(check_window, "left", -1))
        new_top = int(getattr(check_window, "top", -1))
        new_width = int(getattr(check_window, "width", -1))
        new_height = int(getattr(check_window, "height", -1))

        if (
            new_left == target_left and
            new_top == target_top and
            new_width == target_width and
            new_height == target_height
        ):
            print("[Window] Roblox window was not positioned correctly; corrected window position.")
            return True

        print(
            f"[Window] Roblox window was not positioned correctly; correction failed "
            f"(x={new_left}, y={new_top}, w={new_width}, h={new_height})."
        )
        return False
    except Exception as e:
        print(f"[Window] Roblox window was not positioned correctly; correction failed: {e}")
        return False

def _osascript(script: str) -> bool:
    try:
        subprocess.run(["osascript", "-e", script], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False
    

def focus_roblox():
    _osascript('tell application "Roblox" to activate')
    time.sleep(0.2)
    
def bleach_dungeon():
    global loss_detection_active
    global loss_detected

    print("Starting Bleach Macro.")
    print("Press K to stop.")
    time.sleep(1)
    focus_roblox()
    ensure_roblox_window_positioned()
    
    # while not avM.get_wave() == 0:
    #     avM.restart_match()
    session_start = datetime.now()
    total_runs = 0
    wins = 0
    losses = 0
    if not bt.does_exist("Bleach_Dungeon/Positioned.png", confidence=0.7, region=(673,351,208,169), grayscale=False):
        goToStart()
    while True:
        loss_detection_active = False
        loss_detected = False
        negative_modifier_count = 0
        handled_modifier_waves: set[int] = set()

        if total_runs>=1:
            click(REPLAY_POS, delay=0.3)
            time.sleep(0.3)
            click(REPLAY_POS, delay=0.3)
            time.sleep(0.5)
        handle_wave_zero_fisticuffs()
        loss_detection_active = True
        time.sleep(0.2)
        place_unit(UNITS['hb6'])
        while avM.get_wave() < 1:
            time.sleep(0.5)
        do_action(place_unit_at, UNITS["hb5"], 0, wait_after=False)
        do_action(place_unit, UNITS["ainz"], wait_after=False)
        do_action(place_ainz_unit, wait_after=False)
        do_action(place_unit, UNITS["hb1"])
        do_action(place_unit_at, UNITS["hb5"], 1)
        do_action(place_unit_at, UNITS["hb2"], 0)
        do_action(upgrade, UNITS['hb6'])
        do_action(upgrade, UNITS['hb1'])
        do_action(ainz_setup_spells)
        do_action(fully_upgrade, ability=True)
        if TWO_WB:
            do_action(place_unit_at, UNITS["hb2"], 1)
        do_action(upgrade, UNITS['ainz'], close=True)

        negative_modifier_count = wait_for_wave_30_and_modifiers(
            negative_count=negative_modifier_count,
            handled_modifier_waves=handled_modifier_waves,
        )
        
        end_state, total_runs, negative_modifier_count = wait_end(
            total_runs,
            negative_modifier_count,
        )
        loss_detection_active = False

        if end_state == "win":
            wins += 1
            total_runs += 1
            send_run_webhook(session_start=session_start, wins=wins, losses=losses)
            print(f"Runs: {wins+losses} | Wins: {wins} | Losses: {losses} | Runtime: {str(datetime.now() - session_start).split('.')[0]}")
        elif end_state == "fail":
            losses += 1
            total_runs += 1
            send_run_webhook(
                session_start=session_start,
                wins=wins,
                losses=losses,
                alert_text=f"@everyone Bleach dungeon lost a run. Total losses: {losses}",
            )
            print("Run failed; wins not incremented.")
        else:
            print("Replay not detected; skipping win stat update for this cycle.")
            click(REPLAY_POS, delay=0.3)
        
        # Loop again from wait_start() on next iteration.
        continue
Thread(target=periodic_loss_checker, daemon=True).start()
bleach_dungeon()