import pywinctl as pwc

def set_rblx():
    window = None
    found_title = None

    for title in ("Roblox", "RobloxPlayer"):
        windows = pwc.getWindowsWithTitle(title)
        if windows:
            window = windows[0]
            found_title = title
            break

    if window is None:
        print("Roblox window not found (checked Roblox and RobloxPlayer)")
        return

    window.resizeTo(1100, 800)
    print(f"Resized {found_title}.")
    window.moveTo(200, 100)
    print(f"Moved {found_title}.")
    window.activate()
    print(f"Finished positioning {found_title}.")

set_rblx()