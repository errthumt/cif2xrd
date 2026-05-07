def parse_params(s):
    """
    Parse a comma‑separated string of key:value pairs into a dictionary.

    The input string should contain items of the form:
        "key1:val1, key2:val2, ..."

    Items that cannot be parsed as key:value pairs are skipped with a warning.
    This function is primarily intended for passing parameter dictionaries
    through command‑line interfaces or external languages.

    Args:
        s (str):
            Comma‑separated key:value string.

    Returns:
        dict:
            Dictionary mapping keys to string values.
    """

    items = s.split(',')
    out = {}
    for item in items:
        try:
            key, val = item.split(':')
            out[key.strip()] = val.strip()
        except:
            print(f"Error parsing option '{item}'. Excluding from parsed parameters")
    return out 

def clean_parameters(params, defaults={}):
    """
    Validate and type‑coerce a parameter dictionary against a defaults dictionary.

    Each key in `defaults` is guaranteed to appear in the returned dictionary.
    Missing values are filled from defaults. Values with mismatched types are
    coerced to the default type when possible; otherwise the default value is used.

    Boolean defaults accept string values ("true"/"false") and are converted
    case‑insensitively. Complex types such as lists or tuples may not be coerced correctly.

    Args:
        params (dict):
            User‑supplied parameter dictionary.
        defaults (dict):
            Dictionary defining expected keys and their default values.

    Returns:
        dict:
            A fully populated parameter dictionary with validated and coerced types.
    """
    new_params = {}
    for key in defaults:
        def_val = defaults[key]
        def_type = type(def_val)

        new_val = params.get(key)
        if not new_val:
            new_params[key] = def_val
        elif def_type == bool:
            if type(new_val) == str:
                new_params[key] = new_val.lower() == 'true'
            else:
                try:
                    new_params[key] = bool(new_val)
                except:
                    print(f"Incompatible type passed for '{key}'. Defaulting to '{def_val}'")
                    new_params[key] = def_val
        elif def_type != type(new_val):
            try:
                new_params[key] = def_type(new_val)
            except:
                print(f"Incompatible type passed for '{key}'. Defaulting to '{def_val}'")
                new_params[key] = def_val
        else:
            new_params[key] = params[key]

    return new_params


def condense_pattern_parameters(cleaned_params):
    """
    Convert expanded pattern parameters into the condensed parameter format.

    Expanded parameters (wavelength1/2, weight1/2, start_2th, end_2th, step_2th)
    are collapsed into the condensed representation:

        fe_wavelengths : list of one or two wavelengths
        fe_weights     : list of matching weights
        two_theta_range: (start_2θ, end_2θ)
        step           : step size in degrees

    The `doublet` flag determines whether one or two wavelengths are used.
    This function is typically applied to the output of `clean_parameters()`.

    Mapping summary:
        doublet=True  → fe_wavelengths=[w1, w2], fe_weights=[wgt1, wgt2]
        doublet=False → fe_wavelengths=[w1],      fe_weights=[1.0]

        start_2th, end_2th → two_theta_range
        step_2th           → step

    Args:
        cleaned_params (dict):
            Parameter dictionary in expanded format.

    Returns:
        dict:
            Condensed parameter dictionary suitable for pattern generation.
    """

    cif_params = cleaned_params.copy()
    doublet = cif_params.pop("doublet")
    wavelength1 = cif_params.pop("wavelength1")
    weight1 = cif_params.pop("weight1")
    wavelength2 = cif_params.pop("wavelength2")
    weight2 = cif_params.pop("weight2")
    start_2th = cif_params.pop("start_2th")
    end_2th = cif_params.pop("end_2th")
    step = cif_params.pop("step_2th")

    if doublet:
        cif_params["fe_wavelengths"]=[wavelength1,wavelength2]
        cif_params["fe_weights"]=[weight1,weight2]
    else:
        cif_params["fe_wavelengths"]=[wavelength1]
        cif_params["fe_weights"]=[1.0]

    cif_params["two_theta_range"] = (start_2th,end_2th)
    cif_params["step"]=step

    return cif_params

