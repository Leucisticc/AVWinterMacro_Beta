import time
import pyautogui
import os
import webhook
import subprocess
from datetime import datetime
from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Controller
from Tools import botTools as bt
from Tools import winTools as wt
from Tools import avMethods as avM

# ================ TEAM COMPOSITION ================ #
# Ichigo, Sakura, Skele, Rukia, Aki, Gohan
# ================================================== #

TEAM = 2


RUNS_BEFORE_REJOIN = 250


GEMS_PER_WIN = 150
VOTE_START_POS = (840,228)
CLOSE_POS = (602,380)
FOCUS_BOSS = (252,573)
ABILITY_POS = (645,450)
ABILITY_POS_2 = (645, 520)
REPLAY_POS = (590,710) #(697,712)
REPLAY_IMG = "Replay.png"

#520, 615, 710, 800, 895, 985
if TEAM == 1:
    UNITS = {
        "hb1": {"name": "Ichigo", "hotbar": (520, 826), "pos": (682, 512)},
        "hb2": {"name": "Sakura", "hotbar": (615, 826), "pos": (711, 537)},
        "hb3": {"name": "Skele", "hotbar": (710, 826), "pos": (605, 509)},
        "hb4": {"name": "Rukia", "hotbar": (800, 826), "pos": (639, 373)},
        "hb5": {"name": "Aki", "hotbar": (895, 826), "pos": (688, 546)},
    }
elif TEAM == 2:
    UNITS = {
        "hb1": {"name": "Ichigo", "hotbar": (520, 826), "pos": (682, 512)},
        "hb2": {"name": "Sakura", "hotbar": (615, 826), "pos": (711, 537)},
        "hb3": {"name": "Skele", "hotbar": (710, 826), "pos": (605, 509)},
        "hb4": {"name": "Alucard", "hotbar": (800, 826), "pos": (639, 373)},
        "hb5": {"name": "Aki", "hotbar": (895, 826), "pos": (688, 546)},
        "hb6": {"name": "Future Gohan", "hotbar": (895, 826), "pos": (688, 546)},
    }
print(f"Team {TEAM} selected: {UNITS['hb1']['name']}, {UNITS['hb2']['name']}, {UNITS['hb3']['name']}, {UNITS['hb4']['name']}, {UNITS['hb5']['name']}, {UNITS['hb6']['name']}")

failed_runs = 0
failed_matches = 0

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

def pixel_color_seen(x: int, y: int, sample_half: int = 1):
    """
    Return the RGB color seen at a pyautogui point using the same
    coordinate-to-screenshot scaling and median sampling as mouseDebugging.
    """
    img = _safe_screenshot()
    if img is None:
        return None
    return _seen_pixel_from_screenshot(img, x, y, sample_half=sample_half)

def pixel_matches_seen(x: int, y: int, rgb: tuple[int, int, int], tol: int = 20, sample_half: int = 1) -> bool:
    seen = pixel_color_seen(x, y, sample_half=sample_half)
    if seen is None:
        return False
    r, g, b = seen
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
    

def place_unit(unit, click_delay=0.4, step_delay=0.02,close=False):
    click(unit["hotbar"], delay=click_delay)
    time.sleep(step_delay)
    click(unit["pos"], delay=click_delay)
    time.sleep(step_delay)
    if close:
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

            # if bt.does_exist("VoteStart.png", confidence=0.7, grayscale=False, region=(767, 189, 127,83)): 
            if bt.does_exist("VoteStart.png", confidence=0.7, grayscale=False, region=(802, 211, 77, 37)): 
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

    # print("❌ Start screen NOT detected (timeout)")

def set_up_raid():
    wait_start()
    print("Setting up Raid.")
    click(398,160,delay=0.5)
    time.sleep(1)
    click(398,160,delay=0.5)
    time.sleep(1)
    # click(438,532,delay=0.5)
    click(482,462,delay=0.5) #Close objectives
    time.sleep(1)
    click(VOTE_START_POS)
    time.sleep(0.5)
    place_unit(UNITS["setup"])
    time.sleep(1)
    click(399,401,delay=0.5)
    time.sleep(1)
    click(646,781,delay=0.5)
    time.sleep(1)
    click(749,874,delay=0.5)
    time.sleep(1)
    tap('o',hold=1.5)
    time.sleep(0.5)
    quick_rts()
    time.sleep(0.5)
    avM.restart_match()

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

