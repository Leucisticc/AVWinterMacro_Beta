"""
Mouse Debug Tool
─────────────────────────────────────────────────
Z   Capture position + color
H   Toggle cursor HUD (floating, follows mouse)
Y   Region selection (click + drag overlay)
M   Scroll test
U   Next upgrade step
K   Stop
─────────────────────────────────────────────────
"""

import os
import time
import pyautogui
from datetime import datetime
from PIL import ImageDraw
from threading import Thread, Lock
import tkinter as tk

from pynput import keyboard as pynput_keyboard

# ─── Config ───────────────────────────────────────────────────────────────────
SAVE_KEY    = "z"
STOP_KEY    = "k"
SCROLL_KEY  = "m"
UPGRADE_KEY = "u"
REGION_KEY  = "y"
HOVER_KEY   = "h"

SAVE_DEBUG_IMAGES_ENABLED = False
CROP_HALF  = 20
ZOOM_SCALE = 6

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJECT_ROOT, "Resources", "debug_shots")
os.makedirs(OUT_DIR, exist_ok=True)

_SEP  = "─" * 50
_SEP2 = "═" * 50


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _ts():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")


def _rgb_hex(rgb):
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _backing_scale(img):
    sw, sh = pyautogui.size()
    return img.size[0] / sw, img.size[1] / sh


def _sample_color(img, x_pt, y_pt, half=1):
    sx, sy = _backing_scale(img)
    xpx = max(0, min(img.size[0] - 1, int(x_pt * sx)))
    ypx = max(0, min(img.size[1] - 1, int(y_pt * sy)))
    samples = []
    for yy in range(max(0, ypx - half), min(img.size[1] - 1, ypx + half) + 1):
        for xx in range(max(0, xpx - half), min(img.size[0] - 1, xpx + half) + 1):
            p = img.getpixel((xx, yy))
            if isinstance(p, tuple) and len(p) >= 3:
                samples.append(p[:3])
    if not samples:
        return (0, 0, 0), xpx, ypx, sx
    mid = len(samples) // 2
    r = sorted(s[0] for s in samples)[mid]
    g = sorted(s[1] for s in samples)[mid]
    b = sorted(s[2] for s in samples)[mid]
    return (r, g, b), xpx, ypx, sx


def _draw_cross(draw, x, y, size=25, width=3):
    draw.line((x - size, y, x + size, y), width=width)
    draw.line((x, y - size, x, y + size), width=width)


def click(x, y, delay=0.2):
    pyautogui.moveTo(x, y)
    time.sleep(delay)
    pyautogui.click()


def pixel_matches(x, y, rgb, tol=50, half=2):
    """Returns True if the pixel at (x, y) is within `tol` of `rgb`."""
    img = pyautogui.screenshot()
    s, _, _, _ = _sample_color(img, x, y, half=half)
    return all(abs(s[i] - rgb[i]) <= tol for i in range(3))


# ─── Floating HUD ─────────────────────────────────────────────────────────────
class FloatingHUD:
    _W   = 238
    _H   = 126
    _OFF = 28

    def __init__(self, root):
        self.root    = root
        self.visible = False
        self._lock   = Lock()
        self._data   = {}

        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        win.wm_attributes("-alpha", 0.92)
        win.configure(bg="#0e0e1c")
        win.withdraw()
        self._win = win

        self._lbl = tk.Label(
            win, bg="#0e0e1c", fg="#d0d8ff",
            font=("Menlo", 11), justify="left",
            padx=12, pady=10,
        )
        self._lbl.pack()

        Thread(target=self._sampler, daemon=True).start()

    def _sampler(self):
        """Samples color in background every 220 ms to avoid blocking the UI."""
        while True:
            time.sleep(0.22)
            if not self.visible:
                continue
            try:
                x, y = pyautogui.position()
                img  = pyautogui.screenshot()
                rgb, xpx, ypx, sx = _sample_color(img, x, y)
                with self._lock:
                    self._data = dict(
                        x=x, y=y, rgb=rgb,
                        hex=_rgb_hex(rgb),
                        xpx=xpx, ypx=ypx, sx=sx,
                    )
            except Exception:
                pass

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self._win.deiconify()
            print(f"\n  [H]  Cursor HUD on")
        else:
            self._win.withdraw()
            print(f"\n  [H]  Cursor HUD off")

    def update(self):
        if not self.visible:
            return
        try:
            x, y = pyautogui.position()
            with self._lock:
                d = dict(self._data)

            rgb = d.get("rgb", (0, 0, 0))
            hx  = d.get("hex", "#000000")
            xpx = d.get("xpx", 0)
            ypx = d.get("ypx", 0)
            sx  = d.get("sx", 1.0)

            self._lbl.config(text=(
                f"  Position   {x}, {y}\n"
                f"  Pixel      {xpx}, {ypx}\n"
                f"  RGB        {rgb[0]}, {rgb[1]}, {rgb[2]}\n"
                f"  Hex        {hx}\n"
                f"  Scale      {sx:.2f}x"
            ))

            sw, sh = pyautogui.size()
            o  = self._OFF
            wx = x + o if x + o + self._W < sw else x - self._W - o
            wy = y + o if y + o + self._H < sh else y - self._H - o
            self._win.geometry(f"+{wx}+{wy}")
            self._win.wm_attributes("-topmost", True)
            self._win.lift()
        except Exception:
            pass


