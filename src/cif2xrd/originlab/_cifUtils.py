
# These need to be manually kept in sync with PXRD_phaseFrac.py
_MW_LABEL = 'MW (g/mol)'
_Z_LABEL = 'Z'
_VOL_LABEL = 'Cell Volume (Å³)'

import warnings

# Axes3D is not included with Origin's native matplotlib, but it is not necessary for this package
warnings.filterwarnings(
    "ignore",
    message="Unable to import Axes3D",
    category=UserWarning,
    module="matplotlib.projections"
)


import tkinter as tk
root = tk.Tk()
root.withdraw() # Origin is picky about when to display tk windows.

import os
import sys
import originpro as op #type: ignore

import numpy as np #type: ignore
from pymatgen.io.cif import CifParser #type: ignore
from pymatgen.core import Structure #type: ignore
from pymatgen.core.periodic_table import Element #type: ignore
from pymatgen.analysis.diffraction.xrd import XRDCalculator #type: ignore

from cif2xrd.pattern import simPattern #type: ignore
from cif2xrd.paramUtils import clean_parameters, parse_params #type: ignore

# Extra dampening to match VESTA's peak heights
_B_EXTRA = 0.4

# Fix column headers, normalize columns, remove function row.
# Executed as a labtalk command near the end of this script.
def _lt_cleanup(normalize=True):
    wks = op.find_sheet()
    src_idx = wks._user_param_row('SourceFile',True) + 1
    LABTALK_CLEANUP = fr'''
    @SWS = 0;

    int nCols = wks.ncols;
    if (nCols < 2)
        break;

    wks.col1.lname$ = "2θ";
    wks.col1.unit$ = "deg";

    for(int ii = 2; ii <= nCols; ii++)
    {{
        string lng$ = wks.col$(ii).lname$;
        wcol(ii)[SourceFile]$ = lng$;

        wks.col$(ii).lname$ = "Int";
        {'rnormalize irng:=$(ii) method:=1 orng:=$(ii)' if normalize else ""};
        wks.col$(ii).unit$ = "AU";
        
        wcolwidth $(ii) -1;
    }};

    wks.labels(-O);
    wks.labels(>LU);
    wks.labels(<D{src_idx});
    '''
    return LABTALK_CLEANUP


def _pick_cif_files():
    file_select = op.lt_exec('dlgFile init:=%X multi:=1 group:=*.cif title:="Select CIF files to calculate patterns for"')
    # dlgFile automatically stores filenames under global variable fname$
    file_names = op.get_lt_str('fname$')
    if not file_select or not file_names:
        op.lt_exec('type -b "No files selected"')
        return False
    return True

# Select folder containing all desired files. Uses Origin's native dlfPath dialog.
def _pick_cif_folder():
    # dlgPath stores folder path under path$. findFiles finds all matching files in path$ and stores in fname$
    folder_selected = op.lt_exec('dlgPath init:=%X title:="Select folder containing CIF files"; findFiles ext:=*.cif')
    if not folder_selected:
        op.lt_exec('type -b "No folder selected"')
        return False
    
    file_names = op.get_lt_str('fname$')
    if not file_names:
        op.lt_exec('type -b "No CIF files found in the selected folder"')
        return False
    
    return True

def _pick_cifs(mode):
    if mode=='folder':
        picked = _pick_cif_folder()
    else:
        picked = _pick_cif_files()

    if not picked:
        return
    
    # Read the LabTalk variable fname$
    raw_list = op.get_lt_str('fname$')

    if raw_list:
        # Normalize Windows newlines and split into lines
        return [
            f.strip()
            for f in raw_list.replace("\r\n", "\n").split("\n")
            if f.strip()
        ]
    else:
        return None

#  Major import function
def _import_selected_cifs(file_list, normalize, book_name, pattern_params):

    # Create new book
    wb = op.new_book('w', lname=book_name)
    wks = wb[0]

    wks._user_param_row('SourceFile',True) # Create user parameter for source file names
    
    wks._user_param_row(_Z_LABEL,True)
    wks._user_param_row(_VOL_LABEL,True)
    wks._user_param_row(_MW_LABEL,True)


    # Start with no existing 2theta column, starting with first column.
    first_two_theta = None
    col_index = 0
    wavelength = None

    for cif_path in sorted(file_list):
        pattern = simPattern(cif_path, param_type="expanded", **pattern_params)
        if wavelength is None:
            wavelength = pattern.params["fe_wavelengths"][0]

        two_theta = pattern.two_theta
        intensity = pattern.intensity
        molWeight = pattern.molWeight
        Z = pattern.Z
        cell_volume = pattern.cell_volume

        # Only write 2theta column once.
        if first_two_theta is None:
            first_two_theta = two_theta
            wks.from_list(col_index, first_two_theta, lname='2Theta')
            col_index += 1

        # Write intensity for each CIF
        sample_name = os.path.splitext(os.path.basename(cif_path))[0]
        wks.from_list(col_index, intensity, lname=sample_name)
        
        #print(f'{molWeight:.6f}')
        wks.set_label(col_index, f'{molWeight:.6f}', _MW_LABEL)
        wks.set_label(col_index, f'{Z:.0f}', _Z_LABEL)
        wks.set_label(col_index, f'{cell_volume:.6f}', _VOL_LABEL)

        col_index += 1

    # Labtalk cleanup
    wb.activate()
    wks.activate()
    op.lt_exec(_lt_cleanup(normalize))
    
    # Create wavelength row expected by Q-space menu
    wks._user_param_row("Wavelength (Å)",True)
    wks.set_label(0,wavelength, "Wavelength (Å)")

    # Hide unwanted parameters.
    for uParam in ("Group Info","Method", "Wavelength (Å)",_MW_LABEL,_Z_LABEL,_VOL_LABEL):
        idx = wks._user_param_row(uParam,True) + 1
        op.lt_exec(f"wks.labels(-D{idx});")  

def select_cifs_and_import(params):
    pattern_params = params.copy()

    origin_defaults = {
        "file_mode": "files",
        "normalize_mode": True,
        "book_name": "CIF Imports"
    }

    origin_params = clean_parameters(pattern_params, origin_defaults)

    file_mode = origin_params["file_mode"]
    normalize = origin_params["normalize_mode"]
    book_name = origin_params["book_name"]

    file_list = _pick_cifs(file_mode)

    if file_list is None:
        return

    _import_selected_cifs(file_list, normalize, book_name, pattern_params)

def import_cifs_from_xf(argstring):
    params = parse_params(argstring)

    select_cifs_and_import(params)
