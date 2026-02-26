import webhook
import time
import pyautogui
import sys
import os
import subprocess
import json

from Tools import botTools as bt
from Tools import winTools as wt
from Tools import avMethods as avM


from datetime import datetime
from threading import Thread
from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Controller
from pathlib import Path

class Cur_Settings: pass

global Settings
Settings = Cur_Settings()

Settings_Path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"Settings")
WE_Json = os.path.join(Settings_Path,"Winter_Event.json")

VERSION_N = '1.499b beta'
print(f"Version: {VERSION_N}")

CHECK_LOOTBOX = False # Leave false for faster runs

ROBLOX_PLACE_ID = 16146832113

PRIVATE_SERVER_CODE = "" # Not in settings so u dont accidently share ur ps lol

USE_KAGUYA = False # "its faster to lowkey not use kaguya lol" ~LoxerEx

USE_BUU = False #Best unit for highest curency gain

TAK_FINDER = False # turn off if it runs into a wall while trying to find tak

RUNS_BEFORE_REJOIN = 0 # 0 will make it so this doesnt happen, change it to what round u want it to restart

AINZ_SPELLS = False #Keep FALSE!

SLOT_ONE = (499, 150, 122, 110)
REG_SPEED = (495, 789, 570, 866)
REG_TAK = (495, 789, 570, 866)

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0
keyboard_controller = Controller()

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
    
Settings.Units_Placeable.append("Doom")

start = datetime.now()
if not USE_KAGUYA:
    Settings.Units_Placeable.remove("Kag")

# Session-only stats: reset counters every time this script starts.
reset_runtime_stats()

def kill():
    os._exit(0)


def on_press(key):
    try:
        if hasattr(key, "char") and key.char:
            if key.char.lower() == Settings.STOP_START_HOTKEY.lower():
                g_toggle()
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

# -------------------------
# Screenshot Capture and Pixel Detection (Mac Rendering Layer)
# -------------------------

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

def pixel_color_seen(x: int, y: int, sample_half: int = 1):
    img = _safe_screenshot()
    if img is None:
        return (0, 0, 0)
    return _seen_pixel_from_screenshot(img, x, y, sample_half=sample_half)

def pixel_matches_seen(x: int, y: int, rgb: tuple[int, int, int], tol: int = 20, sample_half: int = 1) -> bool:
    img = _safe_screenshot()
    if img is None:
        return False
    r, g, b = _seen_pixel_from_screenshot(img, x, y, sample_half=sample_half)
    return (abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol)

def wait_for_pixel(x: int,y: int,rgb: tuple[int, int, int],tol: int = 20,timeout: float = 10.0,interval: float = 0.1,sample_half: int = 1) -> bool:

    start = time.time()

    while time.time() - start < timeout:

        if pixel_matches_seen(x, y, rgb,tol=tol,sample_half=sample_half):
            return True

        time.sleep(interval)

    return False



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

# Wait for start screen
def wait_start(delay: int | None = None):
    i = 0
    if delay is None:
        delay = 1

    target = (99, 214, 63)

    while i < 90:
        i += 1
        try:
            seen = pixel_color_seen(816, 231, sample_half=2)  # 5x5 median
            # print(f"Looking for start screen: Seen = {seen}")
            print(f"Looking for start screen.")

            if pixel_matches_seen(816, 231, target, tol=35, sample_half=2) or bt.does_exist("VoteStart.png", confidence=0.7, grayscale=False):
                print("✅ Start screen detected")
                return True

        except Exception as e:
            print(f"e {e}")

        time.sleep(delay)

    print("❌ Start screen NOT detected (timeout)")
    return False


