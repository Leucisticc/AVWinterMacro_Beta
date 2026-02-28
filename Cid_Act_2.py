import time
import pyautogui
import os
import webhook
from datetime import datetime
from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Controller
from Tools import botTools as bt
from Tools import winTools as wt
from Tools import avMethods as avM

USE_MOUNT = True
GEMS_PER_WIN = 150
VOTE_START_POS = (840,228)
CLOSE_POS = (602,380)
FOCUS_BOSS = (252,573)
ABILITY_POS = (650,450)
REPLAY_POS = (697,712)
REPLAY_IMG = "Replay.png"
USE_MOUSE_ABILITY_SPAM = True
ABILITY_CLICK_POSITIONS = [
    (615,770),(680,770),(750,770),(815,770),(885,770)
]

if USE_MOUNT:
    UNITS = {
        "aurin": {"name": "Aurin", "hotbar": (865, 835), "pos": (599, 461)},
        "erza": {"name": "Erza", "hotbar": (790, 835), "pos": (480, 576)},
        "skele": {"name": "Skele", "hotbar": (710, 835), "pos": (546, 626)},
        "sasuke": {"name": "Sasuke", "hotbar": (640, 835), "pos": (599, 574)},
        "nami": {"name": "Nami", "hotbar": (560, 835), "pos": (476, 523)},
    }
