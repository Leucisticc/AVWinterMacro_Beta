import pywinctl as pwc

def set_rblx():

    windows = pwc.getWindowsWithTitle("Roblox")

    if not windows:
        print("Roblox window not found")
        return

    window = windows[0]
    window.resizeTo(1100, 800)
    print("Resized.")
    window.moveTo(200, 100)
    print("Moved.")
    window.activate()
    print("Finished Positioning.")

set_rblx()