#Game mechanics

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
                    if bt.does_exist("Winter/LootBox.png",confidence=0.7,grayscale=True):
                        at_location = True
                    if  bt.does_exist("Winter/Full_Bar.png",confidence=0.7,grayscale=True):
                        at_location = True
                    if  bt.does_exist("Winter/NO_YEN.png",confidence=0.7,grayscale=True):
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
            print("At lootbox")

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
        return pixel_matches_seen(x, y, rgb, tol=tol, sample_half=sample_half)

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
            print("Fortune complete")


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
            scroll(100)
            click(1112, 309, delay =0.1)
            print("Damage complete")


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
            scroll(100)   
            click(1112, 309, delay =0.1)
            print("Range complete")


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
            scroll(100)
            click(1112, 309, delay =0.1)
            print("Speed complete")

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
            scroll(100)
            click(1112, 309, delay =0.1)
            print("Armor complete")



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
    attempts = 3

    # Wait until the “selected” UI pixel is white
    while not pixel_matches_seen(607, 381, (255, 255, 255), tol=25, sample_half=2) and attempts<=0:
        attempts -= 1
        print(f"Attempts to select: {attempts}")
        if bt.does_exist('Winter/Erza_Armor.png', confidence=0.8, grayscale=True):
            click(752, 548, delay =0.1)
            time.sleep(0.6)

        click(pos[0], pos[1], delay =0.1)
        time.sleep(0.8)

    print(f"Selected unit at {pos}")

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


def _retina_to_screen_coords(x: int, y: int) -> tuple[int, int]:
    """
    Convert locateOnScreen/screenshot pixel coords to OS screen coords on Retina displays.
    """
    img = _safe_screenshot()
    if img is None:
        return int(x), int(y)

    sw, sh = pyautogui.size()
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return int(x), int(y)

    scale_x = sw / iw
    scale_y = sh / ih
    return int(x * scale_x), int(y * scale_y)


def find_image_center(img_path: str, confidence: float = 0.8, grayscale: bool = False, region=None):
    """
    Returns (cx, cy, box) where box=(left, top, width, height), or (None, None, None) if not found.
    region is (left, top, width, height)
    """
    resolved_img_path = _resolve_image_path(img_path)
    try:
        box = pyautogui.locateOnScreen(
            resolved_img_path,
            confidence=confidence,
            grayscale=grayscale,
            region=region,
        )
    except Exception as e:
        # Some pyautogui/pyscreeze versions raise ImageNotFoundException instead of returning None.
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

    # Match botTools.click_image behavior on macOS Retina displays.
    cx, cy = _retina_to_screen_coords(cx, cy)

    ox, oy = offset if offset is not None else (0, 0)
    click(cx + int(ox), cy + int(oy), delay=delay, right_click=right_click)
    return True


def place_unit(unit: str, pos: tuple[int, int], close: bool | None = None, region: tuple | None = None):
    """
    Places a unit found in Winter/UNIT_hb.png at location given in pos.
    mac/Retina-safe: uses screenshot-based pixel checks.
    """

    # Tunables
    time_out = 20          # placement loop attempts
    time_out_2 = 50        # time to wait for hotbar icon to appear
    white_ui = (255, 255, 255)

    # 1) Wait for the unit icon to exist, then click it
    if region is None:
        while not bt.does_exist(f"Winter/{unit}_hb.png", confidence=0.8, grayscale=False):
            if time_out_2 <= 0:
                break
            time_out_2 -= 1
            time.sleep(0.1)
        click_image_center(f"Winter/{unit}_hb.png", confidence=0.8, grayscale=False, offset=(0, 0))
    else:
        while not bt.does_exist(f"Winter/{unit}_hb.png", confidence=0.8, grayscale=False, region=region):
            if time_out_2 <= 0:
                break
            time_out_2 -= 1
            time.sleep(0.1)
        click_image_center(f"Winter/{unit}_hb.png", confidence=0.8, grayscale=False, offset=(0, 0), region=region)

    time.sleep(0.2)

    # 2) Try to place it
    click(pos[0], pos[1], delay=0.67)
    time.sleep(0.5)

    # Keep attempting until the “close/back” pixel becomes white (means menu closed / placement done)
    while not pixel_matches_seen(607, 381, white_ui, tol=25, sample_half=2):
        time_out -= 1
        if time_out <= 0:
            print("timed out")
            break
        if not g_toggle:
            break

        click(pos[0], pos[1], delay=0.67)

        seen = pixel_color_seen(607, 381, sample_half=2)
        # print(f"Target Color: {white_ui}, seen: {seen}")

        time.sleep(0.1)
        tap('q')  # your “cancel/rotate/nudge” behaviour
        time.sleep(0.5)

        click(pos[0], pos[1], delay=0.1)
        time.sleep(1)

        # If the game shows “UnitExists” we’re done (unit placed)
        if bt.does_exist("Winter/UnitExists.png", confidence=0.9, grayscale=True):
            break

        # If we *now* see the UI pixel is white, also done
        if pixel_matches_seen(607, 381, white_ui, tol=25, sample_half=2):
            break

        # Re-click hotbar icon to re-arm placement if needed
        print("Retrying placement...")
        try:
            if region is None:
                click_image_center(f"Winter/{unit}_hb.png", confidence=0.8, grayscale=False, offset=(0, 0))
            else:
                click_image_center(f"Winter/{unit}_hb.png", confidence=0.8, grayscale=False, offset=(0, 0), region=region)
            time.sleep(0.2)
        except Exception as e:
            print(f"Error {e}")

        time.sleep(0.2)

    if close:
        click(607, 381, delay =0.1)

    print(f"Placed {unit} at {pos}")

