import originpro as op
import sys

# Column formulas require letters instead of column indices
def col_index_to_letter(idx):
    letters = ""
    idx += 1  # convert to 1-based
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def create_q_col_for(wks, col, wl_row):
    """
    Convert the given 0-based column index (col) from 2θ → Q.
    Creates a new column immediately to the right of source col.
    Uses a dynamic formula referencing the user parameter row with index wl_row.
    """

    # Add new column at end
    old_ncols = wks.cols
    wks.cols = old_ncols + 1

    # Find new column at end, define intended location for that column
    new_col_index = old_ncols
    target_index = col + 1

    # Move new column next to source column
    n = target_index - new_col_index
    wks.move_cols(n, new_col_index, 1)

    # New Q col is now at intended location
    q_col = target_index

    # Set Long Name
    wks.set_label(q_col, "Q", 'L')

    # Set Q column as X designation
    wks.cols_axis('x', q_col, q_col, False)

    # Get column letters for formula row
    orig_letter = col_index_to_letter(col)
    new_letter  = col_index_to_letter(q_col)

    # d_row refers to user_parameter row in labtalk formula
    # Python indices are 0-based. Labtalk/formula indices are 1-based
    d_row = wl_row + 1

    # Build formula
    formula_text = (
        f"(4*pi / {orig_letter}[D{d_row}]) * "
        f"sin(radians({orig_letter}/2))"
    )

    # Apply formula. q_col is still 0-based for python, but formula_text contains 1-based indices for labtalk
    wks.set_formula(q_col, formula_text)

    # Set units to inverse angstrom
    wks.set_label(q_col, "Å\\+(-1)", 'U')

    # Copy SourceFile row from worksheet
    try:
        sourcefiles = wks.get_labels('SourceFile')
    except:
        sourcefiles = [""] * wks.cols

    if len(sourcefiles) < wks.cols:
        sourcefiles += [""] * (wks.cols - len(sourcefiles))

    # Copy SourceFile from source column to q column
    sourcefiles[q_col] = sourcefiles[col]
    wks.set_label(q_col, sourcefiles[q_col], 'SourceFile')


# Dispatch logic: "all_deg" OR "selected"
def dispatch_qspace(mode="all_deg"):
    """
    mode = "all_deg"   → convert all columns with units 'deg'
    mode = "selected"  → convert only user-selected columns
    """

    wks = op.find_sheet() # Target active open worksheet
    units = wks.get_labels('U') # Copy all units for "deg" detection

    # Determine which columns to convert
    if mode == "all_deg": # Any column with units "deg" is marked
        col_indices = [
            col for col in range(wks.cols)
            if (units[col] or "").strip().lower() == "deg"
        ]

    elif mode == "selected": # Any selected column is marked.
        col_indices = []
        for i in range(1, wks.cols + 1):  # Origin is 1-based
            # Only a labtalk command can detect column selection by 1-based index
            if op.lt_int(f"wks.isColSel({i})") == 1:
                col_indices.append(i - 1)

    else:
        op.lt_exec(f'type -b "Unknown mode: {mode}";')
        return
    
    # Creates wavelength row if it doesn't already exist
    wl_row = wks._user_param_row("Wavelength (Å)",True)
    op.lt_exec(f"wks.labels(*D{wl_row+1});") # Show wavelength row


    # Convert in reverse order to avoid index shifting
    for col in reversed(col_indices):
        create_q_col_for(wks, col, wl_row)

    # Auto-fit column widths
    op.lt_exec('''
        @SWS = 0;
        int nCols = wks.ncols;
        if (nCols < 2)
            break;
        for(int ii = 2; ii <= nCols; ii++)
        {
            wcolwidth $(ii) -1
        }
        // Long name and units to bottom
        wks.labels(>LU);

    ''')
    op.lt_exec('type -b "Q-space columns created successfully.";')



# Dispatch based on labtalk arguments.
if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all_deg"
    dispatch_qspace(mode)