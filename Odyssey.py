import os
import time
from datetime import datetime

import cv2
import numpy as np
import pyautogui
import webhook
from pynput import keyboard as pynput_keyboard

from Tools import botTools as bt
from Tools import avMethods as avM
from Tools import winTools as wt
from Tools import gameHelpers as gh
from Tools.screenHelpers import pixel_color_at, pixel_matches_at

# ================ LOADOUT COMPOSITION ================ #
# Ragna
# ================================================== #
WEBHOOKS_ENABLED = True  # If False, only treasure alerts send webhooks.
TREASURE_PING_EVERYONE = True
TREASURE_PING_USER_ID = ""
FAST_BOSS = False

VOTE_START_POS = (962,239)
WAVE_REGION = (630, 158, 55, 24)
FAST_BOSS_APPLY_POSITION = (927, 595)

SETTINGS_BUTTON = (224, 876)
SETTINGS_CLOSE = (1393, 262)
AUTO_START_CHECK = (1359, 603)
# AUTO_REPLAY_CHECK = (894, 567)

AUTO_PLAY = (1484, 695)

MAPS = (418,186)
MAPS_COLOUR = (152,142,248)
MAPS_REGION = (258, 257, 879, 480)

SELECT_FLOOR = (1220,427)
SELECT_FLOOR_COLOUR = (88, 186, 117)
SHOP_CONFIRM = (1069, 291)
SHOP_CONFIRM_COLOUR = (255, 255, 255)

SKIP_REGION = (648, 743, 378, 152)
START_REGION = (849, 171, 208, 127)
first_match = True
last_match_type = None
pending_floor_type = None
treasure_continue_requested = False

IMAGE_DIRECTORY = "Odyssey"
MAP_IMAGE_CONFIDENCE = 0.7
MIN_AVAILABLE_MAP_BRIGHTNESS = 85
SKIP_IMAGE_CONFIDENCE = 0.7
TREASURE_IMAGE_CONFIDENCE = 0.7
ELITE_SKIP_INITIAL_DELAY_SECONDS = 70
MAP_TYPE_MATCH_SETTINGS = {
    "Escanor_Boss": {
        "confidence": 0.4,
        "grayscale": True,
        "scales": (1.0, 0.95, 1.05, 0.9, 1.1, 0.85, 1.15, 0.8, 1.2, 0.75, 1.25, 0.67, 0.6, 0.5),
    },
}
MAP_TYPE_PRIORITY = (
    ("Shop", ("Shop.png",)),
    ("Battle", ("Battle.png",)),
    ("Elite", ("Elite.png",)),
    ("Ainz_Boss", ("Ainz_Boss.png",)),
    ("Escanor_Boss", ("Escanor_Boss.png",)),
)
MAP_TYPE_CLEARS = {map_type: 0 for map_type, _ in MAP_TYPE_PRIORITY}
PLAYABLE_MAP_TYPES = {"Battle", "Elite", "Ainz_Boss", "Escanor_Boss"}
BOSS_MAP_TYPES = {"Ainz_Boss", "Escanor_Boss"}

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

def on_press(key):
    global treasure_continue_requested

    try:
        if hasattr(key, "char") and key.char and key.char.lower() == "k":
            gh.kill()
        if hasattr(key, "char") and key.char == "[":
            treasure_continue_requested = True
    except Exception:
        pass

listener = pynput_keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()


def tap_pg(key, hold=0.08, post_delay=0.05):
    pyautogui.keyDown(key)
    time.sleep(hold)
    pyautogui.keyUp(key)
    time.sleep(post_delay)
    time.sleep(0.25)

def open_settings():
    gh.click(*SETTINGS_BUTTON, delay=0.2)
    time.sleep(0.5)
    return True


def close_settings():
    gh.click(*SETTINGS_CLOSE, delay=0.2)
    time.sleep(0.5)
    return False


def enable_auto_start(in_settings=False, close=False):
    print("Enabling Auto Start")

    if not in_settings:
        in_settings = open_settings()

    if pixel_matches_at(*AUTO_START_CHECK, (33, 15, 24), tol=20, sample_half=0):
        gh.click(*AUTO_START_CHECK, delay=0.2)
        time.sleep(1)
        print("Enabled.")
    else:
        print("Already enabled.")

    if close:
        return close_settings()

    return in_settings


