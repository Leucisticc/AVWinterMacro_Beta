from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
import time
import pyautogui
import os
from datetime import datetime
from PIL import ImageDraw
from threading import Thread

# ---------- Settings ----------
SAVE_KEY   = "z"   # press Z to capture
STOP_KEY   = "n"   # press N to stop
SCROLL_KEY = "m"   # press M to run scroll test
UPGRADE_KEY= "u"   # press U to test upgrades
REGION_KEY = "y"   # press Y to draw region (drag mouse)
HOVER_KEY = "h"    # press H to get a live mouse HUD

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJECT_ROOT, "Resources", "debug_shots")
os.makedirs(OUT_DIR, exist_ok=True)

CROP_HALF = 20
ZOOM_SCALE = 6
HOVER_ON = False
RUNNING = True

# ---------- Region Drawer State ----------
_region_mouse_listener = None
_region_drawing = False
_region_start = None

def _region_fmt(a, b):
    x1, y1 = a
    x2, y2 = b
    left = min(x1, x2)
    top = min(y1, y2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    return (left, top, width, height)

def _region_on_click(x, y, button, pressed):
    global _region_drawing, _region_start, _region_mouse_listener

    # Use pyautogui coords to avoid pynput mismatch on mac
    px, py = pyautogui.position()

    if pressed:
        _region_drawing = True
        _region_start = (px, py)
        print(f"\n[REGION] start: {_region_start}")
    else:
        if _region_drawing and _region_start is not None:
            end = (px, py)
            region = _region_fmt(_region_start, end)
            print(f"[REGION] end:   {end}")
            print(f"[REGION] region=(left, top, width, height): {region}")
        _region_drawing = False
        _region_start = None

        # stop after one draw
        if _region_mouse_listener is not None:
            _region_mouse_listener.stop()
            _region_mouse_listener = None

def start_region_draw():
    global _region_mouse_listener
    if _region_mouse_listener is not None:
        return
    print("\n[REGION] Press and drag LEFT mouse. Release to print region.")
    _region_mouse_listener = pynput_mouse.Listener(on_click=_region_on_click)
    _region_mouse_listener.daemon = True
    _region_mouse_listener.start()

def cancel_region_draw():
    global _region_mouse_listener, _region_drawing, _region_start
    _region_drawing = False
    _region_start = None
    if _region_mouse_listener is not None:
        _region_mouse_listener.stop()
        _region_mouse_listener = None
    print("\n[REGION] cancelled")

# ---------- Helpers ----------
def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")

def rgb_to_hex(rgb):
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"

def get_scale(full_img):
    sw, sh = pyautogui.size()
    iw, ih = full_img.size
    return iw / sw, ih / sh

def sample_from_screenshot(full_img, x_pt, y_pt, sample_half=1):
    sx, sy = get_scale(full_img)
    x_px = int(x_pt * sx)
    y_px = int(y_pt * sy)

    w, h = full_img.size
    x_px = max(0, min(w - 1, x_px))
    y_px = max(0, min(h - 1, y_px))

    left = max(0, x_px - sample_half)
    top = max(0, y_px - sample_half)
    right = min(w - 1, x_px + sample_half)
    bottom = min(h - 1, y_px + sample_half)

    px = []
    for yy in range(top, bottom + 1):
        for xx in range(left, right + 1):
            p = full_img.getpixel((xx, yy))
            if isinstance(p, tuple) and len(p) >= 3:
                px.append((p[0], p[1], p[2]))

    if not px:
        return (0, 0, 0), (x_px, y_px), (sx, sy)

    rs = sorted(p[0] for p in px)
    gs = sorted(p[1] for p in px)
    bs = sorted(p[2] for p in px)
    mid = len(px) // 2
    return (rs[mid], gs[mid], bs[mid]), (x_px, y_px), (sx, sy)

def draw_cross(draw, x, y, size=25, width=3):
    draw.line((x - size, y, x + size, y), width=width)
    draw.line((x, y - size, x, y + size), width=width)

def click(x, y, delay=0.2):
    pyautogui.moveTo(x, y)
    time.sleep(delay)
    pyautogui.click()

def pixel_matches_seen(x, y, rgb, tol=50, sample_half=2):
    img = pyautogui.screenshot()
    r, g, b = img.getpixel((x, y))
    return (
        abs(r - rgb[0]) <= tol and
        abs(g - rgb[1]) <= tol and
        abs(b - rgb[2]) <= tol
    )

# ---------- Live Hover (console HUD) ----------
_last_hud = ""
def hud_loop():
    global _last_hud
    while RUNNING:
        if not HOVER_ON:
            time.sleep(0.1)
            continue

        try:
            x, y = pyautogui.position()
            img = pyautogui.screenshot()
            rgb, (xpx, ypx), (sx, sy) = sample_from_screenshot(img, x, y, sample_half=1)
            hx = rgb_to_hex(rgb)

            line = f"Mouse: ({x:4d},{y:4d}) | px: ({xpx:4d},{ypx:4d}) | RGB: {rgb} {hx} | scale: {sx:.2f},{sy:.2f}"
            if line != _last_hud:
                print("\r" + line + " " * 10, end="", flush=True)
                _last_hud = line
        except Exception as e:
            print(f"\n[HUD] error: {e}")

        time.sleep(0.05)

def toggle_hover():
    global HOVER_ON, _last_hud
    HOVER_ON = not HOVER_ON
    _last_hud = ""
    if HOVER_ON:
        print("\n[HUD] ON")
    else:
        print("\n[HUD] OFF")

# ---------- Capture ----------
def save_debug_images():
    t = ts()
    x_pt, y_pt = pyautogui.position()
    full_img = pyautogui.screenshot()
    rgb, (x_px, y_px), (sx, sy) = sample_from_screenshot(full_img, x_pt, y_pt, sample_half=2)
    hx = rgb_to_hex(rgb)

    full_annotated = full_img.copy()
    draw = ImageDraw.Draw(full_annotated)
    draw_cross(draw, x_px, y_px, size=30, width=4)

    full_path = os.path.join(OUT_DIR, f"full_{t}_pt({x_pt},{y_pt})_px({x_px},{y_px})_rgb{rgb}_{hx}.png")
    full_annotated.save(full_path)

    crop_half_px_x = int(CROP_HALF * sx)
    crop_half_px_y = int(CROP_HALF * sy)

    w, h = full_img.size
    left = max(0, x_px - crop_half_px_x)
    top = max(0, y_px - crop_half_px_y)
    right = min(w, x_px + crop_half_px_x)
    bottom = min(h, y_px + crop_half_px_y)

    crop = full_img.crop((left, top, right, bottom))
    crop_annotated = crop.copy()
    cdraw = ImageDraw.Draw(crop_annotated)
    cx = x_px - left
    cy = y_px - top
    draw_cross(cdraw, cx, cy, size=20, width=3)

    crop_path = os.path.join(OUT_DIR, f"crop_{t}_rgb{rgb}_{hx}.png")
    crop_annotated.save(crop_path)

    zoom = crop_annotated.resize((crop_annotated.size[0] * ZOOM_SCALE, crop_annotated.size[1] * ZOOM_SCALE))
    zoom_path = os.path.join(OUT_DIR, f"zoom_{t}_rgb{rgb}_{hx}.png")
    zoom.save(zoom_path)

    print("\n" + "-" * 60)
    print(f"Saved @ ({x_pt},{y_pt}) -> px ({x_px},{y_px})  RGB={rgb} {hx}  scale={sx:.2f},{sy:.2f}")
    print(f" Full: {full_path}")
    print(f" Crop: {crop_path}")
    print(f" Zoom: {zoom_path}")
    print("-" * 60)

def stop():
    global RUNNING
    RUNNING = False
    cancel_region_draw()
    print("\nStopping...")

def scroll_test():
    print("\nRunning scroll test...")
    for i in range(3):
        pyautogui.scroll(-1)
        print(f"Scroll step {i+1}/3")
        time.sleep(0.2)
    print("Scroll test done.")

# ---- Upgrade Testing ----
upgrade_step = 0

def run_next_upgrade():
    global upgrade_step
    print(f"\nRunning upgrade step {upgrade_step}")

    if upgrade_step == 0:
        pyautogui.moveTo(775, 500)
        time.sleep(0.2)
        click(959, 473, delay=0.2)
        time.sleep(0.8)
        click(1112, 309, delay=0.2)
        print("Fortune complete")

    elif upgrade_step == 1:
        pyautogui.moveTo(775, 500)
        time.sleep(0.2)
        for _ in range(6):
            pyautogui.scroll(-1)
            time.sleep(0.2)

        click(959, 635, delay=0.2)
        time.sleep(0.5)
        click(959, 635, delay=0.2)
        time.sleep(0.8)

        pyautogui.moveTo(775, 500)
        pyautogui.scroll(100)
        click(1112, 309, delay=0.2)
        print("Damage complete")

    elif upgrade_step == 2:
        pyautogui.moveTo(775, 500)
        time.sleep(0.2)
        for _ in range(3):
            pyautogui.scroll(-1)
            time.sleep(0.2)

        click(962, 621, delay=0.2)
        time.sleep(0.8)

        pyautogui.moveTo(775, 500)
        pyautogui.scroll(100)
        click(1112, 309, delay=0.2)
        print("Range complete")

    elif upgrade_step == 3:
        pyautogui.moveTo(775, 500)
        time.sleep(0.2)
        click(957, 635, delay=0.2)
        time.sleep(0.5)
        click(957, 635, delay=0.2)
        time.sleep(0.8)

        pyautogui.moveTo(775, 500)
        pyautogui.scroll(100)
        click(1112, 309, delay=0.2)
        print("Speed complete")

    elif upgrade_step == 4:
        pyautogui.moveTo(775, 500)
        time.sleep(0.2)
        for _ in range(9):
            pyautogui.scroll(-1)
            time.sleep(0.2)

        click(955, 635, delay=0.2)
        time.sleep(0.5)
        click(955, 635, delay=0.2)
        time.sleep(0.8)

        pyautogui.moveTo(775, 500)
        pyautogui.scroll(100)
        click(1112, 309, delay=0.2)
        print("Armor complete")

    upgrade_step += 1
    if upgrade_step > 4:
        upgrade_step = 0
        print("Cycle reset\n")

# ---------- Hotkeys ----------
def on_press(key):
    try:
        if hasattr(key, "char") and key.char:
            k = key.char.lower()
            if k == SAVE_KEY:
                save_debug_images()
            elif k == STOP_KEY:
                stop()
            elif k == SCROLL_KEY:
                scroll_test()
            elif k == UPGRADE_KEY:
                run_next_upgrade()
            elif k == REGION_KEY:
                # one-shot region draw; press Y again to cancel if needed
                if _region_mouse_listener is None:
                    start_region_draw()
                else:
                    cancel_region_draw()
            elif k == HOVER_KEY:
                toggle_hover()
    except Exception:
        pass

print("Mouse debug running.")
print("Hotkeys:\nZ = Capture\nM = Scroll test\nU = Next upgrade\nY = Draw region\nH = Turn HUD on\nN = Stop.")

listener = pynput_keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()

Thread(target=hud_loop, daemon=True).start()

while RUNNING:
    time.sleep(0.1)

print("Done.")
