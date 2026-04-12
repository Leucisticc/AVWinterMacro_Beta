import webhook
import time
import pyautogui
import sys
import os
import subprocess
import json
import cv2
import numpy as np
import mss

from Tools import botTools as bt
from Tools import winTools as wt
from Tools import avMethods as avM
from Tools.screenHelpers import _safe_screenshot, _seen_pixel_from_screenshot, _retina_to_screen_coords, _screen_region_to_screenshot_region, pixel_matches_at, _mss, _get_backing_scale
from Utility.detect_hotbar_images import detect_unit_in_slot
from Tools.gameHelpers import kill, focus_roblox, ensure_roblox_window_positioned, _roblox_window_screenshot_for_webhook, _osascript, quick_rts


from datetime import datetime
from threading import Thread, local
from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Controller
from pathlib import Path

class Cur_Settings: pass

global Settings
Settings = Cur_Settings()

Settings_Path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"Settings")
WE_Json = os.path.join(Settings_Path,"Winter_Event.json")
VERSION_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.json")

VERSION_N = "Unknown"

try:
    with open(VERSION_JSON, "r") as f:
        VERSION_N = json.load(f).get("version", VERSION_N)
except Exception as e:
    print(f"[Version] Failed to load version.json: {e}")

print(f"Version: {VERSION_N}")

#Caloric position 1: 821,475
CHECK_LOOTBOX = False # Leave false for faster runs
PLACEMENT_TIMEOUT_SECONDS = 60

ROBLOX_PLACE_ID = 16146832113

PRIVATE_SERVER_CODE = "39534321779207670527898821021810" # Not in settings so u dont accidently share ur ps lol

WEBHOOK_CHECKER = False #Set to True if you want to send a webhook every time you run it
USE_FAST_REGION_CAPTURE = True # Use mss for wt.screenshot_region monkey-patch

USE_KAGUYA = False # "its faster to lowkey not use kaguya lol" ~LoxerEx

USE_BUU = False #Best unit for highest curency gain

TAK_FINDER = False # turn off if it runs into a wall while trying to find tak

RUNS_BEFORE_REJOIN = 0 # 0 will make it so this doesnt happen, change it to what round u want it to restart

AINZ_SPELLS = False #Keep FALSE!

# To change discord pings in settings: @everyone, <@user_id>, <@&role_id>

SLOT_ONE = (499, 150, 122, 110)
REG_SPEED = (495, 789, 570, 866)
REG_TAK = (495, 789, 570, 866)
HOTBAR_REGION = (470, 771, 570, 118)
HOTBAR_SLOT_REGIONS = (
    (469, 782, 94, 89),
    (562, 780, 95, 90),
    (656, 776, 94, 95),
    (748, 780, 97, 91),
    (843, 780, 95, 93),
    (938, 777, 95, 91),
)
BUNNY_HB_DEBUG_REGION = HOTBAR_REGION  # Set to None to capture the full screen instead.

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0
keyboard_controller = Controller()
g_toggle = False
total_screenshot_count = 0
_screenshot_count_guard = local()
_screenshot_counter_installed = False


# Info_Path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Info.json")

#Settings JSON
def load_json_data():
    JSON_DATA = None
    if os.path.isfile(WE_Json):
        with open(WE_Json, 'r') as f:
            JSON_DATA = json.load(f)
    return JSON_DATA

def save_json_data(data):
    with open(WE_Json, 'w') as f:
        json.dump(data, f, indent=4)

def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default

def _sanitize_disconnect_interval(value, default=30.0):
    """
    Keep disconnect polling as a fixed positive number of seconds.
    Backward compatible with old [min, max] format by using the first value.
    """
    try:
        if isinstance(value, (list, tuple)) and len(value) >= 1:
            value = value[0]
        interval = float(value)
        if interval > 0:
            return interval
    except Exception:
        pass
    return default

def reset_runtime_stats():
    """
    Reset run counters at script startup so stats are session-only.
    """
    data = load_json_data() or {}
    data["num_runs"] = 0
    data["wins"] = 0
    data["losses"] = 0
    data["runtime"] = "0:00:00"
    save_json_data(data)

def _install_global_screenshot_counter():
    """
    Count every screenshot capture globally across pyautogui/pyscreeze.
    Uses a thread-local guard to avoid double counting nested calls.
    """
    global _screenshot_counter_installed
    if _screenshot_counter_installed:
        return

    original_pyautogui_screenshot = pyautogui.screenshot

    try:
        import pyscreeze
    except Exception:
        pyscreeze = None

    original_pyscreeze_screenshot = getattr(pyscreeze, "screenshot", None) if pyscreeze else None

    def _wrap_screenshot(fn):
        def _wrapped(*args, **kwargs):
            if getattr(_screenshot_count_guard, "active", False):
                return fn(*args, **kwargs)

            setattr(_screenshot_count_guard, "active", True)
            try:
                img = fn(*args, **kwargs)
                global total_screenshot_count
                total_screenshot_count += 1
                if Settings.PRINT_GLOBAL_SCREENSHOT_COUNT:
                    print(f"[Screenshot] Total captured: {total_screenshot_count}")
                return img
            finally:
                setattr(_screenshot_count_guard, "active", False)

        return _wrapped

    pyautogui.screenshot = _wrap_screenshot(original_pyautogui_screenshot)

    if pyscreeze is not None and callable(original_pyscreeze_screenshot):
        pyscreeze.screenshot = _wrap_screenshot(original_pyscreeze_screenshot)

    _screenshot_counter_installed = True


if os.path.exists(Settings_Path):
    if os.path.exists(WE_Json):
        data = load_json_data()
        for variable in data:
            value = data.get(variable)
            try:
                if variable == "Unit_Positions" or variable == "Unit_Placements_Left":
                    if type(value[0]) == dict:
                        setattr(Settings, variable, value[0])
                else:
                    setattr(Settings, variable, value)
            except Exception as e:
                print(e)
else:
    print("Failed to find settings file. Closing in 10 seconds")
    time.sleep(10)
    sys.exit()

if not hasattr(Settings, "ENABLE_WEBHOOKS"):
    Settings.ENABLE_WEBHOOKS = True
    data = load_json_data() or {}
    data["ENABLE_WEBHOOKS"] = True
    save_json_data(data)
else:
    Settings.ENABLE_WEBHOOKS = _to_bool(Settings.ENABLE_WEBHOOKS, default=True)

if not hasattr(Settings, "ENABLE_FAILURE_PING"):
    Settings.ENABLE_FAILURE_PING = True
    data = load_json_data() or {}
    data["ENABLE_FAILURE_PING"] = True
    save_json_data(data)
else:
    Settings.ENABLE_FAILURE_PING = _to_bool(Settings.ENABLE_FAILURE_PING, default=True)

if not hasattr(Settings, "ALERT_TARGET"):
    Settings.ALERT_TARGET = "@everyone"
    data = load_json_data() or {}
    data["ALERT_TARGET"] = Settings.ALERT_TARGET
    save_json_data(data)
else:
    Settings.ALERT_TARGET = str(Settings.ALERT_TARGET or "").strip() or "@everyone"

if not hasattr(Settings, "USE_FAST_IMAGE_DETECTION"):
    Settings.USE_FAST_IMAGE_DETECTION = True
    data = load_json_data() or {}
    data["USE_FAST_IMAGE_DETECTION"] = Settings.USE_FAST_IMAGE_DETECTION
    save_json_data(data)
else:
    Settings.USE_FAST_IMAGE_DETECTION = _to_bool(
        Settings.USE_FAST_IMAGE_DETECTION,
        default=False,
    )

if not hasattr(Settings, "ENABLE_DISCONNECT_CHECKER"):
    Settings.ENABLE_DISCONNECT_CHECKER = True
    data = load_json_data() or {}
    data["ENABLE_DISCONNECT_CHECKER"] = True
    save_json_data(data)
else:
    Settings.ENABLE_DISCONNECT_CHECKER = _to_bool(Settings.ENABLE_DISCONNECT_CHECKER, default=True)

if not hasattr(Settings, "DISCONNECT_CHECK_INTERVAL_SECONDS"):
    Settings.DISCONNECT_CHECK_INTERVAL_SECONDS = 30
    data = load_json_data() or {}
    data["DISCONNECT_CHECK_INTERVAL_SECONDS"] = 30
    save_json_data(data)

Settings.DISCONNECT_CHECK_INTERVAL_SECONDS = _sanitize_disconnect_interval(
    getattr(Settings, "DISCONNECT_CHECK_INTERVAL_SECONDS", 30)
)

if hasattr(Settings, "PRINT_DISCONNECT_SCREENSHOT_COUNT") and not hasattr(Settings, "PRINT_GLOBAL_SCREENSHOT_COUNT"):
    # Backward compatibility for older config key name.
    Settings.PRINT_GLOBAL_SCREENSHOT_COUNT = _to_bool(
        Settings.PRINT_DISCONNECT_SCREENSHOT_COUNT,
        default=False
    )
    data = load_json_data() or {}
    data["PRINT_GLOBAL_SCREENSHOT_COUNT"] = Settings.PRINT_GLOBAL_SCREENSHOT_COUNT
    data.pop("PRINT_DISCONNECT_SCREENSHOT_COUNT", None)
    save_json_data(data)

if not hasattr(Settings, "PRINT_GLOBAL_SCREENSHOT_COUNT"):
    Settings.PRINT_GLOBAL_SCREENSHOT_COUNT = False
    data = load_json_data() or {}
    data["PRINT_GLOBAL_SCREENSHOT_COUNT"] = False
    save_json_data(data)
else:
    Settings.PRINT_GLOBAL_SCREENSHOT_COUNT = _to_bool(
        Settings.PRINT_GLOBAL_SCREENSHOT_COUNT,
        default=False
    )

_install_global_screenshot_counter()

Settings.Units_Placeable.append("Doom")

start = datetime.now()
if not USE_KAGUYA:
    Settings.Units_Placeable.remove("Kag")

# Session-only stats: reset counters every time this script starts.
reset_runtime_stats()

def toggle_run_state():
    global g_toggle
    g_toggle = not g_toggle
    print(f"Run toggled: {'ON' if g_toggle else 'OFF'}")


