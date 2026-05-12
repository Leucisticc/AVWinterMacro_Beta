import os
import sys
import time
import subprocess
import pyautogui
import cv2
import numpy as np
from datetime import datetime
from pynput import keyboard as pynput_keyboard
from threading import Thread

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import webhook
from Tools import botTools as bt
from Tools import gameHelpers as gh
from Tools import winTools as wt
from Tools import screenHelpers as sh

# The in-game macro has to be in slot 1. Only raids are supported atm

MODE = "UNIVERSAL"
STAGE = "" #"shinobi", "crimson" for sjw, or leave blank for bleach
ACT = "" #1, 2, 3, 4, 5, bossrush
MACRO_SLOT = "2" #1, 2, 3

WINS_BEFORE_LOBBY = 5
CLAIM_TIMEOUT_SECONDS = 6
LOBBY_TIMEOUT_SECONDS = 10
GLOBAL_TIMEOUT_SECONDS = 480
STUCK_VICTORY_SECONDS = 10
REWARD_NAME = "Tokens"
TOKENS_PER_QUEST_CYCLE = 120

REJOIN_LOBBY_WITH_PRIVATE_SERVER = True
ROBLOX_PLACE_ID = "133410800847665"
PRIVATE_SERVER_CODE = "45189178357720008295896832795827"

# Lobby / Match Flow
AREAS = (238, 585)
CREATE_MATCH = (302, 544)
SELECT = (927, 735)
START = (1110, 670)
START_MATCH = (799, 256)
REPLAY = (669, 676)

# Macro Controls
MACRO = (268, 880)
LOAD = (1205, 311)
LOAD2 = (1205, 479)
LOAD3 = (1205, 646)
PLAY_MACRO = (1127, 772)


# Settings / Lobby Return
SETTINGS = (218, 880)
LOBBY = (908, 539)


# Event Rewards
EVENTS = (1269, 539)
CLAIM_1 = (1035, 420)
CLAIM_2 = (1035, 496)
CLAIM_3 = (1035, 578)
CLOSE_EVENT = (696, 169)


# Portal / Items
ITEMS = (237, 523)
SEARCH_BAR = (587, 392)
PORTAL_NAME = " IV"
KEY = (448, 464)
USE_KEY = (561, 514)
START_PORTAL = (1071, 669)


# Stages
SHINOBI_STAGE = (465, 483)
CRIMSON_STAGE = (465, 556)
BLEACH_STAGE = (465, 415)


# Acts
ACT_1 = (652, 402)
ACT_2 = (652, 452)
ACT_3 = (652, 510)
ACT_4 = (652, 561)
ACT_5 = (652, 627)
BOSSRUSH = (652, 676)


# Gamemodes
LTM = (501, 481)
STORY = (623, 481)
CHALLENGES = (872, 481)
VIRTUAL = (985, 481)
RAIDS = (740, 481)
UNIVERSAL_TEAR = (1207,324)


# Image Detection Regions
AREAS_REGION = (212, 528, 52, 60)
SETTINGS_REGION = (200, 865, 40, 31)
ORB_REGION = (627, 383, 354, 360)
VICTORY_REGION = (472, 355, 271, 159)
CREATE_MATCH_REGION = (207, 516, 173, 60)
MACRO_REGION = (231, 855, 87, 39)
TEAR_REGION = (889, 203, 403, 438)
ONLY_LOBBY_REGION = (446, 638, 346, 87)
LOBBY_REGION = (535, 641, 177, 78)

if STAGE.upper() == "SHINOBI":
    CLICK_STAGE = SHINOBI_STAGE
    print("Stage selected: Shinobi Battlefield.")
elif STAGE.upper() == "CRIMSON":
    CLICK_STAGE = CRIMSON_STAGE
    print("Stage selected: Crimson Throne Chamber")
else:
    CLICK_STAGE = BLEACH_STAGE
    print("Stage selected: Top of Hueco Castle")
    
if ACT == "1":
    CLICK_ACT = ACT_1
elif ACT == "2":
    CLICK_ACT = ACT_2