# ─── Region Overlay ───────────────────────────────────────────────────────────
class RegionOverlay:
    _ALPHA   = 0.18
    _FILL    = "#4488ff"
    _OUTLINE = "#88ccff"

    def __init__(self, root):
        self.root   = root
        self.active = False
        self._win   = None
        self._cnv   = None
        self._rect  = None
        self._start = None
        self._ox    = 0
        self._oy    = 0

    def toggle(self):
        if self.active:
            self._close()
        else:
            self._open()

    def _open(self):
        self.active = True
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        win.wm_attributes("-alpha", self._ALPHA)
        win.configure(bg="black")
        win.geometry(f"{sw}x{sh}+0+0")
        win.update()
        self._ox  = win.winfo_rootx()
        self._oy  = win.winfo_rooty()
        self._win = win

        cnv = tk.Canvas(
            win, width=sw, height=sh,
            bg="black", highlightthickness=0, cursor="crosshair",
        )
        cnv.pack()
        cnv.bind("<Button-1>",        self._press)
        cnv.bind("<B1-Motion>",       self._drag)
        cnv.bind("<ButtonRelease-1>", self._release)
        cnv.bind("<Escape>",          lambda _: self._close())
        cnv.focus_set()
        self._cnv = cnv

        print(f"\n{_SEP}")
        print("  Region Selection")
        print("  Click and drag to draw a region.")
        print("  Release to confirm.  Esc to cancel.")
        print(_SEP)

    def _press(self, e):
        self._start = (e.x, e.y)

    def _drag(self, e):
        if self._start is None:
            return
        if self._rect:
            self._cnv.delete(self._rect)
        sx, sy = self._start
        self._rect = self._cnv.create_rectangle(
            sx, sy, e.x, e.y,
            outline=self._OUTLINE, width=2,
            fill=self._FILL, stipple="gray25",
        )

    def _release(self, e):
        if self._start is None:
            return
        x1 = self._start[0] + self._ox
        y1 = self._start[1] + self._oy
        x2 = e.x + self._ox
        y2 = e.y + self._oy
        l = min(x1, x2);  t = min(y1, y2)
        w = abs(x2 - x1); h = abs(y2 - y1)
        print(f"\n{_SEP}")
        print("  Region Result")
        print(f"  Coords     left={l}  top={t}  width={w}  height={h}")
        print(f"  Code       _r({l}, {t}, {w}, {h})")
        print(_SEP)
        self._close()

    def _close(self):
        self.active = False
        self._start = None
        if self._win:
            self._win.destroy()
            self._win = None
        self._cnv = self._rect = None

# ─── Capture ─────────────────────────────────────────────────────────────────
def capture():
    x, y = pyautogui.position()
    img  = pyautogui.screenshot()
    rgb, xpx, ypx, sx = _sample_color(img, x, y, half=2)
    hx = _rgb_hex(rgb)

    print(f"\n{_SEP}")
    print("  Capture")
    print(f"  Position   ({x}, {y})")
    # print(f"  Position   ({x}, {y})  ->  pixel ({xpx}, {ypx})")
    print(f"  Color      RGB ({rgb[0]}, {rgb[1]}, {rgb[2]})   {hx}")
    print(f"  Scale      {sx:.2f}x")

    if not SAVE_DEBUG_IMAGES_ENABLED:
        print("  Images     disabled  (set SAVE_DEBUG_IMAGES_ENABLED = True to save)")
        print(_SEP)
        return

    t   = _ts()
    iw, ih = img.size
    chx = int(CROP_HALF * sx)
    chy = int(CROP_HALF * sx)

    full = img.copy()
    _draw_cross(ImageDraw.Draw(full), xpx, ypx, size=30, width=4)
    full_path = os.path.join(OUT_DIR, f"full_{t}_pt({x},{y})_{hx}.png")
    full.save(full_path)

    cl = max(0, xpx - chx);  cr = min(iw, xpx + chx)
    ct = max(0, ypx - chy);  cb = min(ih, ypx + chy)
    crop = img.crop((cl, ct, cr, cb)).copy()
    _draw_cross(ImageDraw.Draw(crop), xpx - cl, ypx - ct)
    crop.save(os.path.join(OUT_DIR, f"crop_{t}_{hx}.png"))
    crop.resize((crop.size[0] * ZOOM_SCALE, crop.size[1] * ZOOM_SCALE)).save(
        os.path.join(OUT_DIR, f"zoom_{t}_{hx}.png")
    )
    print(f"  Saved      {os.path.basename(full_path)}")
    print(_SEP)


