import originpro as op #type:ignore
import os

from cif2xrd.paramUtils import clean_parameters, parse_params, default_params #type: ignore

# Import ras_files contained in labtalk fname$ variable
def _import_ras_files(file_list=None, normalize=True, book_name='RAS Imports'):
    if file_list is None:
        return

    # Imports using User Files\Filters\rasImp.oif
    # Cleans up names and units
    norm_command = 'rnormalize irng:=$(ic) method:=1 orng:=$(ic);' if normalize else '// Did not normalize'
    
    # Create new book, target worksheet
    wb = op.new_book('w',lname="RAS Imports")
    wks = wb[0]

    src_idx = wks._user_param_row('SourceFile',True) + 1

    labtalk_cmd = fr'''
    impFile filtername:="rasImp.oif" location:=user;
    page.longname$ = "{book_name}";
    wks.name$ = "{book_name}";

    for(int ic=2; ic<=wks.ncols; ic+=2)
    {{
       {norm_command}
       wks.col$(ic).lname$ = "Int";
       wks.col$(ic).unit$ = "AU";
       wks.col$(ic-1).lname$ = "2θ";
       wks.col$(ic-1).unit$ = "deg";
       
       wcolwidth $(ic) -1;
       wcolwidth $(ic-1) -1;
    }}
    
    // Hide Formula Row
    wks.labels(-O);

    // Longname and units to the bottom, source file names to the top
    wks.labels(>LU);
    wks.labels(<D{src_idx});
    '''



    # Import
    op.lt_exec(labtalk_cmd)

    # Init wavelength row if it doesn't exist
    wl_row=wks._user_param_row("Wavelength (Å)", True)
    # hide wavelength row (only revealed for q space)
    op.lt_exec(f"wks.labels(-D{wl_row+1});")

    # Iterate through files in same order as fname$
    for i, path in enumerate(file_list):
        wl_value = None

        # Read Rigaku data header and extract wavelength
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "HW_XG_WAVE_LENGTH_ALPHA1" in line:
                        # Wavelength is on line: *HW_XG_WAVE_LENGTH_ALPHA1 "1.2345"
                        # Extract the number inside quotes
                        parts = line.split('"')
                        if len(parts) >= 2:
                            wl_value = float(parts[1])
                        break
        # Skip not-found wavelengths, but warn user in script window.
        except Exception as e:
            print(f"WARNING: Failed to read wavelength from {path}: {e}")

        # Write wavelength into the correct 2θ column
        if wl_value is not None:
            # 2θ columns are every odd column in order of fname$
            two_theta_col = 2*i  # 0-based column index for 2θ
            wks.set_label(two_theta_col,wl_value,"Wavelength (Å)")
    
    # Hide unwanted parameter rows
    for uParam in ("Group Info","Method"):
        idx = wks._user_param_row(uParam,True) + 1
        op.lt_exec(f"wks.labels(#D{idx});")

    # Clean SourceFile label row to contain only filenames (instead of full path)
    try:
        sourcefiles = wks.get_labels('SourceFile')
        cleaned = [os.path.basename(s) if s else "" for s in sourcefiles]
        for i, val in enumerate(cleaned):
            wks.set_label(i, val, 'SourceFile')
    except:
        pass

    op.lt_exec('type -b "RAS import complete.";')

def _select_ras_from_folder():
    # dlgPath stores folder path under path$. findFiles finds all matching files in path$ and stores in fname$
    folder_path = op.lt_exec('dlgPath init:=%X title:="Select folder containing RAS files"; findFiles ext:=*.ras;')
    if not folder_path:
        op.lt_exec('type -b "No folder selected.";')
        return

    # Get the list of imported file paths from fname$
    file_list = op.get_lt_str('fname$').split("\r\n")
    file_list = [p for p in file_list if p.strip()]  # clean empties

    if not file_list:
        op.lt_exec('type -b "No RAS files found in folder.";')
        return None
    
    return file_list

def _select_ras_files():
    file_select = op.lt_exec('dlgFile init:=%X multi:=1 title:="Select RAS files for import" group:=*.ras')
    # dlgFile automatically stores filenames under global variable fname$
    file_list = op.get_lt_str('fname$').split("\r\n")
    file_list = [p for p in file_list if p.strip()]
    if not file_select or not file_list:
        op.lt_exec('type -b "No files selected"')
        return None
    
    return file_list

def select_ras_and_import(params):
    default_params["RAS"] = {
        "book_name":"RAS Imports",
        "file_mode":"files",
        "normalize_mode":True
    }

    cleaned_params = clean_parameters(params, defaults=default_params["RAS"])

    file_mode = cleaned_params["file_mode"]
    normalize = cleaned_params["normalize_mode"]
    book_name = cleaned_params["book_name"]

    if file_mode == "folder":
        file_list = _select_ras_from_folder()
    elif file_mode == "files":
        file_list = _select_ras_files()
    else:
        op.lt_exec(f'type -b "Unknown mode: {file_mode}";')
        return

    _import_ras_files(file_list, normalize, book_name)

def import_ras_from_xf(argstring):
    params = parse_params(argstring)

    select_ras_and_import(params)
    

# Select folder containing all desired files. Uses Origin's native dlfPath dialog.
def import_ras_from_folder(normalize=True,book_name='RAS Imports'):
    # dlgPath stores folder path under path$. findFiles finds all matching files in path$ and stores in fname$
    folder_path = op.lt_exec('dlgPath init:=%X title:="Select folder containing RAS files"; findFiles ext:=*.ras;')
    if not folder_path:
        op.lt_exec('type -b "No folder selected.";')
        return

    file_list = op.get_lt_str('fname$')

    if not file_list:
        op.lt_exec('type -b "No RAS files found in folder.";')
        return

    _import_ras_files(normalize,book_name)