elif ACT == "3":
    CLICK_ACT = ACT_3
elif ACT == "4":
    CLICK_ACT = ACT_4
elif ACT == "5":
    CLICK_ACT = ACT_5
elif ACT == "bossrush":
    CLICK_ACT = BOSSRUSH

print(f"Act selected: {ACT}")


if MODE.upper() == "LTM":
    GAMEMODE = LTM
    print("Gamemode selected: LTM")
elif MODE.upper() == "STORY":
    GAMEMODE = STORY
    print("Gamemode selected: Story")
elif MODE.upper() == "CHALLENGES":
    GAMEMODE = CHALLENGES
    print("Gamemode selected: Challenges")
elif MODE.upper() == "VIRTUAL":
    GAMEMODE = VIRTUAL
    print("Gamemode selected: Virtual")
elif MODE.upper() == "UNIVERSAL":
    GAMEMODE = UNIVERSAL_TEAR
    print("Gamemode selected: Universal Tear")
else:
    GAMEMODE = RAIDS
    print("Gamemode selected: Raids")

IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "utdx-images")

start_time = datetime.now()
num_runs = 0
wins = 0
losses = 0
lobby_returns = 0
claimed_rewards = 0
current_cycle_wins = 0
last_win_signal_at = time.monotonic()

def go_to_area():
    gh.click(AREAS)
    time.sleep(1)
    gh.click(GAMEMODE)
    time.sleep(2)

def go_to_lobby():
    if REJOIN_LOBBY_WITH_PRIVATE_SERVER:
        rejoin_private_server()
        return

    print("Returning to lobby.")
    gh.click(SETTINGS)
    time.sleep(0.5)
    gh.click(LOBBY)
    time.sleep(0.5)

def rejoin_private_server():
    if not ROBLOX_PLACE_ID or not PRIVATE_SERVER_CODE:
        print("ROBLOX_PLACE_ID or PRIVATE_SERVER_CODE is empty; cannot auto-rejoin.")
        return False

    join_url = f"roblox://placeId={ROBLOX_PLACE_ID}&linkCode={PRIVATE_SERVER_CODE}/"
    print("Rejoining private server.")
    try:
        subprocess.Popen(["open", join_url])
    except Exception as e:
        print(f"Could not open Roblox private server URL: {e}")
        return False

    time.sleep(10)
    gh.focus_roblox()
    gh.ensure_roblox_window_positioned()
    return True

def wait_for_lobby_with_rejoin(timeout_seconds=LOBBY_TIMEOUT_SECONDS):
    while True:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if check_global_timeout():
                return False

            if utdx_image_exists("Areas.png", confidence=0.7, grayscale=False, region=AREAS_REGION):
                print("Lobby Found!")
                return True

            print("Checking for lobby...")
            time.sleep(2)

        print(f"Lobby not found after about {timeout_seconds}s.")
        if not rejoin_private_server():
            print("Rejoin was not started. Retrying lobby check anyway.")

def wait_for_lobby(timeout_seconds=60):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if check_global_timeout():
            return False

        while utdx_image_exists("Settings.png", confidence=0.7, grayscale=False, region=SETTINGS_REGION):
            go_to_lobby()
        if utdx_image_exists("Areas.png", confidence=0.7, grayscale=False, region=AREAS_REGION):
            print("Lobby confirmed.")
            return True
        print("Waiting for lobby after return...")
        time.sleep(5)

    print(f"Timed out waiting for lobby after {timeout_seconds}s.")
    return False