def on_press(key):
    try:
        if hasattr(key, "char") and key.char:
            if key.char.lower() == Settings.STOP_START_HOTKEY.lower():
                toggle_run_state()
            elif key.char.lower() == "k":
                kill()
    except:
        pass


listener = pynput_keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()


# -------------------------
# Click Function (Mac Safe)
# -------------------------
def click(x, y, delay=None, right_click=False, dont_move=False):
    if delay is None:
        delay = 0.3

    if not dont_move:
        pyautogui.moveTo(x, y)

    time.sleep(delay)

    if right_click:
        pyautogui.rightClick()
    else:
        pyautogui.click()


# -------------------------
# Key Press Helpers
# -------------------------
def press(key):
    keyboard_controller.press(key)


def release(key):
    keyboard_controller.release(key)


def tap(key):
    keyboard_controller.press(key)
    keyboard_controller.release(key)

def write_text(text, interval=0.5):
    for char in text:
        keyboard_controller.press(char)
        keyboard_controller.release(char)
        time.sleep(interval)

# -------------------------
# Scroll Replacement
# -------------------------
def scroll(amount):
    pyautogui.scroll(amount)


def refresh_hotbar_hover(
    slot_regions: tuple[tuple[int, int, int, int], ...] = HOTBAR_SLOT_REGIONS,
    hover_delay: float = 0.025,
    restore_mouse: bool = False,
):
    """
    Sweep the mouse across every hotbar slot to force Roblox to refresh slot hover state.
    This helps when the slot visuals shrink until the cursor passes over them again.
    """
    original_pos = pyautogui.position() if restore_mouse else None

    for x, y, w, h in slot_regions:
        pyautogui.moveTo(x + (w // 2), y + (h // 2))
        time.sleep(hover_delay)

    if restore_mouse and original_pos is not None:
        pyautogui.moveTo(original_pos.x, original_pos.y)
        time.sleep(hover_delay)

# -------------------------
# Screenshot Capture and Pixel Detection (Mac Rendering Layer)
# -------------------------

_ORIGINAL_WT_SCREENSHOT_REGION = wt.screenshot_region


def _mss_screenshot_region(region: tuple[int, int, int, int], retries: int = 3, retry_delay: float = 0.08):
    """
    Toggleable replacement for wt.screenshot_region().
    Kept local to this script so it is easy to disable/remove.
    """
    last_error = None
    for _ in range(max(1, retries)):
        try:
            x, y, w, h = region
            monitor = {
                "left": int(x),
                "top": int(y),
                "width": max(1, int(w)),
                "height": max(1, int(h)),
            }
            if _mss is not None:
                shot = _mss.grab(monitor)
            else:
                with mss.mss() as tmp:
                    shot = tmp.grab(monitor)
            img = np.array(shot)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            last_error = e
            time.sleep(retry_delay)

    print(f"[mss_screenshot_region] Region {region} screenshot error: {last_error}")
    return None


if USE_FAST_REGION_CAPTURE:
    wt.screenshot_region = _mss_screenshot_region
    print("[Capture] Using mss for wt.screenshot_region")

def pixel_color_seen(x: int, y: int, sample_half: int = 1, screenshot=None):
    img = screenshot if screenshot is not None else _safe_screenshot()
    if img is None:
        return (0, 0, 0)
    return _seen_pixel_from_screenshot(img, x, y, sample_half=sample_half)

def setup_cam():
    focus_roblox()
    time.sleep(1)
    press('i')
    time.sleep(0.5)
    release('i')
    time.sleep(0.5)
    press('o')
    time.sleep(1)
    release('o')
    time.sleep(0.5)
    quick_rts()
    time.sleep(0.5)
    press('a')
    time.sleep(0.4)
    release('a')
    time.sleep(1)
    tap('v')
    time.sleep(1.5)
    press('w')
    time.sleep(1.5)
    release('w')
    press('a')
    time.sleep(1.1)
    release('a')
    time.sleep(1)
    click(566,587,delay=0.5,right_click=True)
    time.sleep(1.5)
    tap('v')
    time.sleep(0.5)
    tap('e')
    time.sleep(1)
    place_unit('Bunny',(700,700),close=False)
    time.sleep(1)
    clicks_look_down = [(398, 398), (649, 772), (745, 858)]
    for pt in clicks_look_down:
        click(pt[0], pt[1], delay=1)
        time.sleep(1 if pt == (649, 772) else 0.3)
    time.sleep(0.5)
    click(607, 383, delay =0.1)
    time.sleep(0.5)
    press('o'); time.sleep(1); release('o')
    quick_rts()

# -------------------------
# Safe Restart (Mac)
# -------------------------
def safe_restart():
    print("Restarting script...")
    args = list(sys.argv)

    if "--stopped" in args:
        args.remove("--stopped")

    if "--restart" in args:
        args.remove("--restart")

    subprocess.Popen([sys.executable] + args)
    os._exit(0)

def _show_disconnect_alert():
    """
    Best-effort macOS alert to makew disconnects obvious while the script auto-recovers.
    """
    title = "Winter Event Macro"
    body = "Disconnected detected. Rejoining private server."
    script = (
        f'display notification "{body}" with title "{title}" '
        'subtitle "Recovery started" sound name "Frog"'
    )
    _osascript(script)

    # Optional Discord ping for disconnect/rejoin events.
    if Settings.ENABLE_WEBHOOKS and Settings.ENABLE_FAILURE_PING:
        try:
            reconnect_img = _roblox_window_screenshot_for_webhook()
            runtime = f"{str((datetime.now() - start)).split('.')[0]}"
            Thread(
                target=webhook.send_webhook,
                kwargs={
                    "run_time": runtime,
                    "task_name": "Winter Event (Disconnected - Rejoining)",
                    "img": reconnect_img,
                    "enabled": Settings.ENABLE_WEBHOOKS,
                    "alert_text": f"{Settings.ALERT_TARGET} Disconnected detected, rejoining now.",
                },
                daemon=True,
            ).start()
        except Exception as e:
            print(f"[Webhook] Disconnect alert error: {e}")

def disconnect_checker():
    time.sleep(10)  # initial detect delay
    while True:
        if not Settings.ENABLE_DISCONNECT_CHECKER:
            time.sleep(5)
            continue

        disconnected = (
            bt.does_exist("Disconnected.png", confidence=0.9, grayscale=True, region=(512, 354, 450, 322))
            or bt.does_exist("Disconnect_Two.png", confidence=0.9, grayscale=True, region=(512, 354, 450, 322))
            or bt.does_exist("Disconnect_Three.png", confidence=0.9, grayscale=True, region=(512, 354, 450, 322))
        )

        if disconnected:
            print("[Disconnect] Found disconnected prompt")
            _show_disconnect_alert()
            try:
                args = list(sys.argv)
                if "--stopped" in args:
                    args.remove("--stopped")
                while "--restart" in args:
                    args.remove("--restart")

                sys.stdout.flush()
                subprocess.Popen([sys.executable, *args, "--restart"])
                os._exit(0)
            except Exception as e:
                print(f"[Disconnect] Restart launch failed: {e}")

            time.sleep(6)

        time.sleep(Settings.DISCONNECT_CHECK_INTERVAL_SECONDS)

def on_disconnect():
    """
    macOS reconnect routine:
    1) open Roblox private-server URL
    2) try to focus/position window
    3) navigate back into the run flow
    """
    if not PRIVATE_SERVER_CODE:
        print("[Disconnect] PRIVATE_SERVER_CODE is empty; cannot auto-rejoin.")
        return

    join_url = f"roblox://placeId={ROBLOX_PLACE_ID}&linkCode={PRIVATE_SERVER_CODE}/"
    try:
        subprocess.Popen(["open", join_url])
    except Exception as e:
        print(f"[Disconnect] Could not open Roblox URL: {e}")
        return

    time.sleep(10)
    focus_roblox()

    # Best effort window move/resize on macOS.
    try:
        window = None
        for _ in range(20):
            window = wt.get_window("Roblox")
            if window is not None:
                break
            time.sleep(0.5)

        if window is not None:
            wt.move_window(window, 200, 100)
            wt.resize_window(window, 1100, 800)
    except Exception as e:
        print(f"[Disconnect] Window resize/move error: {e}")

    while not bt.does_exist("AreaIcon.png", confidence=0.8, grayscale=False):
        if pixel_matches_at(1085, 321, (255, 255, 255), tol=5):
            click(1083, 321, delay=0.1)
        time.sleep(1)

    time.sleep(1)
    if pixel_matches_at(1085, 321, (255, 255, 255), tol=5):
        click(1083, 321, delay=0.1)

    click_image_center("AreaIcon.png", confidence=0.8, grayscale=False, offset=(0, 0))
    time.sleep(3)

    open_menu = False
    walked_to_menu = False
    spam_thread_started = False

    def spam_e():
        while not open_menu:
            tap('e')
            time.sleep(0.2)

    while not open_menu:
        click(995, 783, delay=0.1)
        time.sleep(1)

        if not walked_to_menu:
            press('s')
            time.sleep(4.8)
            release('s')

            walked_to_menu = True

        if not spam_thread_started:
            Thread(target=spam_e, daemon=True).start()
            spam_thread_started = True

        press('s')
        time.sleep(2)
        release('s')
            
        if pixel_matches_at(888, 269, (165, 232, 235), tol=30):
            open_menu = True

        if not open_menu:
            if pixel_matches_at(1085, 321, (255, 255, 255), tol=5):
                click(1083, 321, delay=0.1)
            click_image_center("AreaIcon.png", confidence=0.8, grayscale=False, offset=(0, 0))

        time.sleep(3)

    click(454, 703, delay=0.1)
    time.sleep(2)
    click(659, 509, delay=0.1)
    time.sleep(2)
    click(745, 560, delay=0.1)
    time.sleep(2)
    click(301, 676, delay=0.1)
    time.sleep(10)
    
    
    wait_start()
    time.sleep(1)
    click(405,160,delay=0.2)
    time.sleep(1)
    click(405,160,delay=0.2)
    time.sleep(1)
    click(835, 226, delay =0.1) # Start Match
    setup_cam()
    time.sleep(0.5)
    click(483, 536, delay=0.2)
    time.sleep(1)
    click(483, 464, delay=0.2)
    time.sleep(1)
    avM.restart_match()
    
# Wait for start screen
def wait_start(delay: int | None = None):
    i = 0
    if delay is None:
        delay = 1

    target = (99, 214, 63)
    print(f"Looking for start screen...")
    while i < 90:
        i += 1
        try:
            # seen = pixel_color_seen(816, 231, sample_half=2)  # 5x5 median
            # print(f"Looking for start screen: Seen = {seen}")

            if bt.does_exist("VoteStart.png", confidence=0.7, grayscale=False, region=(767, 189, 127,83)) or pixel_matches_at(816, 231, target, tol=35, sample_half=2): 
                print("✅ Start screen detected")
                return True

        except Exception as e:
            print(f"e {e}")

        time.sleep(delay)

    print("❌ Start screen NOT detected (timeout)")
    return False


#Game mechanics

def directions(area: str, unit: str | None=None): # This is for all the pathing
    '''
    This is the pathing for all the areas: 1 [rabbit, nami, hero (trash gamer)], 2 [speed, tak], 3: Mystery box, 4: Upgrader, 5: Monarch upgradern
    '''
    # All this does is set up camera whenever it's the first time running, disable if needed
        
    #Contains rabbit, nami, and hero
    if Settings.USE_NIMBUS:
        if area == '1':  
            #DIR_PATHING
            # Pathing
            if not Settings.CTM_P1_P2:
                press('a')
                time.sleep(0.4)
                release('a')
                time.sleep(1)
                tap('v')
                time.sleep(1.5)
                press('w')
                time.sleep(1.5)
                release('w')
                press('a')
                time.sleep(1.1)
                release('a')
            else:
                tap('v')
                time.sleep(1)
                for p in Settings.CTM_AREA_1:
                    click(p[0],p[1],delay =0.1,right_click=True)
                    time.sleep(1.9)
                time.sleep(1.5)
            if unit == 'rabbit':
                #[(558, 334)
                click(Settings.CTM_AREA_1_UNITS[0][0], Settings.CTM_AREA_1_UNITS[0][1], delay =0.1,right_click=True) # Click to move
                time.sleep(1)
            if unit == "nami":
                click(Settings.CTM_AREA_1_UNITS[1][0], Settings.CTM_AREA_1_UNITS[1][1], delay =0.1,right_click=True)
                time.sleep(1)
            if unit == "hero":
                click(Settings.CTM_AREA_1_UNITS[2][0], Settings.CTM_AREA_1_UNITS[2][1], delay =0.1,right_click=True)
                time.sleep(1)
            tap('v') 
            time.sleep(2)
        # Speed wagon + Tak
        if area == '2':
            if not Settings.CTM_P1_P2:
                press('a')
                time.sleep(0.4)
                release('a')
                time.sleep(1)
                tap('v')
                time.sleep(1.5)
                press('w')
                time.sleep(1.5)
                release('w')
            else:
                tap('v')
                time.sleep(1.3)
                for p in Settings.CTM_AREA_2:
                    click(p[0],p[1],delay =0.1,right_click=True)
                    time.sleep(1.5)
                time.sleep(1.5)
            #(534, 706), (535, 546)
            if unit == 'speed':
                click(Settings.CTM_AREA_2_UNITS[0][0], Settings.CTM_AREA_2_UNITS[0][1], delay =0.1,right_click=True)
                time.sleep(1)
            if unit == 'tak':
                click(Settings.CTM_AREA_2_UNITS[1][0], Settings.CTM_AREA_2_UNITS[1][1], delay =0.1,right_click=True)
                time.sleep(1)
            tap('v')
            time.sleep(2)
        # Gambling time
        if area == '3': 
            tap('v')
            time.sleep(1)
            press('a')
            time.sleep(Settings.AREA_3_DELAYS[0])
            release('a')

            press('s')
            time.sleep(Settings.AREA_3_DELAYS[1])
            release('s')

            press('d')
            time.sleep(Settings.AREA_3_DELAYS[2])
            release('d')

            press('s')
            time.sleep(Settings.AREA_3_DELAYS[3])
            release('s')
            tap('v')
            time.sleep(2)
            e_delay = 0.7
            timeout = 2.5/e_delay
            at_location = False
            if CHECK_LOOTBOX == True:
                while not at_location:
                    tap('e')
                    time.sleep(e_delay)
                    if bt.does_exist("Winter/LootBox.png",confidence=0.7,grayscale=True,region=(536, 397, 433, 383)):
                        at_location = True
                    if  bt.does_exist("Winter/Full_Bar.png",confidence=0.7,grayscale=True,region=(536, 397, 433, 383)):
                        at_location = True
                    if  bt.does_exist("Winter/NO_YEN.png",confidence=0.7,grayscale=True,region=(536, 397, 433, 383)):
                        at_location = True
                    if timeout < 0:
                        quick_rts()
                        tap('v')
                        time.sleep(1)
                        press('a')
                        time.sleep(Settings.AREA_3_DELAYS[0])
                        release('a')

                        press('s')
                        time.sleep(Settings.AREA_3_DELAYS[1])
                        release('s')

                        press('d')
                        time.sleep(Settings.AREA_3_DELAYS[2])
                        release('d')

                        press('s')
                        time.sleep(Settings.AREA_3_DELAYS[3])
                        release('s')
                        tap('v')
                        time.sleep(2)
                        timeout = 3/e_delay
                    timeout-=1
            # print("At lootbox")

        if area == '4': #  Upgrader location
            tap('v')
            time.sleep(1)
            press('a')
            time.sleep(Settings.AREA_4_DELAYS[0])
            release('a')

            press('s')
            time.sleep(Settings.AREA_4_DELAYS[1])
            release('s')
            tap('v')
            time.sleep(2)
            
        if area == '5': # This is where it buys monarch
            tap('v')
            time.sleep(1)
            press('a')
            time.sleep(Settings.AREA_5_DELAYS[0])
            release('a')

            press('w')
            time.sleep(Settings.AREA_5_DELAYS[1])
            release('w')
            tap('v')
            time.sleep(2)
        
def upgrader(upgrade: str):
    """
    Buys the upgrades for the winter event: fortune, range, damage, speed, armor
    mac-friendly + Retina-safe pixel checks (screenshot-based)
    """

    def seen(x, y, rgb, tol=40, sample_half=2) -> bool:
        # wrapper so we can tune tol/sample_half in one place
        return pixel_matches_at(x, y, rgb, tol=tol, sample_half=sample_half)

    e_delay = 0.2
    timeout = 3 / e_delay

    tap('e')

    # Wait until the upgrade UI is open (white pixel check)
    while True:
        if seen(524, 324, (235, 235, 235), tol=30, sample_half=2):
            break

        if timeout < 0:
            quick_rts()
            directions('4')
            timeout = 3 / e_delay

        timeout -= 1
        tap('e')
        time.sleep(e_delay)

    click(607, 381, delay =0.1)
    time.sleep(0.5)

    # ---------- UI NAV OFF ----------
    if not Settings.USE_UI_NAV:

        if upgrade == 'fortune':
            pyautogui.moveTo(775, 500)  # ensure scroll is inside panel
            time.sleep(0.2)
            scroll(100)
            time.sleep(0.5)

            pos = (955, 475)
            while not seen(pos[0], pos[1], (24, 24, 24), tol=50, sample_half=2):
                if not g_toggle:
                    break
                click(pos[0], pos[1], delay =0.1)
                time.sleep(0.8)

            click(1112, 309, delay =0.1)
            time.sleep(0.5)


        elif upgrade == "damage":
            pyautogui.moveTo(775, 500)  # ensure scroll is inside panel
            time.sleep(0.2)

            for _ in range(6):
                scroll(-1)
                time.sleep(0.2)

            pos = (955, 635)
            while not seen(pos[0], pos[1], (24, 24, 24), tol=50, sample_half=2):
                if not g_toggle:
                    break
                click(pos[0], pos[1], delay =0.1)
                time.sleep(0.8)

            pyautogui.moveTo(775, 500)  # ensure scroll is inside panel
            time.sleep(0.5)
            scroll(100)
            time.sleep(0.5)
            click(1112, 309, delay =0.1)
            time.sleep(0.5)


        elif upgrade == 'range':
            pyautogui.moveTo(775, 500)  # ensure scroll is inside panel
            time.sleep(0.2)

            for _ in range(3):
                scroll(-1)
                time.sleep(0.2)


            pos = (955, 635)
            while not seen(pos[0], pos[1], (24, 24, 24), tol=50, sample_half=2):
                if not g_toggle:
                    break
                click(pos[0], pos[1], delay =0.1)
                time.sleep(0.8)

            pyautogui.moveTo(775, 500)  # ensure scroll is inside panel
            time.sleep(0.5)
            scroll(100)
            time.sleep(0.5)
            click(1112, 309, delay =0.1)
            time.sleep(0.5)


        elif upgrade == "speed":
            pyautogui.moveTo(775, 500)  # ensure scroll is inside panel
            time.sleep(0.2)

            pos = (955, 635)
            while not seen(pos[0], pos[1], (24, 24, 24), tol=50, sample_half=2):
                if not g_toggle:
                    break
                click(pos[0], pos[1], delay =0.1)
                time.sleep(0.8)

            pyautogui.moveTo(775, 500)  # ensure scroll is inside panel
            time.sleep(0.5)
            scroll(100)
            time.sleep(0.5)
            click(1112, 309, delay =0.1)
            time.sleep(0.5)

        elif upgrade == "armor":
            pyautogui.moveTo(775, 500)  # ensure scroll is inside panel
            time.sleep(0.2)

            
            for _ in range(9):
                scroll(-1)
                time.sleep(0.2)

            pos = (955, 635)
            while not seen(pos[0], pos[1], (24, 24, 24), tol=50, sample_half=2):
                if not g_toggle:
                    break
                click(pos[0], pos[1], delay =0.1)
                time.sleep(0.8)

            pyautogui.moveTo(775, 500)  # ensure scroll is inside panel
            time.sleep(0.5)
            scroll(100)
            time.sleep(0.5)
            click(1112, 309, delay =0.1)
            time.sleep(0.5)



    # ---------- UI NAV ON ----------
    else:
        # These are your UI navigation versions, just swapped to screenshot-based pixel checks

        if upgrade == 'fortune':
            pos = (960, 406)
            click(765, 497, delay=0.1)
            scroll(-1000)
            time.sleep(0.2)
            tap('/')
            tap('/')

            while not seen(pos[0], pos[1], (24, 24, 24), tol=50, sample_half=2):
                if not g_toggle:
                    break
                click(pos[0], pos[1], delay =0.1)
                time.sleep(0.8)

            scroll(1000)
            click(1112, 309, delay =0.1)

        elif upgrade == 'range':
            pos = (955, 562)
            click(765, 497, delay=0.1)
            scroll(-1000)
            time.sleep(0.2)
            tap('/')
            tap('/')

            while not seen(pos[0], pos[1], (24, 24, 24), tol=50, sample_half=2):
                if not g_toggle:
                    break
                click(pos[0], pos[1], delay =0.1)
                time.sleep(0.8)

            scroll(1000)
            click(1112, 309, delay =0.1)

        elif upgrade == "damage":
            pos = (954, 415)
            click(765, 497, delay=0.1)
            scroll(-1000)
            time.sleep(0.2)
            tap('/')
            tap('down'); tap('down'); tap('down'); tap('down')
            tap('/')

            while not seen(pos[0], pos[1], (24, 24, 24), tol=50, sample_half=2):
                if not g_toggle:
                    break
                click(pos[0], pos[1], delay =0.1)
                time.sleep(0.8)

            scroll(1000)
            click(1112, 309, delay =0.1)

        elif upgrade == "speed":
            pos = (956, 566)
            click(765, 497, delay=0.1)
            scroll(-1000)
            time.sleep(0.2)
            tap('/')
            tap('down'); tap('down'); tap('down'); tap('down')
            tap('/')

            while not seen(pos[0], pos[1], (24, 24, 24), tol=50, sample_half=2):
                if not g_toggle:
                    break
                click(pos[0], pos[1], delay =0.1)
                time.sleep(0.8)

            scroll(1000)
            click(1112, 309, delay =0.1)

        elif upgrade == "armor":
            pos = (954, 561)
            click(765, 497, delay=0.1)
            scroll(-1000)
            time.sleep(0.2)
            tap('/')
            tap('down'); tap('down'); tap('down'); tap('down'); tap('down')
            tap('/')

            while not seen(pos[0], pos[1], (24, 24, 24), tol=50, sample_half=2):
                if not g_toggle:
                    break
                click(pos[0], pos[1], delay =0.1)
                time.sleep(0.8)

            scroll(1000)
            click(1112, 309, delay =0.1)

    print(f"Purchased {upgrade}")


def secure_select(pos: tuple[int, int]):
    click(pos[0], pos[1], delay =0.1)
    time.sleep(0.5)
    attempts = 5

    # Wait until the “selected” UI pixel is white
    while not pixel_matches_at(604, 383, (255, 255, 255), tol=25, sample_half=1) and attempts<=0:
        attempts -= 1
        print(f"Attempts to select: {attempts}")
        if bt.does_exist('Winter/Erza_Armor.png', confidence=0.8, grayscale=True):
            click(752, 548, delay =0.1)
            time.sleep(0.6)

        click(pos[0], pos[1], delay =0.1)
        time.sleep(0.8)

    # print(f"Selected unit at {pos}")

#Image recognition
def _resolve_image_path(img_path: str) -> str:
    """
    Preserve legacy `Winter/...` callsites by resolving against common asset roots.
    """
    candidates = []

    # 1) As provided (absolute path or cwd-relative)
    candidates.append(Path(img_path))

    script_dir = Path(__file__).resolve().parent

    # 2) Relative to this script
    candidates.append(script_dir / img_path)

    # 3) Relative to Resources/ (matches botTools asset layout)
    candidates.append(script_dir / "Resources" / img_path)

    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except Exception:
            continue

    # Fall back to original path so pyautogui error still includes caller input
    return img_path


def find_image_center(img_path: str, confidence: float = 0.8, grayscale: bool = False, region=None, screenshot=None):
    """
    Returns (cx, cy, box) where box=(left, top, width, height) in screen coords, or (None, None, None).
    Uses the same mss + backing-scale approach as botTools._locate_image.
    """
    resolved = _resolve_image_path(img_path)
    loc = bt._locate_image(resolved, confidence=confidence, grayscale=grayscale, region=region)
    if loc is None:
        return None, None, None
    left, top, w, h = loc
    return left + w // 2, top + h // 2, loc


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
    """
    Finds an image on screen and clicks its center (+ optional offset).
    Returns True on click, False if the image was not found or locate failed.
    """
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

    # find_image_center already returns screen-space coords via bt._locate_image
    ox, oy = offset if offset is not None else (0, 0)
    click(cx + int(ox), cy + int(oy), delay=delay, right_click=right_click)
    return True


def _match_template_score_in_region(
    img_path: str,
    grayscale: bool = False,
    region: tuple | None = None,
    screenshot=None,
):
    resolved = _resolve_image_path(img_path)
    read_mode = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    template = cv2.imread(resolved, read_mode)
    if template is None:
        return None
    scale = _get_backing_scale()
    if scale != 1.0:
        th_r, tw_r = template.shape[:2]
        template = cv2.resize(template, (max(1, int(tw_r / scale)), max(1, int(th_r / scale))), interpolation=cv2.INTER_AREA)

    if screenshot is None:
        screenshot = _safe_screenshot()
    if screenshot is None:
        return None
    screen_arr = np.array(screenshot)
    screen_img = cv2.cvtColor(screen_arr, cv2.COLOR_RGB2GRAY if grayscale else cv2.COLOR_RGB2BGR)

    ss_region = _screen_region_to_screenshot_region(region, screenshot=screenshot)
    if ss_region is None:
        rx = ry = 0
        crop = screen_img
    else:
        rx, ry, rw, rh = ss_region
        crop = screen_img[ry:ry + rh, rx:rx + rw]
        if crop.size == 0:
            return None

    th, tw = template.shape[:2]
    if crop.shape[0] < th or crop.shape[1] < tw:
        return None

    result = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return {
        "score": float(max_val),
        "box": (rx + max_loc[0], ry + max_loc[1], tw, th),
    }


def _detect_hotbar_unit_in_slot(
    slot_region: tuple[int, int, int, int],
    units: list[str],
    confidence: float = 0.8,
):
    return detect_unit_in_slot(slot_region, units, confidence)


def place_unit(unit: str, pos: tuple[int, int], upgrade: bool | None = None, close: bool | None = None, region: tuple | None = None):
    """
    Places a unit found in Winter/UNIT_hb.png at location given in pos.
    mac/Retina-safe: uses screenshot-based pixel checks.
    """

    # Tunables
    place_attempts = 15
    hotbar_wait_checks = 20
    hotbar_poll_delay = 0.04
    white_ui = (235, 235, 235)
    hb_region = region if region is not None else HOTBAR_REGION

    # 1) Find and arm hotbar icon (bounded to hotbar region for speed)
    armed = False
    hb_img = f"Winter/{unit}_hb.png"
    for arm_pass in range(2):
        for i in range(hotbar_wait_checks):
            if click_image_center(
                hb_img,
                confidence=0.8,
                grayscale=False,
                offset=(0, 0),
                region=hb_region,
                delay=0.05,
                retries=1,
                retry_delay=0.0,
            ):
                armed = True
                break
            time.sleep(hotbar_poll_delay)
        if armed:
            break
        refresh_hotbar_hover()
    if not armed:
        print(f"[place_unit] {unit} hotbar icon not found in time.")
        return

    # 2) Try to place it
    time.sleep(0.2)  # allow hotbar selection to fully arm
    click(pos[0], pos[1], delay=0.6)
    time.sleep(0.2)

    # Keep attempting until the “close/back” pixel becomes white (means menu closed / placement done)
    for attempt in range(place_attempts):
        if pixel_matches_at(604, 383, white_ui, tol=25, sample_half=1):
            break
        if attempt == place_attempts - 1:
            print("timed out")
            break
        if not g_toggle:
            break

        click(pos[0], pos[1], delay=0.51)
        time.sleep(0.09)
        tap('q')  # your “cancel/rotate/nudge” behaviour
        time.sleep(0.15)

        click(pos[0], pos[1], delay=0.1)
        time.sleep(0.30)

        # If the game shows “UnitExists” we’re done (unit placed)
        if bt.does_exist("Winter/UnitExists.png", confidence=0.8, grayscale=True):
            break

        # If we *now* see the UI pixel is white, also done
        if pixel_matches_at(604, 383, white_ui, tol=25, sample_half=1):
            break

        # Re-click hotbar icon to re-arm placement if needed
        click_image_center(
            hb_img,
            confidence=0.8,
            grayscale=False,
            offset=(0, 0),
            region=hb_region,
            delay=0.12,
            retries=1,
            retry_delay=0.0,
        )
        time.sleep(0.12)

    if upgrade:
        tap('z')
        time.sleep(0.2)
    if close:
        click(607, 381, delay =0.1)

    # print(f"Placed {unit} at {pos}")

def buy_monarch():  # this just presses e until it buys monarch, use after direction('5')
    monarch_region = (679, 610, 146, 45)
    e_delay = 0.4
    timeout = 3/e_delay
    tap('e')
    while not bt.does_exist('Winter/DetectArea.png',confidence=0.7,grayscale=True):
        if bt.does_exist('Winter/Monarch.png',confidence=0.7,grayscale=False, region=monarch_region):
            break
        if timeout < 0:
            quick_rts()
            directions('5')
            timeout = 3/e_delay
        timeout-=1
        tap('e')
        time.sleep(e_delay)
    # print("Found area")
    while not bt.does_exist('Winter/Monarch.png',confidence=0.7,grayscale=False, region=monarch_region):
        if not g_toggle:
            break
        tap('e')
        time.sleep(0.8)
    # print("Got monarch")

def place_unit_hotbar():
    # Scans each hotbar slot left-to-right and drains matching units before moving on.
    doom = (572, 560)

    for slot_index, slot_region in enumerate(HOTBAR_SLOT_REGIONS, start=1):
        doom_placements = 0
        while g_toggle:
            detected = _detect_hotbar_unit_in_slot(
                slot_region,
                Settings.Units_Placeable,
                confidence=0.8,
            )
            if detected is None:
                refresh_hotbar_hover()
                detected = _detect_hotbar_unit_in_slot(
                    slot_region,
                    Settings.Units_Placeable,
                    confidence=0.8,
                )
            if detected is None:
                break

            unit = detected["unit"]

            if unit != "Doom":
                placements_left = Settings.Unit_Placements_Left.get(unit, 0)
                unit_pos = Settings.Unit_Positions.get(unit) or []
                index = placements_left - 1

                if placements_left <= 0 or index >= len(unit_pos):
                    print(
                        f"[hotbar] slot {slot_index}: {unit} detected but no placements remain."
                    )
                    break

                place_unit(unit, unit_pos[index], region=slot_region)
                if unit == 'Kag' and USE_KAGUYA:
                    kag_ability = [(645, 444), (743, 817), (1091, 244)]
                    for cl in kag_ability:
                        if cl == (743, 817):
                            click_image_center("Winter/Kaguya_Auto.png", confidence=0.8, grayscale=False, offset=[0,0])
                        else:
                            click(cl[0],cl[1],delay =0.1)
                            time.sleep(1)

                Settings.Unit_Placements_Left[unit] -= 1
                print(
                    f"Placed {unit} from slot {slot_index} | "
                    f"{unit} has {Settings.Unit_Placements_Left.get(unit)} placements left."
                )

                if Settings.Unit_Placements_Left[unit] <= 0:
                    break
                continue

            place_unit(unit, doom, region=slot_region)
            time.sleep(2)
            set_boss()
            tap('z')
            click(607, 381, delay =0.1)
            directions('5')
            buy_monarch()
            quick_rts()
            click(doom[0],doom[1],delay =0.1)
            doom_placements += 1
            print(f"Placed doom slayer from slot {slot_index}.")

            if doom_placements >= 6:
                print(f"[hotbar] slot {slot_index}: stopping repeated Doom placements for safety.")
                break

    click(600,380, delay =0.1)


def place_hotbar_units():
    place_unit_hotbar()
            
def ainz_setup(unit:str): 
    '''
    Set's up ainz's abilities and places the unit given.
    '''
    pos  = [(646, 513), (526, 622), (779, 439), (779, 511), (503, 400), (524, 541), (781, 491), (506, 398), (681, 458), (778, 506), (959, 645), (750, 559), (649, 587), (690, 677), (503, 377), (495, 456), (618, 521)]
    for v,i in enumerate(pos):
        if AINZ_SPELLS and v<12:
            #491,458
            continue
        if v == 12: # the click to open world items
            print("Selected Spells")
            click(Settings.Unit_Positions['Ainz'][0][0], Settings.Unit_Positions['Ainz'][0][1], delay =0.1)
            print("Waiting for world item logo")
            while not bt.does_exist("Winter/CaloricThing.png",confidence=0.8,grayscale=False):
                time.sleep(0.5)
            print(f"Placing unit {unit}")
        while not pixel_matches_at(604, 383,(255,255,255), tol=25, sample_half=0):
            click(i[0],i[1],delay =0.1)
    
        time.sleep(1)
        
        if v == 14:
            write_text(unit)
        time.sleep(0.5)

def repair_barricades(): # Repair barricades 
    #DIR_BARRICADE
    tap('v')
    time.sleep(1)
    press('a')
    time.sleep(0.7)
    release('a')
    tap('e')
    tap('e')
    press('w')
    time.sleep(0.2)
    release('w')
    tap('e')
    tap('e')
    press('s')
    time.sleep(0.4)
    release('s')
    tap('e')
    tap('e')
    time.sleep(1)
    tap('v')
    time.sleep(2)
    
def set_boss(): # Sets unit priority to boss
    tap('r')
    tap('r')
    tap('r')
    tap('r')
    tap('r')
    
def on_failure():
    print("Failed. Fixing...")
    time_out = 60/0.4
    click(Settings.REPLAY_BUTTON_POS[0],Settings.REPLAY_BUTTON_POS[1],delay =0.1)
    time.sleep(1)
    while bt.does_exist("Failed.png",confidence=0.7,grayscale=False):
        if time_out<0:
            on_disconnect()
            print("Should disconnect")
        click(Settings.REPLAY_BUTTON_POS[0],Settings.REPLAY_BUTTON_POS[1],delay =0.1)
        print("Retrying...")
        time_out-=1
        time.sleep(0.4)
    click(Settings.REPLAY_BUTTON_POS[0],Settings.REPLAY_BUTTON_POS[1],delay =0.1)
    click(750, 567, delay = 0.5)

def _record_failure_and_notify(reason: str = "Failure"):
    stats = {}
    try:
        stats = load_json_data()
        if stats is None:
            stats = {}
        stats.setdefault("num_runs", 0)
        stats.setdefault("losses", 0)
        stats.setdefault("wins", 0)
        stats["num_runs"] += 1
        stats["losses"] += 1
        stats["runtime"] = f"{str((datetime.now() - start)).split('.')[0]}"
        save_json_data(stats)
    except Exception as e:
        print(f"stats error: {e}")

    if Settings.ENABLE_WEBHOOKS and Settings.ENABLE_FAILURE_PING:
        try:
            loss_img = _roblox_window_screenshot_for_webhook()
            Thread(
                target=webhook.send_webhook,
                kwargs={
                    "run_time": f"{str((datetime.now() - start)).split('.')[0]}",
                    "num_runs": stats.get("num_runs"),
                    "win": stats.get("wins"),
                    "lose": stats.get("losses"),
                    "task_name": f"Winter Event (Failed: {reason})",
                    "img": loss_img,
                    "enabled": Settings.ENABLE_WEBHOOKS,
                    "alert_text": Settings.ALERT_TARGET,
                },
                daemon=True,
            ).start()
        except Exception as e:
            print(f"[Webhook] Failure ping error: {e}")


def _buy_and_place_nami_with_timeout(timeout_seconds: int = PLACEMENT_TIMEOUT_SECONDS) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline and g_toggle:
        if not bt.does_exist('Winter/Nami_hb.png', confidence=0.7, grayscale=False):
            tap('e')
            time.sleep(0.5)
            continue

        place_unit('Nami', (755, 580))
        time.sleep(0.2)
        tap('z')
        time.sleep(0.2)
        click(607, 381, delay=0.1)
        time.sleep(1)
        quick_rts()
        time.sleep(0.5)

        # After successful placement, Nami should no longer be in hotbar.
        if not bt.does_exist('Winter/Nami_hb.png', confidence=0.7, grayscale=False):
            return True

    return False

def _buy_and_place_tak_with_timeout(timeout_seconds: int = PLACEMENT_TIMEOUT_SECONDS) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline and g_toggle:
        if not bt.does_exist('Winter/Tak_hb.png', confidence=0.7, grayscale=False):
            tap('e')
            time.sleep(0.5)
            continue

        place_unit("Tak", Settings.Unit_Positions.get("tak"))
        tap('z')
        click(607, 381, delay=0.1)
        time.sleep(1)

        # After successful placement, Nami should no longer be in hotbar.
        if not bt.does_exist('Winter/Tak_hb.png', confidence=0.7, grayscale=False):
            return True

    return False

def _buy_and_place_hero_with_timeout(timeout_seconds: int = PLACEMENT_TIMEOUT_SECONDS) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline and g_toggle:
        if not bt.does_exist('Winter/Hero_hb.png', confidence=0.7, grayscale=False):
            tap('e')
            time.sleep(0.5)
            continue
        
        quick_rts()
        place_unit("Hero", Settings.Unit_Positions.get("Hero"))
        tap('z')
        click(607, 381, delay=0.1)
        time.sleep(1)

        # After successful placement, Hero should no longer be in hotbar.
        if not bt.does_exist('Winter/Hero_hb.png', confidence=0.7, grayscale=False):
            return True

    return False


def sell_kaguya(): # Sells kaguya (cant reset while domain is active)
    sold = False
    tick = 0
    click(1119, 450,delay =0.1)
    time.sleep(1)
    while not sold:
        sell = click_image_center('Winter/Kaguya.png',confidence=0.8,grayscale=False,offset=[0,0])
        if g_toggle == False:
            break
        if sell == True:
            time.sleep(1)
            tap('x')
            sold = True
        scroll(-100)
        tick+=1
        if tick>=40:
            sold = True
        time.sleep(0.4)

def detect_loss():
    print("Loss detection: Active")


    while True:
        if not g_toggle:
            time.sleep(0.25)
            continue

        try:
            loss_found = bt.does_exist("Failed.png", confidence=0.7, grayscale=False)
        except Exception as e:
            print(f"[detect_loss] does_exist error: {e}")
            loss_found = False

        if loss_found:
            print("Found loss screen")
            _record_failure_and_notify(reason="Loss Screen")

            try:
                on_failure()
            except Exception as e:
                print(f"[detect_loss] on_failure error: {e}")

            while g_toggle:
                try:
                    still_loss = bt.does_exist("Failed.png", confidence=0.7, grayscale=False)
                except Exception as e:
                    print(f"[detect_loss] does_exist error (wait loop): {e}")
                    still_loss = False

                if not still_loss:
                    break
                time.sleep(1)

            print("relaunching")

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
                print(f"[detect_loss] relaunch error: {e}")

        time.sleep(1)

Thread(target=detect_loss, daemon=True).start()

def main():
    ensure_roblox_window_positioned()
    rabbit_pos = Settings.Unit_Positions.get("mirko")
    speed_pos =  Settings.Unit_Positions.get("speedwagon")
    gamer_pos = Settings.Unit_Positions.get("Hero") or []
    start_of_run = datetime.now()
    startup_stats = load_json_data() or {}
    startup_total = int(startup_stats.get("num_runs", 0) or 0)
    startup_wins = int(startup_stats.get("wins", 0) or 0)
    startup_losses = int(startup_stats.get("losses", 0) or 0)
    # print(f"[Stats] Starting totals | Runs: {startup_total} | Wins: {startup_wins} | Losses: {startup_losses}")
    if Settings.ENABLE_WEBHOOKS:
        if WEBHOOK_CHECKER:
            try:
                startup_img = _roblox_window_screenshot_for_webhook()
                Thread(
                    target=webhook.send_webhook,
                    kwargs={
                        "run_time": "0:00:00",
                        "num_runs": startup_total,
                        "win": startup_wins,
                        "lose": startup_losses,
                        "task_name": "Winter Event (Started)",
                        "img": startup_img,
                        "enabled": Settings.ENABLE_WEBHOOKS,
                    },
                    daemon=True,
                ).start()
            except Exception as e:
                print(f"[Webhook] Startup webhook error: {e}")
    else:
        print("[Webhook] Disabled by settings (ENABLE_WEBHOOKS=false)")
    session_runs = 0
    while True:
        if RUNS_BEFORE_REJOIN > 0:
            print("Restarting")
            if session_runs >= RUNS_BEFORE_REJOIN:
                try:
                    print("reconnect")
                    args = list(sys.argv)
                    if "--stopped" in args:
                        args.remove("--stopped")
                    sys.stdout.flush()
                    subprocess.Popen([sys.executable, *args, "--restart"])
                    os._exit(0)
                except Exception as e:
                    print(e)
        global g_toggle
        if g_toggle:
            # Reset all placement counts:
            Reset_Placements = {
                "Ainz": 1,
                'Beni': 3,
                'Rukia': 3,
                'Mage': 3,
                'Escanor': 1,
                'Hero': 3,
                'Kuzan':4,
                'Kag':1
            }   
            if not USE_KAGUYA:
                Reset_Placements['Kag'] = 0
                
            Settings.Unit_Placements_Left = Reset_Placements.copy()
            
            while not avM.get_wave() == 0:
                avM.restart_match()
            wait_start()
            quick_rts()
            time.sleep(2)
            # Set up first 2 rabbits
            got_mirko = False
            while not got_mirko:
                directions('1', 'rabbit')
                tap('e')
                tap('e')
                time.sleep(0.5)
                refresh_hotbar_hover()
                if bt.does_exist("Winter/Bunny_hb.png",confidence=0.7,grayscale=False,region=HOTBAR_REGION):
                    print("Got mirko")
                    got_mirko = True
                else:
                    print("Didnt detect mirko, retrying purchase")
                quick_rts()
                time.sleep(1.5)
            click(835, 226, delay =0.1) # Start Match
                        
            
            place_unit('Bunny', rabbit_pos[0], close=True)
            time.sleep(3)
            place_unit('Bunny', rabbit_pos[1], close=True)
            print("Placed first 2 rabbits")
            # get third
            got_mirko_two = False
            while not got_mirko_two:
                print("Attempting to buy third rabbit")
                directions('1', 'rabbit')
                tap('e')
                time.sleep(0.5)
                if bt.does_exist("Winter/Bunny_hb.png",confidence=0.5,grayscale=False,region=HOTBAR_REGION):
                    print("Got mirko")
                    got_mirko_two = True
                else:
                    print("Didnt detect mirko, retrying purchase")
                quick_rts()
                time.sleep(1.5)
            place_unit('Bunny', rabbit_pos[2], close=True)
            
            #Start farms - speedwagon
            directions('2', 'speed')
            tap('e')
            tap('e')
            tap('e')
            
            
    
            place_unit('Speed', speed_pos[0], upgrade = True, close=False)
            place_unit('Speed', speed_pos[1], upgrade = True, close=False)
            place_unit('Speed', speed_pos[2], upgrade = True, close=False)
            click(607, 381, delay =0.1)
            
            # Tak's placement + max
            
            time.sleep(1)
            click(760,375,delay=0.2,right_click=True) # Goes to Tak's card
            time.sleep(3)
            # Tak (timeout-safe): if not placed quickly, treat as failed run and restart.
            if not _buy_and_place_tak_with_timeout():
                print(f"[Tak] Failed to place within {PLACEMENT_TIMEOUT_SECONDS}s. Restarting run as failure.")
                _record_failure_and_notify(reason=f"Tak Timeout ({PLACEMENT_TIMEOUT_SECONDS}s)")
                match_restarted = False
                while not match_restarted and g_toggle:
                    print("[Restart] Tak timeout restart...")
                    avM.restart_match()
                    time.sleep(2)
                    match_restarted = True
                continue
            
            #DIR_NAMICARD
            if bt.does_exist("Winter/Nami_detect.png",confidence=0.8,grayscale=True):
                print("Detected Nami.")
                click_image_center("Winter/Nami_detect.png",confidence=0.8,grayscale=True,offset=(0,0))
                time.sleep(0.5)
                click(Settings.CTM_NAMI_CARD[0], Settings.CTM_NAMI_CARD[1], delay =0.2)
                time.sleep(0.5) 
                click(50,50,delay=0.1,right_click=True,dont_move=True)
            else:
                click(Settings.CTM_NAMI_CARD[0], Settings.CTM_NAMI_CARD[1], delay =0.2)
                time.sleep(0.5)
                click(Settings.CTM_NAMI_CARD[0], Settings.CTM_NAMI_CARD[1], delay =0.1, right_click=True) # Goes to nami's card
            time.sleep(7)
            # Nami (timeout-safe): if not placed quickly, treat as failed run and restart.
            if not _buy_and_place_nami_with_timeout():
                print(f"[Nami] Failed to place within {PLACEMENT_TIMEOUT_SECONDS}s. Restarting run as failure.")
                _record_failure_and_notify(reason=f"Nami Timeout ({PLACEMENT_TIMEOUT_SECONDS}s)")
                match_restarted = False
                while not match_restarted and g_toggle:
                    print("[Restart] Nami timeout restart...")
                    avM.restart_match()
                    time.sleep(2)
                    match_restarted = True
                continue

            # Go to upgrader for fortune
            directions('4')
            upgrader('fortune')
            click(1112, 312, delay =1)
            time.sleep(0.5)
            quick_rts()
            time.sleep(0.2)
            
            directions('1', 'hero')
            # time.sleep(10)
            wave_tick = avM.get_wave()
            while avM.get_wave()==wave_tick:
                time.sleep(1)
            
            while not bt.does_exist("Winter/Hero_hb.png", confidence=0.7, grayscale=False):
                tap('e')
                time.sleep(0.2)
                tap('e')
                time.sleep(0.2)
                tap('e')
                time.sleep(2)
            print("Bought Sunraku")
            
            quick_rts()
            time.sleep(0.5)
            
            for i in range(3):
                place_unit('Hero', gamer_pos[i], close = False)
                Settings.Unit_Placements_Left['Hero']-=1
                print(f"Placed Sunraku | Sunraku has {Settings.Unit_Placements_Left.get('Hero')} placements left.")
                time.sleep(0.5)
                click(649, 452, delay=0.1)
                time.sleep(0.5)
                click(1019, 707, delay=0.1)
                time.sleep(0.5)
                click(1140, 290,delay =0.1)
                time.sleep(0.5)
                click(607, 381, delay =0.1)
                
                
            # # Start auto upgrading first rabbit
            # secure_select(rabbit_pos[0])
            # time.sleep(0.5)
            # tap('z')
            # click(607, 381, delay =0.1)
            
            
            # # Start auto upgrading rabbit 1 & 2
            # secure_select(rabbit_pos[1])
            # time.sleep(0.5)
            # tap('z')
            # click(607, 381, delay =0.1)
            # time.sleep(1)
            # secure_select(rabbit_pos[2])
            # time.sleep(0.5)
            # tap('z')
            # click(607, 381, delay =0.1)
            # time.sleep(1)
            
            # # Get first monarch
            # directions('5')
            # buy_monarch()
            # quick_rts()
            # time.sleep(1)
            # secure_select(rabbit_pos[0])
            
            # Wave 19 lane unlocks for 20% boost
            time.sleep(2)
            print("Buying lanes 2 & 3.")
            press('d')
            time.sleep(Settings.BUY_MAIN_LANE_DELAYS[0])
            release('d')

            tap('e'); tap('e')

            press('w')
            time.sleep(Settings.BUY_MAIN_LANE_DELAYS[1])
            release('w')

            tap('e'); tap('e')
            time.sleep(0.5)
            quick_rts()
            
            # get +100% dmg upgrade
            directions('4')
            upgrader('speed')
            upgrader('damage')
            upgrader('range')
            time.sleep(0.5)
            click(1112, 312, delay=1)
            time.sleep(0.5)
            quick_rts()
            
            for gamer in Settings.Unit_Positions['Hero']:
                click(gamer[0],gamer[1],delay =0.1)
                secure_select((gamer[0],gamer[1]))
                time.sleep(0.5)
                tap('z')
                set_boss()
                time.sleep(0.5)
                click(607, 381, delay =0.1)
                directions('5')
                buy_monarch()
                quick_rts()
                time.sleep(0.5)
                secure_select((gamer[0],gamer[1]))
                time.sleep(0.5)
                click(607, 381, delay =0.1)
            # wave_19 = False

            # while not wave_19 and g_toggle:
            #     w = avM.get_wave()
            #     print("Wave read:", w)
                
            #     # ✅ guard against None / unreadable values
            #     if w is None or w == -1:
            #         time.sleep(0.5)
            #         continue

            #     if w >= 19:
            #         # DIR_BUYMAINLANES
            #         press('d')
            #         time.sleep(Settings.BUY_MAIN_LANE_DELAYS[0])
            #         release('d')

            #         tap('e'); tap('e')

            #         press('w')
            #         time.sleep(Settings.BUY_MAIN_LANE_DELAYS[1])
            #         release('w')

            #         tap('e'); tap('e')

            #         wave_19 = True
            #         break

            #     time.sleep(0.5)
            
            time.sleep(0.5)
            # Go to lootbox         
            
            Erza_Upgraded = False
            Erza_Buff = False
            
            gamble_done = False
            ainzplaced = False
            prevent_inf = 5
            at_lootbox = False

            while not gamble_done:

                if not ainzplaced and Settings.Unit_Placements_Left['Ainz'] == 0:
                    print("Ainz Setup")
                    quick_rts()
                    time.sleep(1)

                    ainz_pos = Settings.Unit_Positions['Ainz']
                    pos = Settings.Unit_Positions.get("Caloric_Unit")

                    secure_select((ainz_pos[0]))
                    time.sleep(0.5)
                    tap('z')
                    time.sleep(0.5)

                    if Settings.USE_WD == True:
                        ainz_setup(unit="world")
                    elif Settings.USE_DIO == True:
                        ainz_setup(unit="god")
                    elif USE_BUU:
                        ainz_setup(unit="boo")
                    else:
                        ainz_setup(unit=Settings.USE_AINZ_UNIT)

                    global AINZ_SPELLS
                    if not AINZ_SPELLS:
                        AINZ_SPELLS = True

                    click(pos[0], pos[1], delay=0.67)
                    time.sleep(0.5)

                    while not pixel_matches_at(604, 382, (255, 255, 255), tol=20, sample_half=1) and bt.does_exist("Winter/UnitExists.png",confidence=0.8,grayscale=False,region=(212,576,315,197)):
                        if not g_toggle:
                            break
                        click(pos[0], pos[1], delay=0.67)
                        time.sleep(0.5)

                    time.sleep(1)

                    if Settings.USE_DIO:
                        ability_clicks = [(648, 448), (1010, 563), (1099, 309)]
                        for p in ability_clicks:
                            click(p[0], p[1], delay =0.1)
                            time.sleep(1.2)

                    if Settings.MAX_UPG_AINZ_PLACEMENT:
                        tap('z')

                    if Settings.MONARCH_AINZ_PLACEMENT:
                        directions('5')
                        buy_monarch()
                        quick_rts()
                        time.sleep(1)
                        click(pos[0], pos[1], delay=0.67)

                    time.sleep(1)
                    print("Placed ainz's unit")
                    click(607, 381, delay =0.1)

                    ainzplaced = True

                    directions('5')
                    buy_monarch()
                    quick_rts()
                    time.sleep(1)
                    click(ainz_pos[0][0],ainz_pos[0][1],delay =0.1)

                    time.sleep(1)
                    directions('4')
                    upgrader('armor')
                    click(1112, 312, delay =1)
                    time.sleep(0.5)
                    quick_rts()

                    at_lootbox = False
                    continue

                if (ainzplaced or avM.get_wave()>=40 or not Erza_Buff) and not Erza_Upgraded:

                    erza_buffer = Settings.Unit_Positions['Mage']

                    if Settings.Unit_Placements_Left['Mage'] == 0:
                        quick_rts()
                        time.sleep(1)

                        if Erza_Buff:
                            print("Duelist Erzas")
                            secure_select(erza_buffer[1])
                            time.sleep(0.8)
                            tap('z')
                            click(647, 449,delay =0.1)

                            while not bt.does_exist('Winter/Erza_Armor.png',confidence=0.8,grayscale=True):
                                click(747, 690,delay =0.1)
                                time.sleep(0.5)

                            click(752, 548,delay =0.1)
                            time.sleep(0.5)
                            click(1140, 290,delay =0.1)
                            set_boss()
                            time.sleep(0.5)

                            secure_select(erza_buffer[2])
                            time.sleep(0.8)
                            click(647, 449,delay =0.1)
                            tap('z')

                            while not bt.does_exist('Winter/Erza_Armor.png',confidence=0.8,grayscale=True):
                                click(747, 690,delay =0.1)
                                time.sleep(0.5)

                            click(752, 548,delay =0.1)
                            time.sleep(0.5)
                            click(1140, 290,delay =0.1)
                            set_boss()
                            time.sleep(0.5)
                            click(607, 381, delay =0.1)

                            directions('5')
                            buy_monarch()
                            quick_rts()
                            click(erza_buffer[1][0],erza_buffer[1][1],delay =0.1)
                            time.sleep(0.5)

                            directions('5')
                            buy_monarch()
                            quick_rts()
                            click(erza_buffer[2][0],erza_buffer[2][1],delay =0.1)
                            time.sleep(0.5)

                            Erza_Upgraded = True
                            at_lootbox = False
                            continue

                        if not Erza_Buff:

                            print("Buffing with Erza.")
                            secure_select(erza_buffer[0])
                            time.sleep(8)

                            click(378,662)
                            time.sleep(0.8)
                            click(647, 449,delay =0.1)

                            while not bt.does_exist('Winter/Erza_Armor.png',confidence=0.8,grayscale=True):
                                click(1015,690,delay =0.1)
                                time.sleep(0.5)

                            click(752, 548,delay =0.1)
                            time.sleep(0.5)
                            click(1140, 290,delay =0.1)
                            time.sleep(0.5)
                            click(607, 381, delay =0.1)

                            Erza_Buff = True
                            at_lootbox = False
                            continue

                ready_to_gamble = True

                for unit in Settings.Units_Placeable:
                    if unit != "Doom":
                        if Settings.Unit_Placements_Left[unit] > 0:
                            ready_to_gamble = False
                            break

                if not at_lootbox:
                    directions('3')
                    at_lootbox = True

                for _ in range(50):
                    tap('e')
                    time.sleep(0.1)

                prevent_inf -= 1
                print(f"Prevent Inf: {prevent_inf}")

                full_bar = bt.does_exist("Winter/Full_Bar.png", confidence=0.7, grayscale=True)
                no_yen = bt.does_exist("Winter/NO_YEN.png", confidence=0.5, grayscale=True)

                if full_bar or no_yen or (prevent_inf <= 0):
                    prevent_inf = 5
                    # print("Getting Units")
                    quick_rts()
                    time.sleep(2)
                    place_hotbar_units()
                    at_lootbox = False

                print("===============================")
                is_done = True

                for unit in Settings.Units_Placeable:
                    if unit != "Doom":
                        if Settings.Unit_Placements_Left[unit] > 0:
                            is_done = False
                            print(f"{unit} has {Settings.Unit_Placements_Left[unit]} placements left.")

                print("===============================")

                if is_done and ainzplaced and Erza_Buff:
                    gamble_done = True
                elif avM.get_wave()>=80:
                    gamble_done = True

                time.sleep(0.1)

            print("Gambling done")

            # Auto upgrade + Monarch everything else
            quick_rts()
            time.sleep(1)
    
            # World destroyer
            if Settings.USE_WD:
                print("Already Maxed.")
                # secure_select(Settings.Unit_Positions.get("Caloric_Unit"))
                # time.sleep(1)
                # while not bt.does_exist("Winter/StopWD.png",confidence=0.8,grayscale=False,region=(365,399,309,210)):
                #     tap('t')
                #     time.sleep(1)
                #     if bt.does_exist("Unit_Maxed.png",confidence=0.8,grayscale=False):
                #         print("Unit Maxed.")
                #         break
                # time.sleep(0.5)
                # click(607, 381, delay =0.1)
            elif Settings.USE_DIO:
                secure_select(Settings.Unit_Positions.get("Caloric_Unit"))
                time.sleep(1)
                while True:
                    if bt.does_exist("Winter/DIO_MOVE.png",confidence=0.8,grayscale=False):
                        print("Stop")
                        break
                    if bt.does_exist("Unit_Maxed.png",confidence=0.8,grayscale=False):
                        print("Stop, maxed on accident")
                        break
                    tap('t')
                    time.sleep(0.5)
                time.sleep(0.5)
                click(607, 381, delay =0.1)
            elif USE_BUU:
                secure_select(Settings.Unit_Positions.get("Caloric_Unit"))
                time.sleep(1)
                while True:
                    if bt.does_exist("Winter/Buu_Ability.png",confidence=0.5,grayscale=False):
                        print("Found Ability")
                        click_image_center("Winter/Buu_Ability.png",confidence=0.5,grayscale=False,offset=(0,0))
                        time.sleep(1)
                        click(441,151,0.2)
                        time.sleep(1)
                    if bt.does_exist("Winter/BuuSellDetect.png",confidence=0.8,grayscale=False, ):
                        print("SellBuu")
                        tap('x')
                        break
                    if not bt.does_exist("Winter/Unit_Maxed.png",confidence=0.8,grayscale=False):
                        print("Upgrade")
                        tap('t')
                        time.sleep(.1) 
            elif Settings.MAX_UPG_AINZ_PLACEMENT == False:
                secure_select(Settings.Unit_Positions.get("Caloric_Unit"))
                time.sleep(1)
                while True:
                    if bt.does_exist("Winter/YOUR_MOVE.png",confidence=0.8,grayscale=False):
                        print("Stop")
                        break
                    if bt.does_exist("Unit_Maxed.png",confidence=0.8,grayscale=False):
                        print("Stop, maxed on accident")
                        break
                    tap('t')
                    time.sleep(0.5)
                time.sleep(0.5)
                click(607, 381, delay =0.1)
            
            print("Maxing the rest of the units.")
            for ben in Settings.Unit_Positions['Beni']:
                secure_select((ben[0],ben[1]))
                time.sleep(0.5)
                tap('z')
                set_boss()
                time.sleep(0.5)
                click(607, 381, delay =0.1)
                directions('5')
                buy_monarch()
                quick_rts()
                time.sleep(0.5)
                secure_select((ben[0],ben[1]))
                time.sleep(0.5)
                click(607, 381, delay =0.1)
                    
            # ice queen
            for ice in Settings.Unit_Positions['Rukia']:
                secure_select((ice[0],ice[1]))
                time.sleep(0.5)
                set_boss()
                time.sleep(0.5)
                click(607, 381, delay =0.1)
                directions('5')
                buy_monarch()
                quick_rts()
                time.sleep(0.5)
                secure_select((ice[0],ice[1]))
                time.sleep(0.5)
                for i in range(13):
                    tap('t')
                    time.sleep(0.5)
                while not bt.does_exist("Winter/StopUpgradeRukia.png", confidence=0.7, grayscale = False):
                    if bt.does_exist("Unit_Maxed.png",confidence=0.8,grayscale=False):
                        print("Stop, maxed on accident")
                        break
                    tap('t')
                    time.sleep(1)

                time.sleep(0.5)
                click(607, 381, delay =0.1)

            
            for kuzan in Settings.Unit_Positions['Kuzan']:
                secure_select((kuzan[0],kuzan[1]))
                time.sleep(0.5)
                tap('z')
                set_boss()
                time.sleep(0.5)
                click(607, 381, delay =0.1)
                directions('5')
                buy_monarch()
                quick_rts()
                time.sleep(1)
                secure_select((kuzan[0],kuzan[1]))
                time.sleep(0.5)
                click(607, 381, delay =0.1)
            
            for i in range(3):
                click(rabbit_pos[i][0], rabbit_pos[i][1], delay =0.1)
                time.sleep(0.5)
                tap('z')
                set_boss()
                time.sleep(0.5)
                click(607, 381, delay =0.1)
                directions('5')
                buy_monarch()
                quick_rts()
                time.sleep(1)
                click(rabbit_pos[i][0], rabbit_pos[i][1], delay =0.1)
                time.sleep(0.5)
                click(607, 381, delay =0.1)
                        
            for esc in Settings.Unit_Positions['Escanor']:
                click(esc[0],esc[1],delay =0.1)
                time.sleep(0.5)
                tap('z')
                set_boss()
                time.sleep(0.5)
                click(607, 381, delay =0.1)
                directions('5')
                buy_monarch()
                quick_rts()
                time.sleep(0.5)
                click(esc[0],esc[1],delay =0.1)
                time.sleep(0.5)
                click(607, 381, delay =0.1)
            
            esc_ability = False
            
            print("Finished Upgrading! Waiting for end wave.")
            if Settings.WAVE_RESTART_150:
                wave_150 = False
                done_path = False

                while not wave_150 and g_toggle:
                    w = avM.get_wave()
                    # print("Wave Read: ", w)

                    # ✅ unreadable -> skip tick safely
                    if w is None or w == -1:
                        time.sleep(0.5)
                        continue
                    
                    if w == 145 and not esc_ability:
                        click(607, 381, delay =0.1)
                        print("Escanor Ability")
                        click(esc[0],esc[1],delay =0.1)
                        time.sleep(0.5)
                        click(649,514, delay=0.1)
                        time.sleep(0.5)
                        click(607, 381, delay =0.1)
                        esc_ability = True
                        
                    # Run once on confirmed wave 149
                    if (not done_path) and w == 148:
                        print("Confirmed wave 148 — running pre-150 logic")
                        time.sleep(2)
                        quick_rts()

                        tap('f')  # Unit Manager Hotkey
                        time.sleep(0.7)

                        ok = click_image_center("Winter/LookDownFinder.png",confidence=0.8,grayscale=False,offset=(0, -50))
                        print("[LookDownFinder] Found =", ok)

                        tap('f')

                        # spam E while we do the path (stops when done_path becomes True)
                        def spam_e():
                            while not done_path and g_toggle:
                                tap('e')
                                time.sleep(0.2)
                            print("Done buying lanes")

                        Thread(target=spam_e, daemon=True).start()

                        clicks_look_down = [(401, 404), (649, 777), (750, 875)]
                        for pt in clicks_look_down:
                            click(pt[0], pt[1], delay=1)
                            time.sleep(1 if pt == (649, 777) else 0.2)

                        press('o'); time.sleep(1); release('o')

                        press('s')
                        time.sleep(Settings.BUY_FINAL_LANE_DELAYS[0])
                        release('s')

                        tap('v')
                        time.sleep(1)

                        press('a')
                        time.sleep(Settings.BUY_FINAL_LANE_DELAYS[1])
                        release('a')

                        press('d')
                        time.sleep(Settings.BUY_FINAL_LANE_DELAYS[2])
                        release('d')

                        tap('v')
                        quick_rts()
                        time.sleep(2)

                        done_path = True  # ✅ stop spam thread

                    # Exit when 150 is reached (or higher, within sane range)
                    if w == 150:
                        wave_150 = True
                    else:
                        # ✅ only safe modulo checks when w is a real int
                        if (w % 2 == 0) or (w == 139):
                            repair_barricades()
                            quick_rts()

                    time.sleep(2)

            else:
                wave_140 = False
                done_path = False

                while not wave_140 and g_toggle:
                    w = avM.get_wave()
                    # print("[wave]", w)

                    # ✅ unreadable -> skip tick safely
                    if w is None or w == -1:
                        time.sleep(0.5)
                        continue
                    
                    if w == 135 and not esc_ability:
                        click(607, 381, delay =0.1)
                        print("Escanor Ability")
                        click(esc[0],esc[1],delay =0.1)
                        time.sleep(0.5)
                        click(649,514, delay=0.1)
                        time.sleep(0.5)
                        click(607, 381, delay =0.1)
                        esc_ability = True
                    
                    # Run once on confirmed wave 139
                    if (not done_path) and w == 138:
                        print("Confirmed wave 138 — running pre-140 logic")
                        time.sleep(4)
                        def spam_e():
                            while not done_path and g_toggle:
                                tap('e')
                                time.sleep(0.2)
                            print("Done buying lanes")

                        Thread(target=spam_e, daemon=True).start()

                        quick_rts()
                        tap('f')
                        time.sleep(0.7)

                        ok = click_image_center("Winter/LookDownFinder.png",confidence=0.8,grayscale=False,offset=(0, -50))
                        print("[LookDownFinder click] ok =", ok)

                        tap('f')

                        clicks_look_down = [(404, 400), (649, 772), (745, 858)]
                        for pt in clicks_look_down:
                            click(pt[0], pt[1], delay=1)
                            time.sleep(1 if pt == (649, 772) else 0.3)

                        press('o'); time.sleep(1); release('o')

                        press('s')
                        time.sleep(Settings.BUY_FINAL_LANE_DELAYS[0])
                        release('s')

                        tap('v')
                        time.sleep(1)

                        press('a')
                        time.sleep(Settings.BUY_FINAL_LANE_DELAYS[1])
                        release('a')

                        press('d')
                        time.sleep(Settings.BUY_FINAL_LANE_DELAYS[2])
                        release('d')

                        tap('v')
                        quick_rts()
                        time.sleep(2)

                        done_path = True  # ✅ stop spam thread

                    # Exit when 140 is reached (or higher, within sane range)
                    if w >= 140:
                        print(f"Wave Read: {w}")
                        wave_140 = True
                    else:
                        # ✅ safe modulo checks
                        if (w % 2 == 0) or (w == 139 and done_path):
                            repair_barricades()
                            quick_rts()

                    time.sleep(2)
            session_runs += 1
            try:
                    victory = _roblox_window_screenshot_for_webhook() if Settings.ENABLE_WEBHOOKS else None
                    runtime = f"{datetime.now()-start_of_run}"
                    stats = load_json_data() or {}
                    stats.setdefault("num_runs", 0)
                    stats.setdefault("wins", 0)
                    stats.setdefault("losses", 0)
                    stats["num_runs"] += 1
                    stats["wins"] += 1
                    stats["runtime"] = f"{str(runtime).split('.')[0]}"
                    save_json_data(stats)
                    print(f"Run over, session runs: {session_runs} | total runs: {stats['num_runs']}")
                
                    g = Thread(target=webhook.send_webhook,
                        kwargs={

                                "run_time": f"{str(runtime).split('.')[0]}",
                                "num_runs": stats.get("num_runs"),
                                "win": stats.get("wins"),
                                "lose": stats.get("losses"),
                                "task_name": "Winter Event",
                                "img": victory,
                                "enabled": Settings.ENABLE_WEBHOOKS,
                            },
                        )            
                    g.start()
            except Exception as e:
                print(f" error {e}")
                
            if USE_KAGUYA:    
                ainz_pos = Settings.Unit_Positions['Ainz']
                click(ainz_pos[0][0],ainz_pos[0][1],delay =0.1)
                time.sleep(0.5)
                tap('x')
                time.sleep(0.5)
                tap('f')
                time.sleep(1)
                sell_kaguya()
                tap('f')
                
            match_restarted = False

            while not match_restarted and g_toggle:

                print("[Restart] Attempting restart...")
                avM.restart_match()
                time.sleep(4)
                
                # Prefer UI confirmation over wave OCR
                if wait_start(delay=0.5):
                    print("[Restart] Start screen detected.")
                    match_restarted = True
                    break

                # Fallback: allow wave==0 confirmation
                w = avM.get_wave()
                print("[Restart] Wave after restart:", w)

                if w == 0:
                    print("[Restart] Wave reset confirmed.")
                    match_restarted = True
                    break

                print("[Restart] Restart not confirmed, retrying...")
                time.sleep(2)

if "--restart" in sys.argv:
    on_disconnect()

if Settings.ENABLE_DISCONNECT_CHECKER:
    Thread(target=disconnect_checker, daemon=True).start()
else:
    print("[Disconnect] Checker disabled via settings.")
# print(f"Launched with args {sys.argv}")

# Auto-start logic stays the same
if Settings.AUTO_START:
    if "--stopped" not in sys.argv:
        g_toggle = True
    else:
        print("Program was STOPPED, won't auto start")

for z in range(3):
    print(f"Starting in {3 - z}")
    time.sleep(1)

# if not bt.does_exist("Winter/Camera_Angled.png",confidence=0.9,grayscale=False):
#     auto_camera_angle = input("Automatically set up your camera? [Y/N] > ").strip().lower()
#     if auto_camera_angle == "y":
#         setup_cam()
#         print("Camera Setup")
#     else:
#         print("Camera may be out of position. Set it up manually if it breaks.")

# ✅ Focus Roblox once before any clicks/keys
focus_roblox()
        
# ---- STARTUP ----

if g_toggle:
    w = avM.get_wave()

    # Only restart if we got a real valid wave number
    if isinstance(w, int) and w >= 1:
        avM.restart_match()

    # release potential stuck movement
    tap('w')
    tap('a')
    tap('s')
    tap('d')

    main()

else:
    while not g_toggle:
        time.sleep(1)

    # optional but recommended
    focus_roblox()

    w = avM.get_wave()

    if isinstance(w, int) and w >= 1:
        avM.restart_match()

    release('w')
    release('a')
    release('s')
    release('d')

    main()