def map_clear_counts_text():
    return ", ".join(
        f"{map_type}: {MAP_TYPE_CLEARS[map_type]}" for map_type, _ in MAP_TYPE_PRIORITY
    )


def send_floor_completion_webhook(session_start: datetime, floors_completed: int, floor_type: str):
    if not WEBHOOKS_ENABLED:
        return False

    runtime = str(datetime.now() - session_start).split(".")[0]
    screenshot = gh._roblox_window_screenshot_for_webhook()
    return webhook.send_webhook(
        run_time=runtime,
        num_runs=floors_completed,
        num_runs_label="Floors completed",
        task_name="Odyssey",
        img=screenshot,
        extra_fields=[
            {"name": "Last matched floor type", "value": floor_type, "inline": True},
            {"name": "Map type clears", "value": map_clear_counts_text(), "inline": False},
        ],
    )


def treasure_ping_text():
    if TREASURE_PING_EVERYONE:
        return "@everyone Treasure room found in Odyssey. Press `[` after handling it."

    if TREASURE_PING_USER_ID:
        return f"<@{TREASURE_PING_USER_ID}> Treasure room found in Odyssey. Press `[` after handling it."

    return "Treasure room found in Odyssey. Press `[` after handling it."


def send_treasure_webhook(session_start: datetime, runs: int):
    runtime = str(datetime.now() - session_start).split(".")[0]
    screenshot = gh._roblox_window_screenshot_for_webhook()
    webhook.send_webhook(
        run_time=runtime,
        num_runs=runs,
        num_runs_label="Floors completed",
        task_name="Odyssey Treasure",
        img=screenshot,
        alert_text=treasure_ping_text(),
        extra_fields=[
            {"name": "Last matched floor type", "value": last_match_type or "None", "inline": True},
            {"name": "Map type clears", "value": map_clear_counts_text(), "inline": False},
        ],
    )


def position_roblox():
    gh.focus_roblox()
    target_left, target_top = 200, 100
    target_width, target_height = 1320, 800

    try:
        window = wt.get_window("Roblox")
        if window is None:
            print("[Window] Roblox window not found; could not verify/position window.")
            return False

        left = int(getattr(window, "left", -1))
        top = int(getattr(window, "top", -1))
        width = int(getattr(window, "width", -1))
        height = int(getattr(window, "height", -1))

        if left == target_left and top == target_top and width == target_width and height == target_height:
            return True

        wt.move_window(window, target_left, target_top)
        wt.resize_window(window, target_width, target_height)
        time.sleep(0.2)

        check_window = wt.get_window("Roblox") or window
        new_left = int(getattr(check_window, "left", -1))
        new_top = int(getattr(check_window, "top", -1))
        new_width = int(getattr(check_window, "width", -1))
        new_height = int(getattr(check_window, "height", -1))

        if new_left == target_left and new_top == target_top and new_width == target_width and new_height == target_height:
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


def check_settings():
    print("Checking settings.")
    in_settings = enable_auto_start(close=True)
    # enable_auto_replay(in_settings=in_settings, close=True)


def click_vote_start_if_visible():
    if bt.does_exist(odyssey_image("OdysseyStart.png"), confidence=0.7, grayscale=False, region=START_REGION):
        print("Start screen detected; clicking Vote Start.")
        gh.click(*VOTE_START_POS, delay=0.2)
        time.sleep(0.5)
        return True

    return False


def auto_play_enabled():
    green_1 = pixel_matches_at(1484, 695, (113, 181, 55), tol=30)
    green_2 = pixel_matches_at(1484, 695, (90, 142, 41), tol=30)
    return green_1 or green_2


def ensure_auto_play_enabled():
    tries = 0
    while not auto_play_enabled():
        gh.click(AUTO_PLAY)
        tries += 1
        time.sleep(0.4)

        if tries >= 3 and not auto_play_enabled():
            print("Auto Play did not enable after 3 tries; clicking Vote Start again.")
            gh.click(*VOTE_START_POS, delay=0.2)
            time.sleep(0.5)
            tries = 0


def map_selection_open():
    return pixel_matches_at(*MAPS, MAPS_COLOUR, tol=10, sample_half=0)


def select_floor_visible():
    seen_rgb = pixel_color_at(*SELECT_FLOOR, sample_half=2)
    # print(f"SELECT_FLOOR RGB at {SELECT_FLOOR}: {seen_rgb}")
    if seen_rgb is None:
        return False

    return pixel_matches_at(*SELECT_FLOOR, SELECT_FLOOR_COLOUR, tol=10, sample_half=2)