def claim_event_rewards():
    global claimed_rewards

    print("Claiming event rewards.")
    gh.click(EVENTS)
    time.sleep(0.5)
    claimed = 0
    for claim in (CLAIM_1, CLAIM_2, CLAIM_3):
        print(f"Pressing claim button: {claim}")
        gh.click(claim)

        popup_deadline = time.monotonic() + CLAIM_TIMEOUT_SECONDS
        while time.monotonic() < popup_deadline:
            if utdx_image_exists("Orb.png", confidence=0.7, grayscale=False, region=ORB_REGION):
                claimed += 1
                print(f"Orb reward popup found. Claims logged: {claimed}/3")
                break
            time.sleep(0.5)
        else:
            print(f"Orb popup not found after {CLAIM_TIMEOUT_SECONDS}s: {claim}")
            continue

        dismiss_deadline = time.monotonic() + CLAIM_TIMEOUT_SECONDS
        while time.monotonic() < dismiss_deadline:
            if not utdx_image_exists("Orb.png", confidence=0.7, grayscale=False, region=ORB_REGION):
                print(f"Orb reward popup dismissed: {claim}")
                break

            gh.click(claim)
            time.sleep(0.5)
        else:
            print(f"Orb popup dismiss timed out after {CLAIM_TIMEOUT_SECONDS}s: {claim}")

    if claimed == 3:
        claimed_rewards += TOKENS_PER_QUEST_CYCLE
        print(f"Quest rewards claimed. +{TOKENS_PER_QUEST_CYCLE} {REWARD_NAME} | Total: {claimed_rewards:,}")
        reward_screenshot = gh._roblox_window_screenshot_for_webhook()
        send_rewards_claimed_webhook(screenshot=reward_screenshot)
    else:
        print(f"Quest reward cycle incomplete. Claims logged: {claimed}/3 | Total {REWARD_NAME}: {claimed_rewards:,}")

    gh.click(CLOSE_EVENT)
    time.sleep(0.5)

def load_macro():
    gh.click(MACRO)
    time.sleep(0.5)
    if MACRO_SLOT == "2":
        gh.click(LOAD2)
        print("Loaded slot 2")
    elif MACRO_SLOT == "3":
        gh.click(LOAD3)
        print("Loaded slot 3")
    else:
        gh.click(LOAD)
        print("Loaded slot 1")
    time.sleep(1)
    gh.click(PLAY_MACRO)
    time.sleep(1)
    gh.click(START_MATCH)
    print("Started match.")

def format_runtime():
    return str(datetime.now() - start_time).split(".")[0]

def total_rewards_collected():
    return claimed_rewards

def average_rewards_collected():
    if num_runs <= 0:
        return 0
    return total_rewards_collected() // num_runs

def mark_win_signal():
    global last_win_signal_at

    last_win_signal_at = time.monotonic()

def check_global_timeout():
    if time.monotonic() - last_win_signal_at < GLOBAL_TIMEOUT_SECONDS:
        return False

    handle_global_timeout()
    return True

def handle_global_timeout():
    global losses, num_runs, last_win_signal_at

    elapsed_seconds = int(time.monotonic() - last_win_signal_at)
    losses += 1
    num_runs += 1
    print(
        f"No win signal detected for {elapsed_seconds}s. "
        "Counting this as a failure and returning to lobby."
    )

    timeout_screenshot = gh._roblox_window_screenshot_for_webhook()
    send_global_timeout_webhook(elapsed_seconds=elapsed_seconds, screenshot=timeout_screenshot)
    go_to_lobby()
    last_win_signal_at = time.monotonic()

def send_win_webhook(screenshot=None):
    rewards = total_rewards_collected()
    average = average_rewards_collected()
    Thread(
        target=webhook.send_webhook,
        kwargs={
            "run_time": format_runtime(),
            "win": wins,
            "lose": losses,
            "rewards": rewards,
            "reward_name": REWARD_NAME,
            "average_rewards": average,
            "task_name": "UTDX",
            "img": screenshot,
            "alert_text": (
                f"UTDX win #{wins} | {REWARD_NAME}: {rewards:,} total "
                f"| Average: {average:,} per run"
            ),
        },
        daemon=True,
    ).start()

def send_global_timeout_webhook(elapsed_seconds, screenshot=None):
    rewards = total_rewards_collected()
    average = average_rewards_collected()
    elapsed_minutes = elapsed_seconds // 60
    Thread(
        target=webhook.send_webhook,
        kwargs={
            "run_time": format_runtime(),
            "win": wins,
            "lose": losses,
            "rewards": rewards,
            "reward_name": REWARD_NAME,
            "average_rewards": average,
            "task_name": "UTDX Timeout Failure",
            "img": screenshot,
            "alert_text": (
                f"@everyone UTDX timeout failure | No win signal for about {elapsed_minutes} minutes "
                f"| Losses: {losses}"
            ),
        },
        daemon=True,
    ).start()

