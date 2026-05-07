import re
import originpro as op #type: ignore
from pathlib import Path

_BEAMLINE_WAVELENGTH = 0.11595

op.lt_exec('dlgPath init:=%X title:="Select sample ID folder (contains xye folder and all metadata files)";')
root = Path(op.get_lt_str("path$"))

 
# Meta data file names should match corresponding xye names exactly, before file suffixes.
# Expected file structure:
#     TE001\
#         TE001_heat-00001.tif.metadata
#         TE001_heat-00002.tif.metadata
#         ... and so on
#         xye\
#             TE001_heat-00001.xye
#             TE001_heat-00002.xye
#             ... and so on
xye_folder = root / "xye"
metadata_folder = root
output_folder = root / "xye_withTemp"

output_folder.mkdir(parents=True, exist_ok=True)

# Temperature stored in userComment4 in metadata.
temp_pattern = re.compile(r"^userComment4\s*=\s*(.+)$")

def extract_temperature(metadata_path):
    """Return the temperature string from a .tif.metadata file."""
    with open(metadata_path, "r", encoding="utf-8") as f:
        for line in f:
            m = temp_pattern.match(line.strip())
            if m:
                return m.group(1).strip()
    return None


# Extract temperature from each metadata file and insert it into the first line of xye file.
# Results are placed in a new folder:
#     TE001\
#         TE001_heat-00001.tif.metadata
#         TE001_heat-00002.tif.metadata
#         ... and so on
#         xye\
#             TE001_heat-00001.xye
#             TE001_heat-00002.xye
#             ... ^^^ these files are unchanged
#         xye_withTemp\
#             TE001_heat-00001.xye
#             TE001_heat-00002.xye
#             ... ^^^ these NEW files have temperature in the first line
for xye_file in xye_folder.glob("*.xye"):
    base = xye_file.stem  # filename without extension
    metadata_file = metadata_folder / f"{base}.tif.metadata"

    if not metadata_file.exists():
        print(f"WARNING: No metadata for {base}")
        continue

    temperature = extract_temperature(metadata_file)
    if temperature is None:
        print(f"WARNING: No userComment4 entry in {metadata_file}")
        continue

    # Read original .xye
    with open(xye_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        print(f"WARNING: Empty file: {xye_file}")
        continue

    # Modify first line
    first_line = lines[0].rstrip("\n")
    new_first_line = f"{first_line}  {temperature}\n"

    # Write new file
    out_path = output_folder / xye_file.name
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(new_first_line)
        f.writelines(lines[1:])

    print(f"Processed: {xye_file.name}  →  Temp={temperature}")
print("All temperatures added to xye files.")

# New Workbook
wb = op.new_book('w',lname="In-Situ Import")
wks = wb[0]

# Makes sure Origin is looking for files in new xye_withTemp\ folder
op.set_lt_str("path$",f"{output_folder}\\")

# Labtalk to import all .xye files. 
# Data filter PXRD_11-ID-C_mar2026.oif automatically extracts temperature from first line into "Temp" row.
import_lt = f'''
cd path$;
findFiles ext:=*.xye;
impFile filtername:="PXRD_11-ID-C_mar2026.oif" location:=user;
wks.labels(-O)
'''
op.lt_exec(import_lt)


# Configure wavelength at top of this file.
# Adds wavelength to 2theta column.
# Q-Space script for Menu plugin expects Wavelength row.
wks._user_param_row("Wavelength (Å)",True)
wks.set_label(0,_BEAMLINE_WAVELENGTH,"Wavelength (Å)")

# Clean up columns
ncols = wks.cols
maxInt = 0 # Entire data set will be normalized as one range.
for col in range(ncols-1,0,-1):
    if col%2==0:
        # All 2theta columns will be identical. Delete all but first one.
        wks.del_col(col)
    else:
        # Set column labels
        wks.set_label(col,'Int','L')
        wks.set_label(col,'AU','U')
        
        # If local maximum is higher than maxInt so far, replace maxInt.
        col_data = wks.to_list(col)
        local_max = max(col_data)
        if local_max > maxInt:
            maxInt = local_max

# Column labels for 2theta column
wks.set_label(0,'2θ','L')
wks.set_label(0,'deg','U')

ncols = wks.cols        
for col in range(1,ncols,1):
    # Normalize columns to maxInt = 1
    data = wks.to_list(col)
    norm = [v/maxInt for v in data]
    wks.from_list(col,norm)
    
    # Auto-width resize
    op.lt_exec(f'wcolwidth {col+1} -1')