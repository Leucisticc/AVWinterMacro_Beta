import os
import sys
import json
import time
Settings_Path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"Settings")
WE_Json = os.path.join(Settings_Path,"Winter_Event.json")

global Settings_Data
Settings_Data = None
print("Loading settings data")
def load_json_data():
    JSON_DATA = None
    if os.path.isfile(WE_Json):
        with open(WE_Json, 'r') as f:
            JSON_DATA = json.load(f)
    return JSON_DATA

def save_data(data):
    with open(WE_Json, 'w') as f:
        json.dump(data, f, indent=4)
        
if os.path.exists(Settings_Path):
    if os.path.exists(WE_Json):
        print("hi")
        Settings_Data = load_json_data()
else:
    print("Failed to find settings file. Closing in 10 seconds")
    time.sleep(10)
    
print("Welcome to settings helper!")
print("[1] - Turn on ui navigation")
print("[2] - Turn on click to move for area 1 and 2")
print("[3] - Change Ainz Unit")
answer = int(input(">"))

if answer is not None:
    if answer == 1:
        Settings_Data['USE_UI_NAV'] = True
    if answer == 2:
        Settings_Data['CTM_P1_P2'] = True
    if answer == 3:
            if Settings_Data['USE_WD'] == True:
                print("Current Unit: Whitebeard, would you like to change that? [Y/N]")
            elif Settings_Data['USE_DIO'] == True:
                print("Current Unit: Dio, would you like to change that? [Y/N]")
            else:
                print(f"Current {Settings_Data["USE_AINZ_UNIT"]}: Dio, would you like to change that? [Y/N]")
            a = str(input(">"))
            if a is not None:
                if a.lower() == "y":
                    if Settings_Data['USE_WD'] == True:
                        Settings_Data['USE_WD'] = False
                    print("What unit would you like to use? [wd, dio, or any other av name of a unit]")
                    b = str(input(">"))
                    if b is not None:
                        if b.lower() == "dio":
                            Settings_Data['USE_WD'] = False
                            Settings_Data['USE_DIO'] = True
                            Settings_Data['USE_AINZ_UNIT'] = ""
                        elif b.lower() == "wd":
                            Settings_Data['USE_WD'] = True
                            Settings_Data['USE_DIO'] = False
                            Settings_Data['USE_AINZ_UNIT'] = ""
                        else:
                            Settings_Data['USE_WD'] = False
                            Settings_Data['USE_DIO'] = False
                            Settings_Data['USE_AINZ_UNIT'] = b
                    print("[M/U] Would you like to max the unit or go to an upgrade? If you're not using dio save an image of your upgrade as YOUR_MOVE.png in winter!")
                    c = str(input(">"))
                    if c is not None:
                        if c.lower() == "m":
                            Settings_Data['MAX_UPG_AINZ_PLACEMENT'] = True
                        else:
                            Settings_Data['MAX_UPG_AINZ_PLACEMENT'] = False
                    print("[Y/N] Would you like to monarch it too?")
                    d = str(input(">"))
                    if d is not None:
                        if d.lower() == "y":
                            Settings_Data['MONARCH_AINZ_PLACEMENT'] = True
                        else:
                            Settings_Data['MONARCH_AINZ_PLACEMENT'] = False
save_data(Settings_Data)