def go_to_raid():
    print("Walking to raid.")
    time.sleep(1)
    click(311,487,delay=1)
    time.sleep(1)
    click(652,638,delay=0.5)
    time.sleep(2)
    click(652,638,delay=0.5)
    # click(469,563,right_click=True,delay=5)
    tap('w', hold=3)
    tap('a',hold=5)
    time.sleep(1)
    click(312,459,delay=0.5)
    time.sleep(1)
    click(312,459,delay=0.5)
    time.sleep(1)
    click(412,493,delay=0.5)
    time.sleep(1)
    click(620,425,delay=0.5)
    time.sleep(1)
    click(809,716,delay=0.5)
    time.sleep(1)
    click(286,735,delay=0.5)
    
def rejoin_raid(total_runs):
    go_to_lobby()
    go_to_raid()
    set_up_raid()
    return 0

def enable_auto_start():
    print("Enabling Auto Start")
    click(1184,293,delay=0.2)
    time.sleep(1)
    click(220,879,delay=0.2)
    time.sleep(1)
    if pixel_matches_seen(1180,587,(33,15,24),tol=20):
        click(1180,587,delay=0.2)
        time.sleep(1)
        print("Enabled.")
    else:
        print("Already enabled.")
    click(1223,269,delay=0.2)
    time.sleep(1)
    click(750,286,delay=0.2)

def critical_failure():
    click(100,100)
