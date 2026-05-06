def parse_params(s):
    """
    Converts a string of comma-separated key:value pairs into a dictionary.
    For example, the string "key1:val1, key2:val2" would be converted to {"key1": "val1", "key2": "val2"}.
    If any item in the string cannot be parsed as a key:value pair, it will be skipped and an error message will be printed.
    
    Useful for passing dict args as a single argument string from other languages. Recommended to use with clean_parameters for soft type forcing.
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
    Cleans a dictionary passed as params and returns a dictionary containing only keys found in defaults.
    Coerces types to match defaults. Keys found in defaults but not params will be assigned default values.
    Type coersion not supported for complex structures like lists or tuples.
    For an example of how lists or tuples can be unpacked from string, see condense_pattern_parameters()
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
    Condenses parameters for generating patterns from a dict of key:single_value pairs
    into a dict of key:(value,value) expected by pattern constructors.
    Dicts constructed from clean_parameters() cannot contain lists or tuples.
    This function helps generate pattern parameters from clean_parameters() output.
    {doublet:bool}                           -> determines how wavelength/weight fields collapse
        doublet=True                         -> {fe_wavelengths:[wavelength1, wavelength2],
                                                fe_weights:[weight1, weight2]}
        doublet=False                        -> {fe_wavelengths:[wavelength1],
                                                fe_weights:[1.0]}

    {wavelength1:val1, wavelength2:val2}     -> contributes to {fe_wavelengths:[...]}
        if doublet=True                      -> [val1, val2]
        if doublet=False                     -> [val1]

    {weight1:val1, weight2:val2}             -> contributes to {fe_weights:[...]}
        if doublet=True                      -> [val1, val2]
        if doublet=False                     -> [1.0]

    {start_2th:start, end_2th:end}           -> {two_theta_range:(start, end)}

    {step_2th:val}                           -> {step:val}
        step_2th -> step conversion included for Origin C compatibility        
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
    Reverse of condense_pattern_parameters(). See that docstring for use case.
    {fe_wavelengths:[val1] OR [val1,val2]}   -> controls {doublet:bool}
        [val1,val2]                          -> {doublet:True,
                                                wavelength1:val1,
                                                wavelength2:val2}
        [val1]                               -> {doublet:False,
                                                wavelength1:val1,
                                                weight1:1.0,
                                                wavelength2:1.0,
                                                weight2:1.0}

    {fe_weights:[w1,w2] OR [w1]}             -> expands into:
        [w1,w2]                              -> {weight1:w1, weight2:w2}
        [w1]                                 -> {weight1:1.0, weight2:1.0}
                                            (single‑line mode ignores passed weight)

    {two_theta_range:(start,end)}            -> {start_2th:start,
                                                end_2th:end}

    {step:val}                               -> {step_2th:val}
        step -> step_2th conversion included for Origin C compatibility

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


# default pattern parameters simulate CuKa radiation with doublet splitting on a Rigaku Miniflex 600
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