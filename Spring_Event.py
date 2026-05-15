import time
from datetime import datetime

import pyautogui
import webhook
from pynput import keyboard as pynput_keyboard

from Tools import botTools as bt
from Tools import avMethods as avM
from Tools import winTools as wt
from Tools import gameHelpers as gh
from Tools.screenHelpers import pixel_matches_at

# ================ LOADOUT COMPOSITION ================ #
# Treasury, Treasury, Make it Rain, Setup
# ================================================== #
WEBHOOK_EVERY_N_RUNS = 60  # Send a webhook every N runs (1 = every run)
VC_CHAT = True  # Enable if you have VC in roblox (check in the discord server if you're confused)

REWARDS_PER_WIN = 5400
VOTE_START_POS = (840, 228)

# Spring
# COUNTDOWN = (1137, 153)
COUNTDOWN = (1128, 150)
CONFIRM_WALL = (1075, 284)
SKIP_WAVE = (634, 357)
CLOSE = (1195,159)

SETTINGS_BUTTON = (220, 821)
SETTINGS_CLOSE = (1325, 226)
AUTO_START_CHECK = (1280, 567)
AUTO_REPLAY_CHECK = (894, 567)
ALERT_REGION = (756, 400, 160, 64)
WAVE_REGION = (590, 158, 55, 24)
DEBUG_WAVE = False

AUTO_PLAY = (1357, 601)

failed_runs = 0
failed_matches = 0
first_match = True

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

def on_press(key):
    try:
        if hasattr(key, "char") and key.char and key.char.lower() == "k":
            gh.kill()
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


def wait_start(delay: int | None = None):
    i = 0
    if delay is None:
        delay = 1

    while i < 90:
        i += 1
        try:
            print("Looking for start screen.")

            if bt.does_exist("VoteStart.png", confidence=0.7, grayscale=False, region=(802, 211, 77, 37)):
                print("✅ Start screen detected")
                return True

        except Exception as e:
            print(f"e {e}")

        time.sleep(delay)


def quick_rts():  # Returns to spawn
    locations = [(232, 873), (1153, 503), (1217, 267)]
    for loc in locations:
        gh.click(loc[0], loc[1], delay=0.1)
        time.sleep(0.2)


def slow_rts():  # Returns to spawn
    locations = [(232, 873), (1153, 503), (1217, 267)]
    for loc in locations:
        gh.click(loc[0], loc[1], delay=1)
        time.sleep(0.2)


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


def enable_auto_replay(in_settings=False, close=False):
    print("Enabling Auto Replay")

    if not in_settings:
        in_settings = open_settings()

    if pixel_matches_at(*AUTO_REPLAY_CHECK, (33, 15, 24), tol=20, sample_half=0):
        gh.click(*AUTO_REPLAY_CHECK, delay=0.2)
        time.sleep(1)
        print("Enabled.")
    else:
        print("Already enabled.")

    if close:
        return close_settings()

    return in_settings


def send_run_webhook(session_start: datetime, wins: int, losses: int, alert_text: str | None = None):
    runtime = str(datetime.now() - session_start).split(".")[0]
    rewards = wins * REWARDS_PER_WIN
    screenshot = gh._roblox_window_screenshot_for_webhook()
    webhook.send_webhook(
        run_time=runtime,
        task_name="Spring Event",
        win=wins,
        lose=losses,
        rewards=rewards,
        img=screenshot,
        alert_text=alert_text,
    )


def maybe_send_run_webhook(session_start: datetime, wins: int, losses: int = 0):
    total_runs = wins + losses
    if WEBHOOK_EVERY_N_RUNS <= 0 or total_runs <= 0:
        return

    if total_runs % WEBHOOK_EVERY_N_RUNS != 0:
        return

    try:
        send_run_webhook(session_start=session_start, wins=wins, losses=losses)
        print(f"[Webhook] Sent run update after {total_runs} run(s).")
    except Exception as e:
        print(f"[Webhook] Failed to send run update: {e}")


def position_roblox():
    gh.focus_roblox()
    target_left, target_top = 200, 100
    target_width, target_height = 1243, 743

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
    in_settings = enable_auto_start()
    enable_auto_replay(in_settings=in_settings, close=True)


def alert_visible():
    return bt.does_exist("Alert.png", confidence=0.9, grayscale=False, region=ALERT_REGION)


def auto_play_enabled():
    green_1 = pixel_matches_at(1407, 602, (113, 181, 55), tol=30)
    green_2 = pixel_matches_at(1407, 602, (90, 142, 41), tol=30)
    return green_1 or green_2


def get_wave():
    return avM.get_wave(region=WAVE_REGION, debug=DEBUG_WAVE)


def restart_match_fast():
    """Clicks through the UI to restart a match."""
    alert_found = False
    
    while not get_wave() <= 0:
        gh.click(218, 817)
        time.sleep(0.2)
        gh.click(1249, 426)
        time.sleep(0.2)
        gh.click(744, 543)
        time.sleep(0.2)
        gh.click(816, 541)
        time.sleep(0.5)
        
        while alert_visible():
            gh.click(1325, 226)
            time.sleep(0.1)
        time.sleep(0.4)
        alert_found = True
    print("Restarted Successfully!")


def spring_event():
    print("Starting Spring Macro.")
    print("Press K to stop.")
    session_start = datetime.now()
    time.sleep(0.5)
    position_roblox()
    check_settings()
    print("Positioned.")
    runs = 0
    while True:
        print(f"No. Runs: {runs}")
        restart_match_fast()
        time.sleep(0.5)
        
        #Enable Auto play
        print("Enabling Auto play")
        while not auto_play_enabled():
            gh.click(AUTO_PLAY)
            time.sleep(0.4)
        gh.click(CONFIRM_WALL)
        
        while get_wave() <=0:
            time.sleep(1)
        
        print("Waiting for countdown")
        while not pixel_matches_at(*COUNTDOWN,(255,255,255),tol=20,sample_half=0) and get_wave() >= 1:
            time.sleep(0.1)
        time.sleep(3)
        
        while get_wave() <= 3:
            time.sleep(6)
        
        print("Waiting for countdown")
        while not pixel_matches_at(*COUNTDOWN,(255,255,255),tol=20,sample_half=0):
            time.sleep(0.1)
        # while not (get_wave() >= 4 and pixel_matches_at(*COUNTDOWN,(255,255,255),tol=20,sample_half=0)):
        #     time.sleep(0.1)
        
        for i in range(2):
            print(f"Skipping 5 waves: ({i})")
            gh.tap("e")
            time.sleep(0.2)
            gh.click(SKIP_WAVE)
            time.sleep(0.2)
            while pixel_matches_at(1195,159, (255,255,255),tol=20,sample_half=0):
                gh.click(CLOSE)
                time.sleep(0.1)
            time.sleep(0.5)
            while pixel_matches_at(1126,275, (75,165,95),tol=20,sample_half=0) or pixel_matches_at(1126,275, (93,203,116),tol=20,sample_half=0):
                gh.click(CONFIRM_WALL)
                time.sleep(0.1)
        
        while not get_wave() >= 15:
            time.sleep(0.3)
        
        while get_wave() < 20:  
            print("Skipping to 20")
            gh.tap("e")
            time.sleep(0.1)
            gh.click(SKIP_WAVE)
            time.sleep(0.1)
            while pixel_matches_at(1195,159, (255,255,255),tol=20,sample_half=0):
                gh.click(CLOSE)
        runs += 1
        maybe_send_run_webhook(session_start=session_start, wins=runs, losses=0)


spring_event()