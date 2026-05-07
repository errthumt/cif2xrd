import json
import os
import originpro as op #type: ignore
import sys

op.lt_exec('string __uff$ = %Y;')
user_files = op.get_lt_str('__uff$').rstrip("\\/")

def load_user_json():
    """
    Load the user_calibrations.json from the User Files Folder.
    Returns the parsed JSON as a Python dict.
    """

    # Build full path to the JSON file, create if it doesn't exist
    os.makedirs(os.path.join(user_files, "Furnaces"), exist_ok=True)
    json_path = os.path.join(user_files, "Furnaces", "user_calibrations.json")

    if not os.path.exists(json_path):
        with open(json_path, "w") as f:
            json.dump({}, f, indent=4)

    # Load JSON
    with open(json_path, "r") as f:
        data = json.load(f)

    return data

def load_all_calibrations():
    """
    Load the furnace calibration JSON from the User Files Folder.
    Returns the parsed JSON as a Python dict.
    """
    

    # Build full path to the JSON file
    default_path = os.path.join(user_files, "Furnaces", "default_calibrations.json")
    # Load JSON
    with open(default_path, "r") as f:
        data = json.load(f)

    for furnace in data:
        data[furnace]["source"] = "default"

    user_data = load_user_json()

    for furnace in user_data:
        data[furnace] = user_data[furnace]
        data[furnace]["source"] = "user"

    return data

def load_furnace(silent=False):
    data = load_all_calibrations()
    wks = op.find_sheet()
    furnace_ID = wks.get_label("Actual Temp",'note1')

    furnace_data = data.get(furnace_ID)
    if not furnace_data:
        op.lt_exec(f'type -b "No calibration data found for furnace ID: \'{furnace_ID}\'. Check for typos or save your changes before reloading.";')
        return

    source = furnace_data["source"]
    set_temps = furnace_data["set"]
    actual_temps = furnace_data["actual"]
    cal_date = furnace_data.get("cal_date", "Unknown")
    two_point = "Y" if furnace_data.get("two_point", False) else "N"

    wks.from_list("Set Temp",set_temps)
    wks.from_list("Actual Temp",actual_temps)
    wks.set_label("Actual Temp",cal_date,"note2")
    wks.set_label("Actual Temp",two_point,"note3")
    
    if not silent:
        op.lt_exec(f'type -b "Loaded {furnace_ID} from {source} calibration data";')

def save_furnace():
    user_data = load_user_json()

    wks = op.find_sheet()
    furnace_ID = wks.get_label("Actual Temp",'note1')
    set_temps = wks.to_list("Set Temp")
    actual_temps = wks.to_list("Actual Temp")
    cal_date = wks.get_label("Actual Temp","note2")
    two_point = wks.get_label("Actual Temp","note3") == "Y"

    user_data[furnace_ID] = {
        "set": set_temps,
        "actual": actual_temps,
        "cal_date": cal_date,
        "two_point": two_point
    }

    # Build full path to the JSON file
    json_path = os.path.join(user_files, "Furnaces", "user_calibrations.json")
    # Save JSON
    with open(json_path, "w") as f:
        json.dump(user_data, f, indent=4)
    op.lt_exec(f'type -b "Saved {furnace_ID} to user calibration data";')
    load_furnace(silent=True)

def empty_sheet():
    wbook = op.load_book('PXRD_furnace_template.ogwu')
    wbook.activate()

dispatch = {
    "load": load_furnace,
    "save": save_furnace,
    "empty": empty_sheet
}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "load"
    if mode in dispatch:
        dispatch[mode]()
    else:
        print(f"Unknown mode: {mode}. Valid modes are: {list(dispatch.keys())}")