def handle_shop_floor():
    print("Shop floor opened; waiting for shop confirm.")
    for _ in range(60):
        if pixel_matches_at(*SHOP_CONFIRM, SHOP_CONFIRM_COLOUR, tol=5, sample_half=0):
            break
        time.sleep(0.5)
    else:
        print("Shop confirm was not found; continuing.")
        return

    while pixel_matches_at(*SHOP_CONFIRM, SHOP_CONFIRM_COLOUR, tol=5, sample_half=0):
        print("Clicking shop confirm.")
        gh.click(*SHOP_CONFIRM, delay=0.1)
        time.sleep(0.5)


def click_select_floor_until_maps_close():
    while pixel_matches_at(*MAPS, MAPS_COLOUR, tol=10, sample_half=0):
        if select_floor_visible():
            # print("Clicking Select Floor.")
            gh.click(*SELECT_FLOOR, delay=0.1)
        time.sleep(0.5)


def handle_elite_skip_after_selection():
    print(f"Elite floor selected; waiting {ELITE_SKIP_INITIAL_DELAY_SECONDS}s before looking for Skip.")
    time.sleep(ELITE_SKIP_INITIAL_DELAY_SECONDS)

    print("Looking for Elite skip button.")
    while True:
        if gh.click_image_center(
            odyssey_image("Skip.png"),
            confidence=SKIP_IMAGE_CONFIDENCE,
            grayscale=False,
            region=SKIP_REGION,
            delay=0.1,
            retries=1,
        ):
            print("Clicked Elite skip button.")
            time.sleep(0.5)
            return

        time.sleep(0.5)


def handle_fast_boss_floor():
    if not FAST_BOSS:
        return

    print("Fast boss enabled; waiting for wave 5.")
    while not map_selection_open():
        wave = avM.get_wave(region=WAVE_REGION)
        if wave == 5:
            print("Wave 5 detected; waiting 8 seconds before applying fast boss action.")
            time.sleep(8)
            break
        time.sleep(1)

    while not map_selection_open():
        tap_pg("2")
        gh.click(*FAST_BOSS_APPLY_POSITION, delay=0.1)
        time.sleep(1)


def handle_battle_treasure_before_auto_play(session_start, runs):
    global treasure_continue_requested

    if last_match_type != "Battle":
        return False

    if not bt.does_exist(
        odyssey_image("Treasure.png"),
        confidence=TREASURE_IMAGE_CONFIDENCE,
        grayscale=False,
    ):
        return False

    print("Treasure room found after Battle; sending webhook and waiting for '['.")
    treasure_continue_requested = False

    try:
        send_treasure_webhook(session_start=session_start, runs=runs)
        print("[Webhook] Sent treasure alert.")
    except Exception as e:
        print(f"[Webhook] Failed to send treasure alert: {e}")

    while not treasure_continue_requested:
        time.sleep(0.2)

    treasure_continue_requested = False
    print("Continuing Odyssey after treasure room.")
    return True


def odyssey_image(filename):
    return f"{IMAGE_DIRECTORY}/{filename}"


def print_map_clear_stats():
    print(f"Last matched floor type: {last_match_type or 'None'}")
    clear_counts = ", ".join(
        f"{map_type}: {MAP_TYPE_CLEARS[map_type]}" for map_type, _ in MAP_TYPE_PRIORITY
    )
    print(f"Map type clears: {clear_counts}")


def complete_pending_floor_if_map_open(runs, session_start):
    global pending_floor_type

    if pending_floor_type is None or not map_selection_open():
        return runs

    completed_floor_type = pending_floor_type
    runs += 1
    MAP_TYPE_CLEARS[completed_floor_type] += 1
    print(f"Completed {completed_floor_type} floor.")
    pending_floor_type = None
    print_map_clear_stats()

    try:
        send_floor_completion_webhook(
            session_start=session_start,
            floors_completed=runs,
            floor_type=completed_floor_type,
        )
        print("[Webhook] Sent floor completion update.")
    except Exception as e:
        print(f"[Webhook] Failed to send floor completion update: {e}")

    return runs


