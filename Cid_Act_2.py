import time
import pyautogui
import webhook
from datetime import datetime
from pynput import keyboard as pynput_keyboard
from Tools import botTools as bt
from Tools import avMethods as avM
from Tools.screenHelpers import _safe_screenshot, pixel_matches_at
from Tools.imageHelpers import find_image_center
from Tools.gameHelpers import (
    kill, click, tap, spam_chord_for_duration,
    click_image_center, wait_start, quick_rts, slow_rts,
    focus_roblox, ensure_roblox_window_positioned, _roblox_window_screenshot_for_webhook,
)

# ================ TEAM COMPOSITION ================ #
# Ichigo, Sakura, Skele, Rukia, Aki, Gohan
# ================================================== #

TEAM = 1


RUNS_BEFORE_REJOIN = 250


GEMS_PER_WIN = 150
VOTE_START_POS = (840,228)
CLOSE_POS = (602,380)
FOCUS_BOSS = (252,573)
SKELE_KING_CLOSE = (931,282)
ABILITY_POS = (645,450)
ABILITY_POS_2 = (645, 520)
REPLAY_POS = (590,710) #(697,712)
REPLAY_IMG = "Replay.png"

#520, 615, 710, 800, 895, 985
if TEAM == 1:
    # UNITS = {
    #     "hb1": {"name": "Ichigo", "hotbar": (520, 826), "pos": (650, 525)},
    #     "hb2": {"name": "Sakura", "hotbar": (615, 826), "pos": (711, 537)},
    #     "hb3": {"name": "Skele", "hotbar": (710, 826), "pos": (605, 560)},
    #     "hb4": {"name": "Alucard", "hotbar": (800, 826), "pos": (580, 525)},
    #     "hb5": {"name": "Rukia", "hotbar": (895, 826), "pos": (688, 546)},
    #     "hb6": {"name": "Future Gohan", "hotbar": (895, 826), "pos": (688, 546)},
    # }
    
    
    
    UNITS = {
        "setup": {"name": "Ichigo", "hotbar": (520, 826), "pos": (805, 399)},
        "hb1": {"name": "Ichigo", "hotbar": (520, 826), "pos": (805, 399)},
        "hb2": {"name": "Sakura", "hotbar": (615, 826), "pos": (829, 338)},
        "hb3": {"name": "Skele", "hotbar": (710, 826), "pos": (738, 399)},
        "hb4": {"name": "Alucard", "hotbar": (800, 826), "pos": (735, 333)},
        "hb5": {"name": "Rukia", "hotbar": (895, 826), "pos": (688, 546)},
        "hb6": {"name": "Future Gohan", "hotbar": (895, 826), "pos": (688, 546)},
    }
