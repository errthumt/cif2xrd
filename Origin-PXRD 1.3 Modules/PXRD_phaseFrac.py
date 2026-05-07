import originpro as op
import sys

_MOL_FRACTION_LABEL = 'Mol Fraction'
_CELL_FRACTION_LABEL = 'Cell Fraction'
_WT_FRACTION_LABEL = 'Wt Fraction'

# These need to be manually kept in sync with PXRD_cifImp.py
_MW_LABEL = 'MW (g/mol)'
_Z_LABEL = 'Z'
_VOL_LABEL = 'Cell Volume (Å³)'


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



if __name__ == "__main__":
    frac_type = sys.argv[1] if len(sys.argv) > 1 else 'moles'
    lt_cleanup_cmd = main(frac_type)
    op.lt_exec(f'string cleanup$ = "{lt_cleanup_cmd}";')

    #print(lt_cleanup_cmd)
    wks = op.find_sheet()
    wks.activate()
    #op.lt_exec(lt_cleanup_cmd)