def _boxes_overlap(box_a, box_b):
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    overlap_left = max(ax, bx)
    overlap_top = max(ay, by)
    overlap_right = min(ax + aw, bx + bw)
    overlap_bottom = min(ay + ah, by + bh)
    return overlap_left < overlap_right and overlap_top < overlap_bottom


def find_image_matches(image_directory, confidence=0.8, grayscale=False, region=None, scales=None):
    img_path = bt._resource_path(image_directory)
    template_flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    template = cv2.imread(img_path, template_flag)
    if template is None:
        return []

    if region is None:
        sw, sh = pyautogui.size()
        region = (0, 0, sw, sh)

    haystack_bgr = bt._grab_region(region)
    if haystack_bgr is None or haystack_bgr.size == 0:
        return []

    haystack = cv2.cvtColor(haystack_bgr, cv2.COLOR_BGR2GRAY) if grayscale else haystack_bgr
    candidate_scales = list(scales or (1.0,))
    scale = bt._get_backing_scale()
    if scale != 1.0 and (1.0 / scale) not in candidate_scales:
        candidate_scales.append(1.0 / scale)

    candidates = []
    seen_sizes = set()
    th, tw = template.shape[:2]
    for candidate_scale in candidate_scales:
        scaled_width = max(1, int(tw * candidate_scale))
        scaled_height = max(1, int(th * candidate_scale))
        if (scaled_width, scaled_height) in seen_sizes:
            continue

        seen_sizes.add((scaled_width, scaled_height))
        if candidate_scale == 1.0:
            candidates.append(template)
            continue

        th, tw = template.shape[:2]
        candidates.append(
            cv2.resize(
                template,
                (scaled_width, scaled_height),
                interpolation=cv2.INTER_AREA,
            )
        )

    rx, ry, rw, rh = region
    haystack_h, haystack_w = haystack.shape[:2]
    scale_x = haystack_w / max(1, rw)
    scale_y = haystack_h / max(1, rh)
    matches = []

    for candidate in candidates:
        th, tw = candidate.shape[:2]
        if haystack.shape[0] < th or haystack.shape[1] < tw:
            continue

        result = cv2.matchTemplate(haystack, candidate, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(result >= confidence)
        scored_points = sorted(
            ((float(result[y, x]), int(x), int(y)) for y, x in zip(ys, xs)),
            reverse=True,
        )

        for score, x, y in scored_points:
            left = int(round(rx + (x / scale_x)))
            top = int(round(ry + (y / scale_y)))
            width = int(round(tw / scale_x))
            height = int(round(th / scale_y))
            box = (left, top, width, height)

            if any(_boxes_overlap(box, existing_box) for existing_box, _ in matches):
                continue

            matches.append((box, score))

    return [box for box, _ in sorted(matches, key=lambda match: (-match[0][1], match[0][0]))]


def best_image_match_score(image_directory, grayscale=False, region=None, scales=None):
    img_path = bt._resource_path(image_directory)
    template_flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    template = cv2.imread(img_path, template_flag)
    if template is None:
        return None

    if region is None:
        sw, sh = pyautogui.size()
        region = (0, 0, sw, sh)

    haystack_bgr = bt._grab_region(region)
    if haystack_bgr is None or haystack_bgr.size == 0:
        return None

    haystack = cv2.cvtColor(haystack_bgr, cv2.COLOR_BGR2GRAY) if grayscale else haystack_bgr
    candidate_scales = list(scales or (1.0,))
    scale = bt._get_backing_scale()
    if scale != 1.0 and (1.0 / scale) not in candidate_scales:
        candidate_scales.append(1.0 / scale)

    best_score = None
    best_scale = None
    template_h, template_w = template.shape[:2]
    for candidate_scale in candidate_scales:
        scaled_width = max(1, int(template_w * candidate_scale))
        scaled_height = max(1, int(template_h * candidate_scale))
        candidate = template if candidate_scale == 1.0 else cv2.resize(
            template,
            (scaled_width, scaled_height),
            interpolation=cv2.INTER_AREA,
        )

        candidate_h, candidate_w = candidate.shape[:2]
        if haystack.shape[0] < candidate_h or haystack.shape[1] < candidate_w:
            continue

        result = cv2.matchTemplate(haystack, candidate, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if best_score is None or max_val > best_score:
            best_score = float(max_val)
            best_scale = candidate_scale

    if best_score is None:
        return None

    return best_score, best_scale


def is_match_bright_enough(box, min_brightness=MIN_AVAILABLE_MAP_BRIGHTNESS):
    left, top, width, height = box
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    img = np.array(screenshot)
    if img.size == 0:
        return False

    brightness = (
        0.299 * img[:, :, 0]
        + 0.587 * img[:, :, 1]
        + 0.114 * img[:, :, 2]
    ).mean()

    return brightness >= min_brightness


def select_next_floor():
    for map_type, image_names in MAP_TYPE_PRIORITY:
        match_settings = MAP_TYPE_MATCH_SETTINGS.get(map_type, {})
        confidence = match_settings.get("confidence", MAP_IMAGE_CONFIDENCE)
        grayscale = match_settings.get("grayscale", False)
        scales = match_settings.get("scales")
        map_matches = []
        for image_name in image_names:
            image_path = bt._resource_path(odyssey_image(image_name))
            if not os.path.exists(image_path):
                continue

            map_matches.extend(
                find_image_matches(
                    odyssey_image(image_name),
                    confidence=confidence,
                    grayscale=grayscale,
                    region=MAPS_REGION,
                    scales=scales,
                )
            )

        if not map_matches:
            if map_type in MAP_TYPE_MATCH_SETTINGS:
                for image_name in image_names:
                    best = best_image_match_score(
                        odyssey_image(image_name),
                        grayscale=grayscale,
                        region=MAPS_REGION,
                        scales=scales,
                    )
                    if best is not None:
                        score, scale = best
                        print(
                            f"No {map_type} match above {confidence}; "
                            f"best {image_name} score={score:.3f} scale={scale}."
                        )
            continue

        print(f"Found {len(map_matches)} {map_type} floor match(es).")
        for left, top, width, height in map_matches:
            box = (left, top, width, height)
            if not is_match_bright_enough(box):
                # print(f"Skipping dim completed {map_type} floor.")
                continue

            cx = int(left + width // 2)
            cy = int(top + height // 2)
            # print(f"Trying {map_type} floor at ({cx}, {cy}).")
            gh.click(cx, cy, delay=0.1)
            time.sleep(0.35)

            if select_floor_visible():
                print(f"Selected {map_type} floor.")
                return map_type

        print(f"No selectable {map_type} floor found; checking next priority.")

    return None


def odyssey():
    global first_match, last_match_type, pending_floor_type

    print("Starting Odyssey Macro.")
    print("Press K to stop.")
    session_start = datetime.now()
    time.sleep(0.5)
    position_roblox()
    runs = 0
    while True:
        print(f"Floors completed: {runs}")
        print_map_clear_stats()
        time.sleep(0.5)

        map_already_open = map_selection_open()
        if map_already_open:
            runs = complete_pending_floor_if_map_open(runs, session_start)
            map_already_open = True

        if first_match and not map_already_open:
            click_vote_start_if_visible()
        
        treasure_handled = False
        if not map_already_open:
            treasure_handled = handle_battle_treasure_before_auto_play(session_start=session_start, runs=runs)

        if map_already_open:
            print("Map selection screen already open.")
        elif treasure_handled:
            print("Treasure handled; skipping Auto Play check because map should be open.")
        elif not first_match:
            pass
        else:
            ensure_auto_play_enabled()
        
        while not map_selection_open():
            time.sleep(1)
        runs = complete_pending_floor_if_map_open(runs, session_start)
        print("Map open! Selecting Next Floor.")
        
        selected_map_type = None
        while not select_floor_visible():
            selected_map_type = select_next_floor()
            if selected_map_type is None:
                print("No matching Odyssey floor found; retrying.")
                time.sleep(1)
                
        if selected_map_type is not None:
            click_select_floor_until_maps_close()
            if first_match and selected_map_type in PLAYABLE_MAP_TYPES:
                click_vote_start_if_visible()
                print(f"First playable floor selected ({selected_map_type}); checking settings.")
                check_settings()
                ensure_auto_play_enabled()
                first_match = False

            if selected_map_type == "Shop":
                handle_shop_floor()
            elif selected_map_type == "Elite":
                handle_elite_skip_after_selection()
            elif selected_map_type in BOSS_MAP_TYPES:
                handle_fast_boss_floor()

            last_match_type = selected_map_type
            pending_floor_type = selected_map_type
            print_map_clear_stats()


odyssey()