# ─── Scroll Test ──────────────────────────────────────────────────────────────
def scroll_test():
    print(f"\n{_SEP}")
    print("  Scroll Test")
    for i in range(3):
        pyautogui.scroll(-1)
        print(f"  Step {i + 1} / 3")
        time.sleep(0.2)
    print("  Done.")
    print(_SEP)


# ─── Upgrade Test ─────────────────────────────────────────────────────────────
_upgrade_step = 0


def run_next_upgrade():
    global _upgrade_step
    s = _upgrade_step

    def _mv(x, y):
        pyautogui.moveTo(x, y)
        time.sleep(0.2)

    print(f"\n{_SEP}")
    print(f"  Upgrade Step {s}")

    if s == 0:
        _mv(775, 500)
        click(959, 473); time.sleep(0.8); click(1112, 309)
        print("  Fortune    done")
    elif s == 1:
        _mv(775, 500)
        for _ in range(6):
            pyautogui.scroll(-1)
            time.sleep(0.2)
        click(959, 635); time.sleep(0.5); click(959, 635); time.sleep(0.8)
        _mv(775, 500); pyautogui.scroll(100); click(1112, 309)
        print("  Damage     done")
    elif s == 2:
        _mv(775, 500)
        for _ in range(3):
            pyautogui.scroll(-1)
            time.sleep(0.2)
        click(962, 621); time.sleep(0.8)
        _mv(775, 500); pyautogui.scroll(100); click(1112, 309)
        print("  Range      done")
    elif s == 3:
        _mv(775, 500)
        click(957, 635); time.sleep(0.5); click(957, 635); time.sleep(0.8)
        _mv(775, 500); pyautogui.scroll(100); click(1112, 309)
        print("  Speed      done")
    elif s == 4:
        _mv(775, 500)
        for _ in range(9):
            pyautogui.scroll(-1)
            time.sleep(0.2)
        click(955, 635); time.sleep(0.5); click(955, 635); time.sleep(0.8)
        _mv(775, 500); pyautogui.scroll(100); click(1112, 309)
        print("  Armor      done")

    _upgrade_step = (s + 1) % 5
    if _upgrade_step == 0:
        print("  Cycle reset.")
    print(_SEP)


# ─── Stop ─────────────────────────────────────────────────────────────────────
def stop():
    print(f"\n{_SEP}\n  Stopped.\n{_SEP}\n")
    root.destroy()


# ─── Keyboard ─────────────────────────────────────────────────────────────────
def on_press(key):
    try:
        k = key.char.lower() if hasattr(key, "char") and key.char else ""
        if   k == SAVE_KEY:    Thread(target=capture,          daemon=True).start()
        elif k == STOP_KEY:    root.after(0, stop)
        elif k == SCROLL_KEY:  Thread(target=scroll_test,      daemon=True).start()
        elif k == UPGRADE_KEY: Thread(target=run_next_upgrade,  daemon=True).start()
        elif k == REGION_KEY:  root.after(0, overlay.toggle)
        elif k == HOVER_KEY:   root.after(0, hud.toggle)
    except Exception:
        pass


# ─── Main ─────────────────────────────────────────────────────────────────────
def _tick():
    hud.update()
    root.after(40, _tick)


root    = tk.Tk()
root.withdraw()
hud     = FloatingHUD(root)
overlay = RegionOverlay(root)

print(f"\n{_SEP2}")
print("  Mouse Debug Tool")
print(_SEP2)
print(f"  {'Z':<4}  Capture position + color to console")
print(f"  {'H':<4}  Cursor HUD  (floating window, follows mouse)")
print(f"  {'Y':<4}  Region selection  (click + drag overlay)")
print(f"  {'M':<4}  Scroll test")
print(f"  {'U':<4}  Next upgrade step")
print(f"  {'K':<4}  Stop")
print(f"{_SEP2}\n")

pynput_keyboard.Listener(on_press=on_press, daemon=True).start()

root.after(40, _tick)
root.mainloop()
print("Done.")
