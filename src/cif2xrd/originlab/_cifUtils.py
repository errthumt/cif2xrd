
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

import os
import originpro as op #type: ignore

from cif2xrd.pattern import simPattern #type: ignore
from cif2xrd.paramUtils import clean_parameters, parse_params #type: ignore

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



def add_phase_fractions(frac_mode):
    _MOL_FRACTION_LABEL = 'Mol Fraction'
    _CELL_FRACTION_LABEL = 'Cell Fraction'
    _WT_FRACTION_LABEL = 'Wt Fraction'

    # Column formulas require letters instead of column indices
    def col_index_to_letter(idx):
        letters = ""
        idx += 1  # convert to 1-based
        while idx > 0:
            idx, rem = divmod(idx - 1, 26)
            letters = chr(65 + rem) + letters
        return letters

    def get_max_range(n1,n2):
        max_string = ""
        for n in range(n1,n2+1):
            max_string += f'max({col_index_to_letter(n)}),'
        max_string = max_string[:-1]  # Remove trailing comma
        return max_string

    def refresh_label(col, label):
        return f'wcol({col+1})[{label}]$ = wcol({col+1})[{label}]$; wcolwidth({col+1}) -1;'

    def main(frac_type='moles'):
        lt_cleanup_cmd = ''#type -b "Imported CIFs successfully!";'
        wks = op.find_sheet()

        # number of phase columns imported
        n_phases = wks.cols - 1
        wks.cols = 2+4*n_phases

        norm_idx = wks._user_param_row('Norm Type',True)+1
        lt_cleanup_cmd += f'wks.labels(-D{norm_idx});' # Hide norm type row for autosizing. It will be revealed again at the end of this script.
        mol_idx = wks._user_param_row('Mol Fraction',True)+1
        vol_idx = None
        wt_idx = None

        if frac_type == 'cell':
            vol_idx = wks._user_param_row('Vol Fraction',True)+1
        elif frac_type == 'weight':
            wt_idx = wks._user_param_row('Wt Fraction',True)+1
        elif frac_type != 'moles':
            print(f'Unknown fraction type: {frac_type}')
            return

        source_range = get_max_range(1,n_phases)
        phase_range = get_max_range(1+n_phases,2*n_phases)
        max_norm_range = f'{col_index_to_letter(1+2*n_phases)}:{col_index_to_letter(3*n_phases)}'
        sum_norm_range =f'{col_index_to_letter(1+3*n_phases)}:{col_index_to_letter(4*n_phases)}'

        copy_labels = ['L','U','SourceFile',_MW_LABEL,_Z_LABEL,_VOL_LABEL]

        cleanup_cmds = {
            'phase': [],
            'max_norm': [],
            'sum_norm': []
        }

        for col in range(1,n_phases+1):

            wks.set_label(col,'Raw Data','Norm Type')

            phase_col = col+n_phases
            wks.set_label(phase_col,'Phase-Scaled','Norm Type')

            if frac_type == 'moles':
                wks.set_label(phase_col,1.0,_MOL_FRACTION_LABEL)
            elif frac_type == 'cell':
                wks.set_label(phase_col,1.0,_CELL_FRACTION_LABEL)
                lt_cmd = f'''wcol({col+1})[{_MOL_FRACTION_LABEL}]$ = "=This[{_CELL_FRACTION_LABEL}] * This[{_Z_LABEL}]";
                                wks.labels(-D{mol_idx});'''
                op.lt_exec(lt_cmd)
                copy_labels.append(_MOL_FRACTION_LABEL)
                cleanup_cmds['phase'].append(refresh_label(phase_col, _MOL_FRACTION_LABEL))

            elif frac_type == 'weight':
                wks.set_label(phase_col,1.0,_WT_FRACTION_LABEL)
                lt_cmd = f'''wcol({col+1})[{_MOL_FRACTION_LABEL}]$ = "=This[{_WT_FRACTION_LABEL}] / This[{_MW_LABEL}]";
                                wks.labels(-D{mol_idx});'''
                op.lt_exec(lt_cmd)
                copy_labels.append(_MOL_FRACTION_LABEL)
                cleanup_cmds['phase'].append(refresh_label(phase_col, _MOL_FRACTION_LABEL))

            source_letter = col_index_to_letter(col)
            phase_formula = f'{source_letter} * This[{_MOL_FRACTION_LABEL}] / max({source_range})'
            wks.set_formula(phase_col,phase_formula)
            cleanup_cmds['phase'].append(refresh_label(phase_col, 'O'))

            max_norm_col = phase_col+n_phases
            wks.set_label(max_norm_col,'Max Phase','Norm Type')

            phase_letter = col_index_to_letter(phase_col)
            max_norm_formula = f'{phase_letter} / max({phase_range})'
            wks.set_formula(max_norm_col,max_norm_formula)
            cleanup_cmds['max_norm'].append(refresh_label(max_norm_col, 'O'))

            sum_norm_col = max_norm_col+n_phases
            wks.set_label(sum_norm_col,'Sum','Norm Type')
            
            max_norm_letter = col_index_to_letter(max_norm_col)
            sum_norm_formula = f'{max_norm_letter} / max(sum({max_norm_range}))'
            wks.set_formula(sum_norm_col,sum_norm_formula)
            cleanup_cmds['sum_norm'].append(refresh_label(sum_norm_col, 'O'))

            for lbl in copy_labels:
                val = wks.get_label(col,lbl)
                if val:
                    for calc_col in (phase_col,max_norm_col,sum_norm_col):
                        wks.set_label(calc_col,val,lbl)

        for section, cmds in cleanup_cmds.items():
            for cmd in cmds:
                lt_cleanup_cmd += cmd

        sum_col = wks.cols-1
        wks.set_label(sum_col,'Normalized','Norm Type')
        sum_formula = f'sum({sum_norm_range})'
        wks.set_formula(sum_col,sum_formula)
        wks.set_label(sum_col,'Int','L')
        wks.set_label(sum_col, 'AU','U')
        wks.set_label(sum_col,'All Phases','C')
        lt_cleanup_cmd += refresh_label(sum_col, 'O')

        lt_cleanup_cmd += f'wks.labels(*D{norm_idx});' # Reveal norm type row again.

        for row_idx in (mol_idx,vol_idx,wt_idx):
            if row_idx is not None:
                lt_cleanup_cmd += f'wks.labels(>D{row_idx});' # Move fraction row to bottom.

        lt_cleanup_cmd += 'wks.labels(>LU);'
        lt_cleanup_cmd +=f'wks.merge(D{norm_idx},1);' # Identical norm type labels will be visually merged.


        return lt_cleanup_cmd




    lt_cleanup_cmd = main(frac_mode)
    op.lt_exec(f'string cleanup$ = "{lt_cleanup_cmd}";')

    #print(lt_cleanup_cmd)
    wks = op.find_sheet()
    wks.activate()
    #op.lt_exec(lt_cleanup_cmd)




