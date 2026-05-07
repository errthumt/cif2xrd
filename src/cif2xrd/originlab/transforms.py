import originpro as op

# Column formulas require letters instead of column indices
def _col_index_to_letter(idx):
    letters = ""
    idx += 1  # convert to 1-based
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters

# Decrepit from old use of tkinter UI. May be refactored in future.
def _gui_select_columns(wks):
    """
    Replacement for the old Tkinter GUI.
    Now returns the list of 0-based column indices
    that the user has selected in the active worksheet.
    """

    selected = []

    # Origin uses 1-based column indices
    for i in range(1, wks.cols + 1):
        is_selected = op.lt_int(f"wks.isColSel({i})")
        if is_selected == 1:
            selected.append(i - 1)  # convert to 0-based

    return selected


# Mark all desired columns based on mode
def _collect_applicable_columns(mode="au"):
    """
    mode = "au"  → return all columns with Units == "AU"
    mode = "deg" -> return all columns with Units == "deg"
    mode = "gui" → return all columns selected in Origin
    """
    # target active sheet
    wks = op.find_sheet()

    if mode.lower() == "gui":
        return _gui_select_columns(wks)

    # Default: AU mode
    units = wks.get_labels('U')
    applicable = []

    for col in range(wks.cols):
        unit = units[col].strip().lower() if units[col] else ""
        if unit == mode:
            applicable.append(col)

    return applicable

# Setup large-scale method for rescale transformation.
def _wks_scale_setup(wks):
    idx = wks._user_param_row('ScaleFactor', True)
    return idx + 1  # D-row index

def _col_scale_setup(wks,col):
    wks.set_label(col,0.5,'ScaleFactor')
    return None

def _col_q_setup(w, col):
    # Set Q column as X designation
    w.cols_axis('x', col, col, False)

    # Set units to inverse angstrom
    w.set_label(col, "Å\\+(-1)", 'U')

# Transforms have a setup routine, a longname template, comment template and a formula row template
TRANSFORMS = {
    # "transform_name": {
    #     "setup": lambda w: setup routine in terms of target worksheet w. Returns index for applicable user parameter row
    #     "col_setup": lambda w,c: setup routine in terms of tartget worksheet w and column col.
    #     "longname": lambda ln: returns transformed column longname in terms of original longname ln
    #     "comment": lambda c: returns transformed column comment in terms of original comment c
    #     "formula": lambda orig, new, d_row: returns labtalk formula text in terms of original and new col indices and d_row returned by setup routine.
    # },
    "qspace": {
        "setup": lambda w: w._user_param_row("Wavelength (Å)", True) + 1,
        "col_setup": _col_q_setup,
        "longname": lambda ln: "Q",
        "comment": lambda c: f"{c}\n(Q-space)" if c else "(Q-space)",
        "formula": lambda orig, new, d_row: (
            f"(4*pi / {orig}[D{d_row}]) * sin(radians({orig}/2))"
        ),
    },
    "scale": {
        "setup": _wks_scale_setup,
        "col_setup": _col_scale_setup,
        "longname": lambda ln: ln,
        "comment": lambda c: f"{c}\n(Rescaled)" if c else "(Rescaled)",
        "formula": lambda orig, new, d_row: f"{new}[D{d_row}] * {orig}",
    },
    "square": {
        "setup": lambda w: None,
        "col_setup": lambda w,col: None,
        "longname": lambda ln: f"{ln}^2" if ln else "Int^2",
        "comment": lambda c: f"{c}\n(Squared)" if c else "(Squared)",
        "formula": lambda orig, new, d_row: f"{orig}^2",
    },
    "sqrt": {
        "setup": lambda w: None,
        "col_setup": lambda w,col: None,
        "longname": lambda ln: f"sqrt[{ln}]" if ln else "sqrt[Int]",
        "comment": lambda c: f"{c}\n(Sqrt)" if c else "(Sqrt)",
        "formula": lambda orig, new, d_row: f"sqrt({orig})",
    }
}

# Adds transformed columns. NEEDS REFACTORED.
def _add_columns(col_indices, transform):
    wks = op.find_sheet()

    if transform not in TRANSFORMS:
        raise ValueError(f"Unknown transform mode: {transform}")

    T = TRANSFORMS[transform]

    # Run worksheet-scoped setup hook
    d_row = T["setup"](wks)

    # Get inherited labels
    units = wks.get_labels('U')
    longnames = wks.get_labels('L')
    comments = wks.get_labels('C')
    try:
        sourcefiles = wks.get_labels('SourceFile')
    except:
        sourcefiles = [""] * wks.cols

    # main loop
    for col in reversed(col_indices):

        # add new column at end
        old_ncols = wks.cols
        wks.cols = old_ncols + 1

        # Find new column at end, define intended location for that column
        new_col_index = old_ncols
        target_index = col + 1

        # Move new column next to source column
        n = target_index - new_col_index
        wks.move_cols(n, new_col_index, 1)

        # New col is now at intended location
        new_col = target_index

        # Set long name with transform routine
        orig_ln = longnames[col] or ""
        new_ln = T["longname"](orig_ln)
        wks.set_label(new_col, new_ln, 'L')

        # Inherit units (usually AU)
        if units[col]:
            wks.set_label(new_col, units[col], 'U')

        # Inherit sourcefile
        try:
            sourcefiles = wks.get_labels('SourceFile')
        except:
            sourcefiles = [""] * wks.cols
        if len(sourcefiles) < wks.cols:
            sourcefiles += [""] * (wks.cols - len(sourcefiles))
        sourcefiles[new_col] = sourcefiles[col]
        wks.set_label(new_col, sourcefiles[new_col], 'SourceFile')

        # Set comment with transform routine
        base_comment = comments[col] or ""
        new_comment = T["comment"](base_comment)
        wks.set_label(new_col, new_comment, 'C')

        # Identify column letters for formula
        orig_letter = _col_index_to_letter(col)
        new_letter  = _col_index_to_letter(new_col)

        # Set formula with transform routine
        formula_text = T["formula"](orig_letter, new_letter, d_row)

        # Perform colum-scoped setup hook
        T["col_setup"](wks, new_col)

        wks.set_formula(new_col, formula_text)

    op.lt_exec(f'wks.labels(*D{d_row}); wks.labels(>LU); type -b "Transformed Columns Successfully";')

def transform_columns(select_mode:str, transform_mode:str):
    cols = _collect_applicable_columns(select_mode)
    _add_columns(cols,transform_mode)
