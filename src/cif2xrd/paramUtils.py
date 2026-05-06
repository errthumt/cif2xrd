default_params = {
    "pattern":{
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
    }
}


def clean_parameters(params, defaults={}):
    new_params = {}
    for key in defaults:
        def_val = defaults[key]
        def_type = type(def_val)

        new_val = params.get(key)
        if not new_val:
            new_params[key] = def_val
        elif def_type == bool:
            new_params[key] = new_val.lower() == 'true'
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