def expand_pattern_params(condensed_params):
    """
    Convert condensed pattern parameters back into the expanded parameter format.

    This reverses `condense_pattern_parameters()`. The length of
    `fe_wavelengths` determines whether the expanded representation uses
    single‑line or doublet mode.

    Mapping summary:
        fe_wavelengths=[w1, w2] → doublet=True,
                                  wavelength1=w1, wavelength2=w2,
                                  weight1=wgt1, weight2=wgt2

        fe_wavelengths=[w1]     → doublet=False,
                                  wavelength1=w1,
                                  weight1=1.0, weight2=1.0

        two_theta_range → start_2th, end_2th
        step            → step_2th

    Args:
        condensed_params (dict):
            Parameter dictionary in condensed format.

    Returns:
        dict:
            Expanded parameter dictionary validated against
            `default_params["pattern_expanded"]`.

    Raises:
        ValueError:
            If fe_wavelengths and fe_weights have mismatched lengths.
            If two_theta_range is not a 2‑tuple.
    """
    new_params = clean_parameters(condensed_params, defaults=default_params["pattern_condensed"])
    wavelengths = new_params.pop("fe_wavelengths")
    weights = new_params.pop("fe_weights")

    if len(weights) != len(wavelengths):
        raise ValueError("'fe_weights' must contain the same number of values as 'fe_wavelengths'.")
    
    if len(wavelengths) == 2:
        new_params["doublet"] = True
        new_params["wavelength1"], new_params["wavelength2"] = wavelengths
        new_params["weight1"], new_params["weight2"] = weights

    elif len(wavelengths) == 1:
        new_params["doublet"] = False
        new_params["wavelength1"] = wavelengths[0]
        new_params["weight1"] = 1.0
        new_params["wavelength2"] = 1.0
        new_params["weight2"] = 1.0
    else:
        raise ValueError("Only splitting of up to two wavelengths is supported. 'fe_wavelengths' must contain either 1 or 2 values.")
    
    two_theta_range = new_params.pop("two_theta_range")
    try:
        new_params["start_2th"], new_params["end_2th"] = two_theta_range
    except Exception:
        raise ValueError("'two_theta_range' must be a tuple containing two values: (start_2th, end_2th).")
    
    new_params["step_2th"] = new_params.pop("step")

    return clean_parameters(new_params, defaults=default_params["pattern_expanded"])


#: Default parameter sets for pattern simulation.
#:
#: This dictionary contains two parallel representations:
#:
#: - ``pattern_expanded``:
#:     The full, human‑readable parameter set using explicit fields
#:     (wavelength1/2, weight1/2, start_2th, end_2th, step_2th, U/V/W/X/Y, axial_S).
#:     Suitable for UI input, CLI parsing, or user‑facing configuration.
#:     These particular parameters were refined to match CuKa radiation on a Rigaku Miniflex 600
#:
#: - ``pattern_condensed``:
#:     The compact representation produced by ``condense_pattern_parameters``.
#:     Contains ``fe_wavelengths``, ``fe_weights``, ``two_theta_range``, and ``step``.
#:     This is the format consumed directly by ``simPattern``.
#:
#: Both dictionaries are guaranteed to stay synchronized. ``pattern_condensed`` is
#: automatically regenerated from ``pattern_expanded`` at import time.
#:
#: Users may import this object to access canonical defaults or to seed custom
#: parameter dictionaries before modification.
default_params = {
    "pattern_expanded":{
        "doublet": True,
        "wavelength1": 1.5406,
        "weight1":1.0,
        "wavelength2":1.54439,
        "weight2":0.5,
        "start_2th":3.0,
        "end_2th":90.0,
        "step_2th":0.2,
        "U":0.0,
        "V":0.0,
        "W":0.012,
        "X":0.0,
        "Y":0.0,
        "axial_S":0.015
    },
    "pattern_condensed":{} #populated by condense_pattern_parameters below
}

default_params["pattern_condensed"] = condense_pattern_parameters(default_params["pattern_expanded"])