else:
    UNITS = {
        "aurin": {"name": "Aurin", "hotbar": (865, 835), "pos": (599, 461)},
        "erza": {"name": "Erza", "hotbar": (790, 835), "pos": (424, 553)},
        "skele": {"name": "Skele", "hotbar": (710, 835), "pos": (546, 626)},
        "sasuke": {"name": "Sasuke", "hotbar": (640, 835), "pos": (572, 571)},
        "nami": {"name": "Nami", "hotbar": (560, 835), "pos": (432, 527)},
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

listener = pynput_keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()



# AV Functions
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

# def spam_keys_for_duration(keys=("a", "s", "d", "f", "g"), duration=6.0, key_gap=0.004):
#     end_time = time.perf_counter() + duration
#     while time.perf_counter() < end_time:
#         for key in keys:
#             keyboard_controller.press(key)
#             keyboard_controller.release(key)
#             if key_gap > 0:
#                 time.sleep(key_gap)
#             if time.perf_counter() >= end_time:
#                 break


# def spam_clicks_for_duration(positions, duration=6.0, click_delay=0.05, step_delay=0.0):
#     if not positions:
#         return

#     end_time = time.perf_counter() + duration
#     while time.perf_counter() < end_time:
#         for pos in positions:
#             click(pos, delay=click_delay)
#             if step_delay > 0:
#                 time.sleep(step_delay)
#             if time.perf_counter() >= end_time:
#                 break

def chord(keys=("a", "s", "d", "f", "g"), hold=0.03):
    for k in keys:
        keyboard_controller.press(k)
    time.sleep(hold)
    for k in reversed(keys):
        keyboard_controller.release(k)


def spam_chord_for_duration(keys=("a", "s", "d", "f", "g"), duration=6.0, hold=0.02, gap=0.005):
    end_time = time.perf_counter() + duration
    while time.perf_counter() < end_time:
        chord(keys, hold=hold)
        if gap > 0:
            time.sleep(gap)



def place_unit(unit, click_delay=0.3, step_delay=0.1):
    click(unit["hotbar"], delay=click_delay)
    time.sleep(step_delay)
    click(unit["pos"], delay=click_delay)
    time.sleep(step_delay)
    click(CLOSE_POS, delay=click_delay)

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

    print("❌ Start screen NOT detected (timeout)")

def wait_end(delay: float = 0.5, timeout: float = 180.0):
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            if bt.does_exist(REPLAY_IMG, confidence=0.7, grayscale=False):
                print("✅ Replay button detected")
                return True
        except Exception as e:
            print(f"replay detect error: {e}")
        time.sleep(delay)
    print("❌ Replay button NOT detected (timeout)")
    return False


def _roblox_window_screenshot_for_webhook():
    try:
        roblox_window = wt.get_window("Roblox")
        if roblox_window is None:
            return None
        return wt.screen_shot_memory(roblox_window)
    except Exception as e:
        print(f"[Webhook] Roblox window screenshot failed: {e}")
        return None


def send_run_webhook(session_start: datetime, wins: int):
    runtime = str(datetime.now() - session_start).split(".")[0]
    rewards = wins * GEMS_PER_WIN
    screenshot = _roblox_window_screenshot_for_webhook()
    webhook.send_webhook(
        run_time=runtime,
        task_name="Cid Act 2",
        win=wins,
        lose=0,
        rewards=rewards,
        img=screenshot,
    )



def mini_click_test(cycles=2, pre_delay=3, click_delay=0.08, step_delay=0.05):
    print(f"Mini click test starts in {pre_delay}s...")
    time.sleep(pre_delay)

    for cycle in range(1, cycles + 1):
        print(f"Cycle {cycle}/{cycles}")
        for unit in UNITS.values():
            click(unit["pos"], delay=click_delay)
            print(f"Clicked {unit['name']} @ {unit['pos']}")
            time.sleep(step_delay)

    print("Mini click test complete.")

def cid_farm():
    print("Starting Cid Macro.")
    print("Press K to stop.")
    time.sleep(3)

    # Focus game first.
    click(599, 461, delay=0.3)
    time.sleep(0.1)
    
    avM.restart_match()
    session_start = datetime.now()
    total_runs = 0
    wins = 0
    while True:
        click(REPLAY_POS)
        time.sleep(0.2)
        click(REPLAY_POS)
        print(f"Total Runs: {total_runs}")
        wait_start()
        if USE_MOUNT:
            time.sleep(2)
            tap('v')
            click(VOTE_START_POS)
            time.sleep(0.5)
            place_unit(UNITS["aurin"])
            time.sleep(0.5)
            place_unit(UNITS["sasuke"])
            time.sleep(2.5)
            place_unit(UNITS["nami"])
            time.sleep(0.5)
            place_unit(UNITS["erza"])
            time.sleep(3)
            place_unit(UNITS["skele"])
            time.sleep(0.5)
            click(UNITS["sasuke"]["pos"], delay=0.3)
            time.sleep(0.3)
            tap('z')
            time.sleep(0.3)
            click(FOCUS_BOSS, delay=0.3)
            time.sleep(0.3)
            click(CLOSE_POS)
            time.sleep(0.5)
            click(UNITS["skele"]["pos"], delay=0.3)
            time.sleep(2)
            click(ABILITY_POS)
            time.sleep(0.8)
            spam_chord_for_duration(duration=8, hold=0.02, gap=0.03)
            click(CLOSE_POS)
            time.sleep(0.3)
            click(UNITS["erza"]["pos"], delay=0.3)
            time.sleep(0.3)
            click(ABILITY_POS)
            time.sleep(6)
            click(1026,696)
            time.sleep(0.2)
            click(1026,696)
            time.sleep(0.5)
            click(750,553)
            time.sleep(0.5)
            click(1137,292)
        else:
            click(VOTE_START_POS)
            time.sleep(0.5)
            place_unit(UNITS["aurin"])
            time.sleep(0.5)
            place_unit(UNITS["sasuke"])
            time.sleep(2.5)
            place_unit(UNITS["nami"])
            time.sleep(0.5)
            place_unit(UNITS["erza"])
            time.sleep(3)
            place_unit(UNITS["skele"])
            time.sleep(0.5)
            click(UNITS["sasuke"]["pos"], delay=0.3)
            time.sleep(0.3)
            tap('z')
            time.sleep(0.3)
            click(FOCUS_BOSS, delay=0.3)
            time.sleep(0.3)
            click(CLOSE_POS)
            time.sleep(0.5)
            click(UNITS["skele"]["pos"], delay=0.3)
            time.sleep(2)
            click(ABILITY_POS)
            time.sleep(0.8)
            spam_chord_for_duration(duration=8, hold=0.02, gap=0.03)
            click(CLOSE_POS)
            time.sleep(0.3)
            click(UNITS["erza"]["pos"], delay=0.3)
            time.sleep(0.3)
            click(ABILITY_POS)
            time.sleep(6)
            click(1026,696)
            time.sleep(0.2)
            click(1026,696)
            time.sleep(0.5)
            click(750,553)
            time.sleep(0.5)
            click(1137,292)
        
        time.sleep(5)
        if wait_end():
            wins += 1
            total_runs += 1
            send_run_webhook(session_start=session_start, wins=wins)
            print(f"Wins: {wins} | Runtime: {str(datetime.now() - session_start).split('.')[0]} | Rewards: {wins * GEMS_PER_WIN:,}")
        else:
            print("Replay not detected; skipping win stat update for this cycle.")
        
        # Loop again from wait_start() on next iteration.
        continue

cid_farm()
