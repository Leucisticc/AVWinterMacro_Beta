import os
import sys
import requests
import zipfile
# This gets the rest of the files and puts them in the right direct
# This file should be in Utility
Main_Folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

winter_event_url = "https://raw.githubusercontent.com/loxerex/Winter-Normal-Macro/main/Winter_Event.py"
images_url = "https://github.com/loxerex/Winter-Normal-Macro/raw/refs/heads/main/Images.zip"

def get_cur_ver(target: str):
    file_path = os.path.join(Main_Folder+target)
    with open(file_path, 'r', encoding="utf-8") as t:
        content = t.read()
        for line in content.splitlines():
            if 'VERSION_N' in line:
                return line
                break
def get_newest_ver():
    req_obj = requests.get(winter_event_url)
    text = req_obj.text.split('VERSION_N')
    newest_ver = None
    for line in req_obj.text.splitlines():
        if 'VERSION_N' in line:
            newest_ver = line
            break
    return newest_ver


winter_event_name = winter_event_url.split('/')[-1].replace(" ","_")
winter_event_path = os.path.join((Main_Folder),winter_event_name)

images_name = images_url.split('/')[-1].replace(" ","_")
images_path = os.path.join((Main_Folder),images_name)



print("Welcome to the file checker, you can either")
print("[1] - Run a file check which sees if everything is in the right place")
print("[2] - Check/update/install winter_event.py + resources")
answer = int(input(">"))

get_winter = False
get_resources = False


if type(answer) == int:
    
    if answer == 1:
        print("Running file check..")
        print(f"Home folder: {Main_Folder}")
        print(f"Winter_Event.py, Exists: {os.path.exists(os.path.join(Main_Folder,"Winter_Event.py"))}")
        print(f"webhook.py, Exists: {os.path.exists(os.path.join(Main_Folder, "webhook.py"))}")
        print(f"Position.py, Exists: {os.path.exists(os.path.join(Main_Folder, "Position.py"))}")
        
        print(f"Settings Folder: {os.path.join(Main_Folder, "Settings")}")
        print(f"Winter_Event.json, Exists: {os.path.exists(os.path.join(Main_Folder, "Settings/Winter_Event.json"))}")
        
        
        print(f"Utility Folder: {os.path.join(Main_Folder, "Utility")}")
        print(f"mouseDebugging.py, Exists: {os.path.exists(os.path.join(Main_Folder, "Utility/mouseDebugging.py"))}")
        print(f"SettingsHelper.py, Exists: {os.path.exists(os.path.join(Main_Folder, "Utility/SettingsHelper.py"))}")
        
        print(f"Tools Folder: {os.path.join(Main_Folder, "Tools")}")
        print(f"avMethods.py, Exists: {os.path.exists(os.path.join(Main_Folder, "Tools/avMethods.py"))}")
        print(f"botTools.py, Exists: {os.path.exists(os.path.join(Main_Folder, "Tools/botTools.py"))}")
        print(f"winTools.py, Exists: {os.path.exists(os.path.join(Main_Folder, "Tools/winTools.py"))}")
        
        print(f"Resources Folder, Exists: {os.path.exists(os.path.join(Main_Folder, "Resources"))}")
        print(f"tesseract Folder, Exists: {os.path.exists(os.path.join(Main_Folder, "tesseract"))}")
        
        
        
        
    if answer == 2:
        if os.path.exists(os.path.join(Main_Folder,winter_event_name)):
            print("It looks like you already have the files")
            cur_ver = get_cur_ver('/Winter_Event.py')
            new_ver = get_newest_ver()
            if cur_ver==new_ver:
                print("It looks like your winter_event.py is update to date would you like to replace it? [Y/N]")
                a = input(">")
                if type(a) == str:
                    if a.lower() == "y":
                        get_winter = True
                print("would you want to update resources? (Y/N)")
                b = input(">")
                if type(b) == str:
                    if b.lower() == "y":
                        get_resources = True
            else:
                print(f"Your winter_event.py is outdated! n:{new_ver} | c:{cur_ver}")
                print("Would you like to update? This will also update resources. [Y/N]")
                a = input(">")
                if type(a) == str:
                    if a.lower() == "y":
                        get_winter = True
                        get_resources = True

        else:
            print("Would you like to download Winter_Event.py and resources? [Y/N]")
            a = input(">")
            if type(a) == str:
                if a.lower() == "y":
                    get_winter = True
                    get_resources = True
                        
        try:
            if get_winter:
                # winter_event.py
                with requests.get(winter_event_url, stream=True) as req:
                    req.raise_for_status() # error check
                    with open (winter_event_path, 'wb') as file: 
                        for chunk in req.iter_content(chunk_size=8192):
                            file.write(chunk)
            if get_resources:
                # resources
                with requests.get(images_url, stream=True) as req:
                    req.raise_for_status() # error check
                    with open (images_path, 'wb') as file: 
                        for chunk in req.iter_content(chunk_size=8192):
                            file.write(chunk)  
                # unzip resources
                with zipfile.ZipFile(images_path, "r") as z: 
                    z.extractall(Main_Folder)
                # remove useless images.zip
                os.remove(images_path)
        except Exception as e:
            print(e)