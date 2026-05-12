import subprocess
import pywinctl as pwc

try:
    import Quartz
except Exception:
    Quartz = None


TARGET_W = 1100
TARGET_H = 800
TARGET_X = 200
TARGET_Y = 100


def move_with_pywinctl():
    window = None
    found_title = None

    for title in ("Roblox", "RobloxPlayer"):
        windows = pwc.getWindowsWithTitle(title)
        if windows:
            window = windows[0]
            found_title = title
            break

    if window is None:
        return False

    try:
        window.resizeTo(TARGET_W, TARGET_H)
        print(f"Resized {found_title} with pywinctl.")
        window.moveTo(TARGET_X, TARGET_Y)
        print(f"Moved {found_title} with pywinctl.")
        window.activate()
        print(f"Finished positioning {found_title} with pywinctl.")
        return True
    except Exception as e:
        print(f"pywinctl found a window but failed to move/resize it: {e}")
        return False


def find_roblox_with_quartz():
    if Quartz is None:
        print("Quartz not available.")
        return None

    try:
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID
        )
    except Exception as e:
        print(f"Quartz window scan failed: {e}")
        return None

    candidates = []

    for w in windows:
        owner = w.get("kCGWindowOwnerName", "")
        name = w.get("kCGWindowName", "")
        bounds = w.get("kCGWindowBounds", {})
        pid = w.get("kCGWindowOwnerPID")

        owner_l = str(owner).lower()
        name_l = str(name).lower()

        if "roblox" in owner_l or "roblox" in name_l:
            candidates.append({
                "owner": owner,
                "name": name,
                "pid": pid,
                "bounds": bounds,
            })

    if not candidates:
        print("Quartz did not find a Roblox window.")
        return None

    chosen = candidates[0]
    print("Quartz found Roblox candidate:")
    print(f"  owner={chosen['owner']!r}")
    print(f"  name={chosen['name']!r}")
    print(f"  pid={chosen['pid']}")
    print(f"  bounds={chosen['bounds']}")
    return chosen


def move_with_applescript(process_name):
    script = f'''
    tell application "System Events"
        if not (exists process "{process_name}") then
            error "Process {process_name} not found"
        end if

        tell process "{process_name}"
            set frontmost to true

            if (count of windows) < 1 then
                error "No windows found for {process_name}"
            end if

            tell window 1
                set position to {{{TARGET_X}, {TARGET_Y}}}
                set size to {{{TARGET_W}, {TARGET_H}}}
            end tell
        end tell
    end tell
    '''

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"Finished positioning {process_name} with AppleScript.")
        return True

    print("AppleScript move/resize failed:")
    if result.stderr.strip():
        print(result.stderr.strip())
    else:
        print(result.stdout.strip())
    return False


def set_rblx():
    if move_with_pywinctl():
        return

    print("pywinctl failed or found nothing. Trying Quartz fallback...")

    quartz_match = find_roblox_with_quartz()
    if not quartz_match:
        print("Roblox window not found.")
        return

    process_name = quartz_match["owner"]

    if move_with_applescript(process_name):
        return

    print("Quartz recognised Roblox, but move/resize still failed.")
    print("Check macOS permissions:")
    print("- System Settings -> Privacy & Security -> Accessibility")
    print("- Enable VS Code / Terminal / Python")


set_rblx()