def send_rewards_claimed_webhook(screenshot=None):
    rewards = total_rewards_collected()
    average = average_rewards_collected()
    Thread(
        target=webhook.send_webhook,
        kwargs={
            "run_time": format_runtime(),
            "win": wins,
            "lose": losses,
            "rewards": rewards,
            "reward_name": REWARD_NAME,
            "average_rewards": average,
            "task_name": "UTDX Rewards Claimed",
            "img": screenshot,
            "alert_text": (
                f"UTDX rewards claimed | +{TOKENS_PER_QUEST_CYCLE} {REWARD_NAME} "
                f"| Total: {rewards:,}"
            ),
        },
        daemon=True,
    ).start()
    
def _scaled_templates(template):
    candidates = [("original", template)]
    scale = sh._get_backing_scale()
    if scale != 1.0:
        th, tw = template.shape[:2]
        scaled = cv2.resize(
            template,
            (max(1, int(tw / scale)), max(1, int(th / scale))),
            interpolation=cv2.INTER_AREA,
        )
        candidates.append((f"{scale:g}x-down", scaled))
    return candidates

def utdx_image_exists(image_name, confidence, grayscale, region=None, debug=False):
    image_path = os.path.join(IMAGE_DIR, image_name)
    template_flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    template = cv2.imread(image_path, template_flag)
    if template is None:
        if debug:
            print(f"[image] missing: {image_path}")
        return False

    if region is None:
        sw, sh = pyautogui.size()
        region = (0, 0, sw, sh)

    haystack_bgr = bt._grab_region(region)
    if haystack_bgr is None or haystack_bgr.size == 0:
        if debug:
            print(f"[image] empty screenshot region: {region}")
        return False

    haystack = cv2.cvtColor(haystack_bgr, cv2.COLOR_BGR2GRAY) if grayscale else haystack_bgr
    best = (0.0, "none", template.shape[:2])

    for label, candidate in _scaled_templates(template):
        th, tw = candidate.shape[:2]
        if haystack.shape[0] < th or haystack.shape[1] < tw:
            continue

        result = cv2.matchTemplate(haystack, candidate, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if max_val > best[0]:
            best = (max_val, label, (th, tw))
        if max_val >= confidence:
            return True

    if debug:
        rh, rw = haystack.shape[:2]
        th, tw = best[2]
        print(f"[image] {image_name} best={best[0]:.3f}/{confidence:.3f} scale={best[1]} template={tw}x{th} region={rw}x{rh}")
    return False

def on_press(key):
    try:
        if key.char == 'k':
            print("Kill switch pressed. Exiting...")
            os._exit(0)
    except AttributeError:
        pass

listener = pynput_keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()
keyboard_controller = pynput_keyboard.Controller()

def write_text(text, interval=0.5):
    for char in text:
        keyboard_controller.press(char)
        keyboard_controller.release(char)
        time.sleep(interval)

def wait_for_wins_before_lobby(target_wins=WINS_BEFORE_LOBBY):
    global num_runs, wins, lobby_returns, current_cycle_wins

    victory_seen = False
    victory_seen_at = None
    print(f"Waiting for {target_wins} wins before returning to lobby.")
    print(f"Current cycle wins: {current_cycle_wins}/{target_wins}")

    while current_cycle_wins < target_wins:
        if check_global_timeout():
            return False

        victory_visible = utdx_image_exists("Victory.png", confidence=0.7, grayscale=False, region=VICTORY_REGION)

        if victory_visible and not victory_seen:
            victory_screenshot = gh._roblox_window_screenshot_for_webhook()
            current_cycle_wins += 1
            wins += 1
            num_runs += 1
            victory_seen = True
            victory_seen_at = time.monotonic()
            mark_win_signal()
            print(
                f"Victory detected. Cycle wins: {current_cycle_wins}/{target_wins} "
                f"| Total wins: {wins} | {REWARD_NAME}: {total_rewards_collected():,}"
            )
            send_win_webhook(screenshot=victory_screenshot)

        elif victory_visible and victory_seen:
            if victory_seen_at is not None and time.monotonic() - victory_seen_at >= STUCK_VICTORY_SECONDS:
                print(
                    f"Victory still visible after {STUCK_VICTORY_SECONDS}s. "
                    "Stage appears closed; rejoining private server and keeping current cycle progress."
                )
                if REJOIN_LOBBY_WITH_PRIVATE_SERVER:
                    rejoin_private_server()
                    wait_for_lobby_with_rejoin()
                else:
                    go_to_lobby()
                    wait_for_lobby()
                mark_win_signal()
                return False

        elif not victory_visible:
            victory_seen = False
            victory_seen_at = None

        time.sleep(1)
        if MODE.upper() == "PORTAL":
            gh.click(REPLAY)
        else:
            gh.click(START_MATCH)

    print(f"Reached {target_wins} wins. Returning to lobby.")

    lobby_returns += 1
    if lobby_returns >= 1:
        if REJOIN_LOBBY_WITH_PRIVATE_SERVER:
            rejoin_private_server()
            lobby_ready = wait_for_lobby_with_rejoin()
        else:
            lobby_ready = wait_for_lobby()

        if lobby_ready:
            claim_event_rewards()
            current_cycle_wins = 0

    return True

def main():
    global num_runs, wins, losses
    
    print("UTDX Macro Started. Start in lobby. Press 'k' to stop.")
    
    # Position Roblox window
    gh.ensure_roblox_window_positioned()
    gh.focus_roblox()
    
    
    while True:
        if not wait_for_lobby_with_rejoin():
            continue
        if check_global_timeout():
            continue
        
        found = False
        while not found: 
            if check_global_timeout():
                break
            
            if MODE.upper() == "PORTAL":
                print("Joining portal")
                gh.click(ITEMS)
                time.sleep(0.5)
                gh.click(SEARCH_BAR)
                time.sleep(0.5)
                write_text(PORTAL_NAME, 2)
                gh.click(KEY)
                time.sleep(0.5)
                gh.click(USE_KEY)
                time.sleep(0.5)
                gh.click(START_PORTAL)
                
            elif MODE.upper() == "UNIVERSAL":
                print("Joining Universal Tear")
                gh.tap("o",hold=3)
                print("Looking for Universal Tear.")
                while not utdx_image_exists("UniversalTear.png", confidence=0.7, grayscale=False, region=TEAR_REGION):
                    time.sleep(2)
                print("Found.")
                gh.click_image_center(os.path.join(IMAGE_DIR, "UniversalTear.png"),confidence=0.7,grayscale=False,region=TEAR_REGION)
                time.sleep(1)
                gh.tap("w",hold=5)
                print("Creating Match.")
                gh.click(CREATE_MATCH)
                time.sleep(1)
                gh.click(SELECT)
                time.sleep(1)
                gh.click(START)
                
            else:
                go_to_area()
                gh.tap("w",hold=5.3)
                gh.tap("a",hold=3)
                time.sleep(1)
                if utdx_image_exists("CreateMatch.png", confidence=0.7, grayscale=False, region=CREATE_MATCH_REGION):
                    print("Creating Match.")
                    found = True
                else:
                    go_to_area()
                gh.click(CREATE_MATCH)
                time.sleep(0.5)
                gh.click(CLICK_STAGE)
                time.sleep(0.5)
                gh.click(CLICK_ACT)
                time.sleep(0.5)
                gh.click(SELECT)
                time.sleep(0.5)
                gh.click(START)
            
            macro_wait_timed_out = False
            while not utdx_image_exists("Macro.png", confidence=0.7, grayscale=False, region=MACRO_REGION):
                if check_global_timeout():
                    macro_wait_timed_out = True
                    break
                time.sleep(1)
            if macro_wait_timed_out:
                break

            print("Found macro")
            load_macro()
            wait_for_wins_before_lobby()
        

if __name__ == "__main__":
    main()