def buy_monarch():  # this just presses e until it buys monarch, use after direction('5')
    monarch_region = (686, 606, 818, 646)
    e_delay = 0.4
    timeout = 3/e_delay
    tap('e')
    while not bt.does_exist('Winter/DetectArea.png',confidence=0.7,grayscale=True):
        if bt.does_exist('Winter/Monarch.png',confidence=0.7,grayscale=False):
            break
        if timeout < 0:
            quick_rts()
            directions('5')
            timeout = 3/e_delay
        timeout-=1
        tap('e')
        time.sleep(e_delay)
    print("Found area")
    while not bt.does_exist('Winter/Monarch.png',confidence=0.7,grayscale=False):
        if not g_toggle:
            break
        tap('e')
        time.sleep(0.8)
    print("Got monarch")

def place_hotbar_units():
    # Scans and places all units in your hotbar, tracking them too
    placing = True
    while placing:
        is_unit = False
        for unit in Settings.Units_Placeable:
            if bt.does_exist(f"Winter/{unit}_hb.png", confidence=0.8, grayscale=False):
                if unit != "Doom":
                    is_unit = True
                    unit_pos = Settings.Unit_Positions.get(unit)
                    index = Settings.Unit_Placements_Left.get(unit)-1
                    if index <0:
                        is_unit = False
                    print(f"Placing unit {unit} {index+1} at {unit_pos}")
                    place_unit(unit, unit_pos[index])
                    if unit == 'Kag':
                        if USE_KAGUYA:
                            kag_ability = [(645, 444), (743, 817), (1091, 244)]
                            for cl in kag_ability:
                                if cl == (743, 817):
                                    click_image_center("Winter/Kaguya_Auto.png", confidence=0.8, grayscale=False, offset=[0,0]) 
                                else:
                                    click(cl[0],cl[1],delay =0.1)
                                    time.sleep(1)
                else:
                    doom = (572, 560)
                    place_unit(unit,doom)
                    time.sleep(2)
                    set_boss()
                    tap('z')
                    click(607, 381, delay =0.1)
                    directions('5')
                    buy_monarch()
                    quick_rts()
                    click(doom[0],doom[1],delay =0.1)
                if unit != "Doom":
                    Settings.Unit_Placements_Left[unit]-=1
                    print(f"Placed {unit} | {unit} has {Settings.Unit_Placements_Left.get(unit)} placements left.")
                else:
                    print("Placed doom slayer.")
        if is_unit == False:
            click(600,380, delay =0.1)
            placing = False
            
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
    print("ran")
    time_out = 60/0.4
    click(Settings.REPLAY_BUTTON_POS[0],Settings.REPLAY_BUTTON_POS[1],delay =0.1)
    time.sleep(1)
    while bt.does_exist("Winter/DetectLoss.png",confidence=0.7,grayscale=True):
        if time_out<0:
            #on_disconnect()
            print("should disconnect")
        click(Settings.REPLAY_BUTTON_POS[0],Settings.REPLAY_BUTTON_POS[1],delay =0.1)
        print("Retrying...")
        time_out-=1
        time.sleep(0.4)
    click(Settings.REPLAY_BUTTON_POS[0],Settings.REPLAY_BUTTON_POS[1],delay =0.1)
    click(750, 567, delay = 0.5)
    

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


    while g_toggle:
        try:
            loss_found = bt.does_exist("Winter/DetectLoss.png", confidence=0.7, grayscale=True)
        except Exception as e:
            print(f"[detect_loss] does_exist error: {e}")
            loss_found = False

        if loss_found:
            print("Found loss screen")

            try:
                new_Data = load_json_data()
                if new_Data is None:
                    new_Data = {}
                new_Data.setdefault("num_runs", 0)
                new_Data.setdefault("losses", 0)
                new_Data.setdefault("wins", 0)
                new_Data["num_runs"] += 1
                new_Data["losses"] += 1
                new_Data["runtime"] = f"{str((datetime.now() - start)).split('.')[0]}"
                save_json_data(new_Data)
            except Exception as e:
                print(f"stats error: {e}")

            try:
                on_failure()
            except Exception as e:
                print(f"[detect_loss] on_failure error: {e}")

            while g_toggle:
                try:
                    still_loss = bt.does_exist("Winter/DetectLoss.png", confidence=0.7, grayscale=True)
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