elif TEAM == 2:
    UNITS = {
        "setup": {"name": "Ichigo", "hotbar": (520, 826), "pos": (805, 399)},
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

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

def on_press(key):
    try:
        if hasattr(key, "char") and key.char and key.char.lower() == "k":
            kill()
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

def _hotbar_slot_for_unit(unit):
    for slot_name, slot_unit in UNITS.items():
        if slot_unit is unit:
            return slot_name.removeprefix("hb")

    for slot_name, slot_unit in UNITS.items():
        if (
            slot_unit.get("name") == unit.get("name")
            and slot_unit.get("hotbar") == unit.get("hotbar")
            and slot_unit.get("pos") == unit.get("pos")
        ):
            return slot_name.removeprefix("hb")

    raise KeyError(f"Could not determine hotbar slot for unit: {unit.get('name', unit)}")

def place_unit(unit, click_delay=0.4, step_delay=0.02,close=False):
    click(unit["hotbar"], delay=click_delay)
    time.sleep(step_delay)
    click(unit["pos"], delay=click_delay)
    time.sleep(step_delay)
    if close:
        click(CLOSE_POS, delay=click_delay)

def place_unit_hotkey(unit, click_delay=0.1, step_delay=0.02, close=False, hotkey=None):
    if hotkey is None:
        hotkey = _hotbar_slot_for_unit(unit)

    pyautogui.moveTo(*unit["pos"])
    time.sleep(step_delay)
    tap_pg(str(hotkey))
    time.sleep(step_delay)
    click(unit["pos"], delay=click_delay, dont_move=True)
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
    time.sleep(10)
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
    if pixel_matches_at(1180,587,(33,15,24),tol=20):
        click(1180,587,delay=0.2)
        time.sleep(1)
        print("Enabled.")
    else:
        print("Already enabled.")
    click(1223,269,delay=0.2)
    time.sleep(1)
    click(750,286,delay=0.2)

def wait_end(total_runs, delay: float = 0.2, timeout: float = 15.0):
    global failed_runs
    global failed_matches
    result_region = (380, 257, 120, 55)
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            screenshot = _safe_screenshot()
            if screenshot is None:
                time.sleep(delay)
                continue

            if bt.does_exist("Victory.png",confidence=0.7,grayscale=False,region=result_region):
                print("✅ Win detected")
                failed_runs = 0
                return "win", total_runs
            elif bt.does_exist("Failed.png",confidence=0.7,grayscale=False,region=result_region):
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
    avM.restart_match()
    return "timeout", total_runs

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
        if total_runs>= RUNS_BEFORE_REJOIN:
            total_runs = rejoin_raid(total_runs)
        if total_runs == 0:
            wait_start()
            quick_rts()
            time.sleep(0.5)
            click(523,544,right_click=True,delay=0.5)
            time.sleep(2)
            if TEAM == 1:
                click(580,650, right_click=True,delay=0.5)
                time.sleep(2)
            click(VOTE_START_POS)
        time.sleep(0.2)
        
        
        
        if TEAM == 1:
            place_unit_hotkey(UNITS["hb3"],click_delay=0.2)
            time.sleep(0.2)
            place_unit_hotkey(UNITS["hb1"])
            time.sleep(0.1)
            click(UNITS["hb3"]["pos"])
            time.sleep(0.2)
            click(ABILITY_POS, delay=0.2)
            time.sleep(3)
            spam_chord_for_duration(duration=2)
            click(SKELE_KING_CLOSE)
            time.sleep(1.6)
            place_unit_hotkey(UNITS["hb4"])
            time.sleep(0.1)
            place_unit_hotkey(UNITS["hb2"])
            time.sleep(0.1)
            temp = 0
            while pixel_matches_at(975,142,(103,219,81),tol=20,sample_half=1):
                if temp>=1:
                    click(UNITS["hb2"]["pos"])
                    time.sleep(0.1)
                click(ABILITY_POS, delay=0.2)
                time.sleep(0.1)
                click(UNITS["hb1"]["pos"])
                time.sleep(0.15)
                temp += 1
            click(UNITS["hb2"]["pos"])
            time.sleep(0.2)
            click(ABILITY_POS, delay=0.2)
            time.sleep(0.1)
            click(UNITS["hb3"]["pos"])
            # tap('f')
            # time.sleep(0.7)
            # click_image_center("Gohan2.png",confidence=0.7,grayscale=True,region=(814, 283, 470, 430), delay=0.03, retries=2)
            # time.sleep(0.1)
            # tap('f')
            time.sleep(0.1)
            click(UNITS["hb2"]["pos"])
            time.sleep(0.2)
            tap('x')
            time.sleep(0.2)
            click(UNITS["hb1"]["pos"])
            time.sleep(0.2)
            tap('r')
            time.sleep(0.3)
            for i in range(2):
                tap('x')
                time.sleep(0.3)
            while bt.does_exist("Cid_Health.png", confidence=0.7, grayscale=False, region=(555,235,125,27)):
                time.sleep(0.1)
            click(UNITS["hb3"]["pos"])
            time.sleep(4.3)
            for i in range(10):
                click(ABILITY_POS_2, delay=0.2)
                time.sleep(0.1)
            
            
            
            
            
        elif TEAM == 2:
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
            while pixel_matches_at(*UNITS["hb4"]["hotbar"], (35, 35, 35), tol=20, sample_half=0):
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
cid_farm()