def wait_end(total_runs, delay: float = 0.5, timeout: float = 15.0):
    global failed_runs
    global failed_matches
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            if bt.does_exist("Victory.png", confidence=0.7, grayscale=False, region=(380,257,120,55)): #Won
                print("✅ Win detected")
                failed_runs = 0
                return "win", total_runs
            elif bt.does_exist("Failed.png",confidence=0.7, grayscale=False, region=(380,257,120,55)): #Failed
                print("❌ Failure detected")
                failed_runs+=1
                if failed_runs>=2:
                    failed_matches+=1
                    failed_runs = 0
                    if failed_matches>=2:
                        kill()
                    else:
                        total_runs = rejoin_raid(total_runs)
                return "fail", total_runs
        except Exception as e:
            print(f"replay detect error: {e}")
        time.sleep(delay)
    print("❌ Replay button NOT detected (timeout)")
    critical_failure()
    return "timeout", total_runs

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
    rewards = wins * GEMS_PER_WIN
    screenshot = _roblox_window_screenshot_for_webhook()
    webhook.send_webhook(
        run_time=runtime,
        task_name="Cid Act 2",
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
    
def cid_farm():
    print("Starting Cid Macro.")
    print("Press K to stop.")
    time.sleep(0.5)
    focus_roblox()
    time.sleep(0.2)
    ensure_roblox_window_positioned()

    while not avM.get_wave() == 0:
        avM.restart_match()
    session_start = datetime.now()
    total_runs = 0
    wins = 0
    losses = 0
    while True:
        click(REPLAY_POS)
        time.sleep(0.2)
        if total_runs>= RUNS_BEFORE_REJOIN:
            total_runs = rejoin_raid(total_runs)
        if total_runs == 0:
            wait_start()
            quick_rts()
            time.sleep(0.5)
            click(523,544,right_click=True,delay=0.5)
            time.sleep(2)
            click(VOTE_START_POS)
        time.sleep(0.2)
        place_unit(UNITS["hb3"])
        time.sleep(3.6)
        place_unit(UNITS["hb1"])
        time.sleep(2.5)
        place_unit(UNITS["hb5"])
        time.sleep(0.1)
        place_unit(UNITS["hb2"])
        time.sleep(0.2)
        click(ABILITY_POS, delay=0.2)
        time.sleep(0.2)
        click(UNITS["hb5"]["pos"])
        time.sleep(0.2)
        click(UNITS["hb2"]["pos"])
        time.sleep(0.2)
        click(ABILITY_POS, delay=0.2)
        time.sleep(0.2)
        click(UNITS["hb1"]["pos"])
        time.sleep(0.2)
        click(UNITS["hb2"]["pos"])
        time.sleep(0.3)
        tap('x')
        time.sleep(0.2)
        click(UNITS["hb1"]["pos"])
        time.sleep(0.3)
        for i in range(2):
            tap('r')
            time.sleep(0.2)
        time.sleep(6)
        for i in range(2):
            tap('x')
            time.sleep(0.2)
        click(CLOSE_POS)
        time.sleep(3)
        # place_unit(UNITS["hb4"], close=True)
        # time.sleep(0.3)
        click(UNITS["hb3"]["pos"])
        time.sleep(1.5)
        click(ABILITY_POS_2, delay=0.2)
        time.sleep(0.2)
        click(ABILITY_POS_2, delay=0.2)
        end_state, total_runs = wait_end(total_runs)
        if end_state == "win":
            if total_runs==0:
                enable_auto_start()
            wins += 1
            total_runs += 1
            send_run_webhook(session_start=session_start, wins=wins, losses=losses)
            print(f"Runs: {wins+losses} | Wins: {wins} | Losses: {losses} | Runtime: {str(datetime.now() - session_start).split('.')[0]} | Rewards: {wins * GEMS_PER_WIN:,}")
        elif end_state == "fail":
            losses += 1
            total_runs += 1
            send_run_webhook(
                session_start=session_start,
                wins=wins,
                losses=losses,
                alert_text=f"@everyone Cid Act 2 lost a run. Total losses: {losses}",
            )
            print("Run failed; wins not incremented.")
        else:
            print("Replay not detected; skipping win stat update for this cycle.") 
        # Loop again from wait_start() on next iteration.
        continue

def cid_farm2():
    print("Starting Cid Macro.")
    print("Press K to stop.")
    time.sleep(0.5)
    focus_roblox()
    time.sleep(0.2)
    ensure_roblox_window_positioned()

    while not avM.get_wave() == 0:
        avM.restart_match()
    session_start = datetime.now()
    total_runs = 0
    wins = 0
    losses = 0
    while True:
        click(REPLAY_POS)
        time.sleep(0.2)
        if total_runs>= RUNS_BEFORE_REJOIN:
            total_runs = rejoin_raid(total_runs)
        if total_runs == 0:
            wait_start()
            quick_rts()
            time.sleep(0.5)
            click(523,544,right_click=True,delay=0.5)
            time.sleep(2)
            click(VOTE_START_POS)
        time.sleep(0.2)
        place_unit(UNITS["hb3"])
        time.sleep(3.4)
        place_unit(UNITS["hb1"])
        time.sleep(2.6)
        # while pixel_matches_seen(*UNITS["hb5"]["hotbar"], (35, 35, 35), tol=20, sample_half=0):
        #     time.sleep(0.1)
        place_unit(UNITS["hb5"])
        time.sleep(0.1)
        place_unit(UNITS["hb2"])
        time.sleep(0.1)
        click(ABILITY_POS, delay=0.2)
        time.sleep(0.1)
        click(UNITS["hb5"]["pos"])
        time.sleep(0.1)
        click(UNITS["hb2"]["pos"])
        time.sleep(0.1)
        click(ABILITY_POS, delay=0.2)
        time.sleep(0.1)
        click(UNITS["hb1"]["pos"])
        time.sleep(0.1)
        click(UNITS["hb2"]["pos"])
        time.sleep(0.3)
        tap('x')
        time.sleep(0.2)
        click(UNITS["hb1"]["pos"])
        time.sleep(0.3)
        for i in range(2):
            tap('r')
            time.sleep(0.2)
        time.sleep(0.2)
        for i in range(2):
            tap('x')
            time.sleep(0.2)
        while bt.does_exist("Cid_Health.png", confidence=0.7, grayscale=False, region=(555,235,125,27)):
            time.sleep(0.1)
        time.sleep(0.2)
        click(CLOSE_POS)
        while pixel_matches_seen(*UNITS["hb4"]["hotbar"], (35, 35, 35), tol=20, sample_half=0):
            time.sleep(0.1)
        place_unit(UNITS["hb4"], click_delay=0.6, step_delay=0.15, close=True)
        time.sleep(0.5)
        click(UNITS["hb3"]["pos"])
        time.sleep(0.4)
        for i in range(4):
            click(ABILITY_POS_2, delay=0.2)
            time.sleep(0.1)
        # while avM.get_wave() >= 2:
        #     click(ABILITY_POS_2, delay=0.2)
        #     time.sleep(0.2)
        end_state, total_runs = wait_end(total_runs)
        if end_state == "win":
            if total_runs==0:
                enable_auto_start()
            wins += 1
            total_runs += 1
            send_run_webhook(session_start=session_start, wins=wins, losses=losses)
            print(f"Runs: {wins+losses} | Wins: {wins} | Losses: {losses} | Runtime: {str(datetime.now() - session_start).split('.')[0]} | Rewards: {wins * GEMS_PER_WIN:,}")
        elif end_state == "fail":
            losses += 1
            total_runs += 1
            send_run_webhook(
                session_start=session_start,
                wins=wins,
                losses=losses,
                alert_text=f"@everyone Cid Act 2 lost a run. Total losses: {losses}",
            )
            print("Run failed; wins not incremented.")
        else:
            print("Replay not detected; skipping win stat update for this cycle.") 
        # Loop again from wait_start() on next iteration.
        continue

cid_farm2()