def _roblox_window_screenshot_for_webhook():
    """
    Capture only the Roblox window for webhook screenshots.
    Returns PNG BytesIO or None (does not fall back to full screen).
    """
    try:
        roblox_window = wt.get_window("Roblox")
        if roblox_window is None:
            print("[Webhook] Roblox window not found, sending webhook without screenshot")
            return None
        return wt.screen_shot_memory(roblox_window)
    except Exception as e:
        print(f"[Webhook] Roblox window screenshot failed: {e}")
        return None

def main():
    rabbit_pos = Settings.Unit_Positions.get("mirko")
    speed_pos =  Settings.Unit_Positions.get("speedwagon")
    start_of_run = datetime.now()
    startup_stats = load_json_data() or {}
    startup_total = int(startup_stats.get("num_runs", 0) or 0)
    startup_wins = int(startup_stats.get("wins", 0) or 0)
    startup_losses = int(startup_stats.get("losses", 0) or 0)
    # print(f"[Stats] Starting totals | Runs: {startup_total} | Wins: {startup_wins} | Losses: {startup_losses}")
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
            },
            daemon=True,
        ).start()
    except Exception as e:
        print(f"[Webhook] Startup webhook error: {e}")
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
            
            print("Starting new match")
            wait_start()
            quick_rts()
            time.sleep(2)
            # Set up first 2 rabbits
            got_mirko = False
            while not got_mirko:
                directions('1', 'rabbit')
                tap('e')
                tap('e')
                quick_rts()
                time.sleep(1.5)
                got_mirko = True
                # if bt.does_exist("Winter/Bunny_hb.png",confidence=0.7,grayscale=False):
                #     print("Got mirko")
                #     got_mirko = True
                # else:
                #     print("Didnt detect mirko, retrying purchase")
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
                quick_rts()
                time.sleep(1.5)
                got_mirko_two = True
                # if bt.does_exist("Winter/Bunny_hb.png",confidence=0.7,grayscale=False):
                #     print("Got mirko")
                #     got_mirko_two = True
                # else:
                #     print("Didnt detect mirko, retrying purchase")
            place_unit('Bunny', rabbit_pos[2], close=True)
            
            #Start farms - speedwagon
            directions('2', 'speed')
            tap('e')
            tap('e')
            tap('e')
            
            
            
            place_unit('Speed', speed_pos[0], close=False)
            tap('z')
            place_unit('Speed', speed_pos[1], close=False)
            tap('z')
            place_unit('Speed', speed_pos[2], close=False)
            tap('z')
            click(607, 381, delay =0.1)
            
            # Tak's placement + max
            

            if bt.does_exist("Winter/Tak_Detect.png", confidence=0.7, grayscale=True):
                clicked = False

                # try up to 6 times (fast), then fall back
                for _ in range(6):
                    ok = click_image_center("Winter/Tak_Detect.png",confidence=0.7,grayscale=True,offset=(0, -20))
                    if ok:
                        clicked = True
                        break
                    time.sleep(0.15)

                if clicked:
                    click(50, 50, delay=0.1, right_click=True, dont_move=True)
                else:
                    print("[Tak_Detect] Saw image but click failed -> fallback movement")
                    press('w')
                    time.sleep(Settings.TAK_W_DELAY)
                    release('w')
            else:
                    print("[Tak_Detect] Saw image but click failed -> fallback movement")
                    press('w')
                    time.sleep(Settings.TAK_W_DELAY)
                    release('w')

            if TAK_FINDER:
                path_tak = False
                while not path_tak:
                    press('w')
                    time.sleep(0.1)
                    release('w')
                    tap('e')
                    time.sleep(0.4)
                    if bt.does_exist('Winter/TakDetect.png', confidence=0.7, grayscale=True,region=(581, 676, 958, 752)) or  bt.does_exist('Winter/Tak_hb.png', confidence=0.7, grayscale=False):
                        path_tak = True
                    time.sleep(0.5)
            # Press e until tak is bought
            while not bt.does_exist('Winter/Tak_hb.png', confidence=0.7, grayscale=False):
                tap('e')
                time.sleep(0.2)
            
            place_unit("Tak", Settings.Unit_Positions.get("tak"))
            tap('z')
            time.sleep(0.5)
            click(607, 381, delay =0.1)
            
            #DIR_NAMICARD
            if bt.does_exist("Winter/Nami_detect.png",confidence=0.8,grayscale=True):
                click_image_center("Winter/Nami_detect.png",confidence=0.8,grayscale=True,offset=(0,0))   
                click(50,50,delay=0.1,right_click=True,dont_move=True)
            else:
                click(Settings.CTM_NAMI_CARD[0], Settings.CTM_NAMI_CARD[1], delay =0.1, right_click=True) # Goes to nami's card
            time.sleep(2)
            #Nami
            while not bt.does_exist('Winter/Nami_hb.png', confidence=0.7, grayscale=False): # Buys nami's card
                tap('e')
                time.sleep(0.2)
            quick_rts()
            place_unit('Nami',(755, 524)) # Nami placement
            tap('z')
            click(607, 381, delay =0.1)

            # Go to upgrader for fortune
            directions('4')
            upgrader('fortune')
            click(1112, 312, delay =1)
            quick_rts()
            slow_rts()
            
            # Start auto upgrading first rabbit
            secure_select(rabbit_pos[0])
            time.sleep(0.5)
            tap('z')
            click(607, 381, delay =0.1)
            
            # get +100% dmg upgrade
            directions('4')
            upgrader('damage')
            click(1112, 312, delay =0.1)
            quick_rts()
            slow_rts()
            
            # Start auto upgrading rabbit 1 & 2
            secure_select(rabbit_pos[1])
            time.sleep(0.5)
            tap('z')
            click(607, 381, delay =0.1)
            time.sleep(1)
            secure_select(rabbit_pos[2])
            time.sleep(0.5)
            tap('z')
            click(607, 381, delay =0.1)
            time.sleep(1)
            
            # Get first monarch
            directions('5')
            buy_monarch()
            quick_rts()
            time.sleep(1)
            secure_select(rabbit_pos[0])
            
            # Wave 19 lane unlocks for 20% boost
            wave_19 = False

            while not wave_19 and g_toggle:
                w = avM.get_wave()
                print("Wave read:", w)
                
                # ✅ guard against None / unreadable values
                if w is None or w == -1:
                    time.sleep(0.5)
                    continue

                if w >= 19:
                    # DIR_BUYMAINLANES
                    press('d')
                    time.sleep(Settings.BUY_MAIN_LANE_DELAYS[0])
                    release('d')

                    tap('e'); tap('e')

                    press('w')
                    time.sleep(Settings.BUY_MAIN_LANE_DELAYS[1])
                    release('w')

                    tap('e'); tap('e')

                    wave_19 = True
                    break

                time.sleep(0.5)
    
            # Get 2nd and 3rd bunny monarch'd
            quick_rts()
            directions('5')
            buy_monarch()
            quick_rts()
            time.sleep(1)
            secure_select(rabbit_pos[1])
            time.sleep(1)
            directions('5')
            buy_monarch()
            quick_rts()
            time.sleep(1)
            secure_select(rabbit_pos[2])
            
            # Get all upgrades
            directions('4')
            upgrader('range')
            upgrader('speed')
            upgrader('armor')
            click(1112, 312, delay =0.1)
            quick_rts()
            slow_rts()
            directions('3')
            
            Ben_Upgraded = False
            Erza_Upgraded = False
            Gamer_Upgraded = False
            Kuzan_Upgraded = False
            
            # Lucky box
            gamble_done = False
            g_toggle= True
            ainzplaced=False
            prevent_inf = 5
            while not gamble_done:
                for i in range(50):
                    tap('e')
                    time.sleep(0.1)
                prevent_inf -= 1
                print(f"Prevent Inf: {prevent_inf}")
                
                full_bar = bt.does_exist("Winter/Full_Bar.png", confidence=0.7, grayscale=True)
                no_yen = bt.does_exist("Winter/NO_YEN.png", confidence=0.5, grayscale=True)

                if full_bar or no_yen or (prevent_inf <= 0):
                    prevent_inf = 5
                    print("Getting Units")
                    quick_rts()
                    time.sleep(3)
                    place_hotbar_units()
                    directions('3')
                if not Erza_Upgraded:
                    print("Buffing Erza")
                    erza_buffer = Settings.Unit_Positions['Mage']
                    if Settings.Unit_Placements_Left['Mage'] == 0:
                        quick_rts()
                        time.sleep(1)
                        # Buffer
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
                            
                        #Duelist 1
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
                        
                        #Duelist 2
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
                        # more gamble
                        directions('3')
                        
                if not Ben_Upgraded:
                    print("Upgrading Beni")
                    if Settings.Unit_Placements_Left['Beni'] == 0:
                        quick_rts()
                        time.sleep(1)
                        for ben in Settings.Unit_Positions['Beni']:
                            click(ben[0],ben[1],delay =0.1)
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
                        Ben_Upgraded = True
                        # more gamble
                        directions('3')
                        
                if not Gamer_Upgraded:
                    print("Upgrading Hero")
                    if Settings.Unit_Placements_Left['Hero'] == 0:
                        quick_rts()
                        time.sleep(1)
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
                        Gamer_Upgraded = True
                        # more gamble
                        directions('3')
                        
                if not Kuzan_Upgraded:
                    print("Upgrading Kuzan")
                    if Settings.Unit_Placements_Left['Kuzan'] == 0:
                        quick_rts()
                        time.sleep(1)
                        for kuzan in Settings.Unit_Positions['Kuzan']:
                            click(kuzan[0],kuzan[1],delay =0.1)
                            secure_select((kuzan[0],kuzan[1]))
                            time.sleep(0.5)
                            tap('z')
                            set_boss()
                            time.sleep(0.5)
                            click(607, 381, delay =0.1)
                            directions('5')
                            buy_monarch()
                            quick_rts()
                            time.sleep(0.5)
                            secure_select((kuzan[0],kuzan[1]))
                            time.sleep(0.5)
                            click(607, 381, delay =0.1)
                        Kuzan_Upgraded = True
                        # more gamble
                        directions('3')
                        
                if not ainzplaced:
                    if Settings.Unit_Placements_Left['Ainz'] == 0: # Ainz thingy
                        print("Ainz Setup")
                        ainzplaced = True
                        quick_rts()
                        time.sleep(1)
                        ainz_pos = Settings.Unit_Positions['Ainz']
                        pos = Settings.Unit_Positions.get("Caloric_Unit")
                        secure_select((ainz_pos[0]))
                        time.sleep(0.5)
                        if Settings.USE_WD == True:
                            ainz_setup(unit="world des")
                        elif Settings.USE_DIO == True:
                            ainz_setup(unit="god")
                        elif USE_BUU:
                            ainz_setup(unit="boo")
                        else:
                            ainz_setup(unit=Settings.USE_AINZ_UNIT)
                        global AINZ_SPELLS
                        if not AINZ_SPELLS:
                            AINZ_SPELLS = True
                        click(pos[0], pos[1], delay=0.67) # Place world destroyer
                        time.sleep(0.5)
                        while not pixel_matches_seen(607, 381, (255, 255, 255), tol=20, sample_half=2):
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
                        
                        # Ainz auto upgrade + monarch
                        secure_select((ainz_pos[0]))
                        time.sleep(0.5)
                        tap('z')
                        time.sleep(0.5)
                        click(607, 381, delay =0.1)
                        directions('5')
                        buy_monarch()
                        quick_rts()
                        time.sleep(1)
                        click(ainz_pos[0][0],ainz_pos[0][1],delay =0.1)
                        time.sleep(1)
                        # go gamble more son
                        directions('3')
                print("===============================")
                is_done = True
                for unit in Settings.Units_Placeable:
                    if unit != "Doom":
                        if Settings.Unit_Placements_Left[unit] > 0:
                            is_done = False
                            print(f"{unit} has {Settings.Unit_Placements_Left[unit]} placements left.")
                print("===============================")
                if is_done:
                    gamble_done = True
                time.sleep(0.1)
            print("Gambling done")
             
               

            # Auto upgrade + Monarch everything else
            
            # set up buffer erza
            
            quick_rts()
            time.sleep(1)
    
            # World destroyer
            if Settings.USE_WD:
                secure_select(Settings.Unit_Positions.get("Caloric_Unit"))
                time.sleep(1)
                while True:
                    print("Upgrading")
                    if bt.does_exist("Winter/StopWD.png",confidence=0.8,grayscale=False):
                        print("Stop")
                        break
                    if bt.does_exist("Unit_Maxed.png",confidence=0.8,grayscale=False):
                        print("Stop, maxed on accident")
                        break
                    tap('t') #Upgrade Hotkey
                    time.sleep(0.5)
                time.sleep(0.5)
                click(607, 381, delay =0.1)
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
                while True:
                    if bt.does_exist("Winter/StopUpgradeRukia.png",confidence=0.8,grayscale=True):
                        print("Stop")
                        break
                    if bt.does_exist("Unit_Maxed.png",confidence=0.8,grayscale=False):
                        print("Stop, maxed on accident")
                        break
                    tap('t')
                    time.sleep(0.5)
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

                    # Run once on confirmed wave 149
                    if (not done_path) and w == 148:
                        print("Confirmed wave 148 — running pre-150 logic")
                        time.sleep(2)
                        quick_rts()

                        tap('f')  # Unit Manager Hotkey
                        time.sleep(0.7)

                        ok = click_image_center("Winter/LookDownFinder.png",confidence=0.8,grayscale=False,offset=(0, -50))
                        print("[LookDownFinder click] ok =", ok)

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
                    if w == 140:
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
                    victory = _roblox_window_screenshot_for_webhook()
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

# Loss Detector
Thread(target=detect_loss, daemon=True).start()

# Auto-start logic stays the same
if Settings.AUTO_START:
    if "--stopped" not in sys.argv:
        g_toggle = True
    else:
        print("Program was STOPPED, won't auto start")

for z in range(3):
    print(f"Starting in {3 - z}")
    time.sleep(1)

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
