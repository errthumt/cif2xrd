import warnings

# Axes3D is not included with Origin's native matplotlib, but it is not necessary for this package
warnings.filterwarnings(
    "ignore",
    message="Unable to import Axes3D",
    category=UserWarning,
    module="matplotlib.projections"
)

import os
import sys

import numpy as np
from pymatgen.io.cif import CifParser
from pymatgen.core import Structure
from pymatgen.core.periodic_table import Element
from pymatgen.analysis.diffraction.xrd import XRDCalculator

import cif2xrd.paramUtils as pUtl

def _tch_pseudo_voigt(two_theta, t0, H_G, H_L):
    """
    Compute the Thompson–Cox–Hastings (TCH) pseudo-Voigt peak profile.

    This function evaluates a normalized pseudo-Voigt line shape centered at
    `t0`, using Gaussian (H_G) and Lorentzian (H_L) FWHM components combined
    through the TCH mixing approximation.

    Args:
        two_theta (np.ndarray):
            Array of 2θ values at which the peak shape is evaluated.
        t0 (float):
            Peak center position in degrees 2θ.
        H_G (float):
            Gaussian FWHM component from the Caglioti equation.
        H_L (float):
            Lorentzian FWHM component from the Caglioti equation.

    Returns:
        np.ndarray:
            Normalized pseudo-Voigt profile evaluated at `two_theta`.
    """

    H = (H_G**5 + 2.69269*H_G**4*H_L + 2.42843*H_G**3*H_L**2 +
         4.47163*H_G**2*H_L**3 + 0.07842*H_G*H_L**4 + H_L**5)**0.2

    eta = 1.36603*(H_L/H) - 0.47719*(H_L/H)**2 + 0.11116*(H_L/H)**3
    eta = np.clip(eta, 0, 1)

    sigma = H / (2*np.sqrt(2*np.log(2)))
    gamma = H / 2

    G = np.exp(-((two_theta - t0)**2) / (2*sigma**2))
    L = 1 / (1 + ((two_theta - t0)/gamma)**2)

    pv = eta * L + (1 - eta) * G
    pv /= pv.sum() + 1e-12
    return pv

def _fcj_asymmetry(two_theta, t0, H, S=0.015):
    """
    Compute the Finger–Cox–Jephcoat (FCJ) axial divergence asymmetry factor.

    This is the Gaussian approximation to the FCJ model, which introduces
    low-angle peak tailing due to axial divergence in Bragg–Brentano geometry.

    Args:
        two_theta (np.ndarray):
            Array of 2θ values at which the asymmetry factor is evaluated.
        t0 (float):
            Symmetric peak position (before asymmetry) in degrees 2θ.
        H (float):
            Effective FWHM of the peak (typically the Gaussian component).
        S (float, optional):
            Axial divergence parameter. Defaults to 0.015.

    Returns:
        np.ndarray:
            Multiplicative asymmetry factor applied to the peak shape.
    """

    delta = S * np.tan(np.radians(t0/2))
    shift = delta * (two_theta - t0)
    return np.exp(-shift**2 / (2*H**2))

def _compute_Z(structure=None, cif_path=None):
    """
    Determine the number of formula units per unit cell (Z).

    The function attempts to extract Z directly from the CIF file using the
    `_cell_formula_units_Z` field or common variants. If no such field is
    present, Z is computed from the pymatgen Structure object as:

        Z = (number of atoms in unit cell) / (atoms in reduced formula)

    Args:
        structure (pymatgen.core.Structure, optional):
            Structure object already loaded from a CIF. Required if
            `cif_path` is not provided.
        cif_path (str, optional):
            Path to the CIF file. Used to extract Z directly if possible.

    Returns:
        float:
            Formula units per unit cell.

    Raises:
        ValueError:
            If neither `structure` nor `cif_path` is provided.
    """
    # --- Case 1: Try reading Z directly from CIF ---
    if cif_path is not None:
        parser = CifParser(cif_path)
        cif_blocks = parser.as_dict()  # dict of CIF blocks

        # Usually only one block, but loop safely
        for block in cif_blocks.values():
            # Try the canonical key
            if "_cell_formula_units_Z" in block:
                try:
                    return float(block["_cell_formula_units_Z"])
                except Exception:
                    pass

            # Try common variants (CIFs are messy)
            for key in block.keys():
                if key.lower().endswith("formula_units_z"):
                    try:
                        return float(block[key])
                    except Exception:
                        pass

        # If we reach here, CIF did not contain Z → fall back

        structure = parser.get_structures()[0]

    # --- Case 2: Compute Z from Structure ---
    if structure is None:
        raise ValueError("Either structure or cif_path must be provided.")

    comp = structure.composition
    full_atoms = comp.num_atoms
    formula_atoms = comp.reduced_composition.num_atoms

    return full_atoms / formula_atoms

class simPattern:
    """
    Simulates a powder XRD pattern from a CIF structure.

    Attributes:
        params (dict):
            The parameter dictionary used to generate the pattern.
        structure (pymatgen.core.Structure):
            Crystal structure loaded from the CIF file.
        Z (float):
            Formula units per unit cell.
        molWeight (float):
            Molecular weight of a formula unit (amu).
        cell_volume (float):
            Unit cell volume (Å³).
        two_theta (np.ndarray):
            Array of simulated 2θ values.
        intensity (np.ndarray):
            Array of simulated intensities corresponding to `two_theta`.

    Methods:
        set_parameters(**kwargs):
            Update simulation parameters and recompute the pattern.
        save_pattern(filepath):
            Save the simulated pattern to a text file.
    """
    def __init__(self, cif_path, param_type="condensed", **kwargs):
        """
        Initialize a simPattern object and compute the powder pattern.

        Args:
            cif_path (str):
                Path to the CIF file containing the crystal structure.
            param_type ({"condensed", "expanded"}):
                Format of the parameters supplied in `kwargs`.
                - "condensed": expects fe_wavelengths, fe_weights, two_theta_range, step, U/V/W/X/Y, axial_S.
                - "expanded": expects wavelength1/2, weight1/2, start_2th, end_2th, step_2th, U/V/W/X/Y, axial_S.
                See `paramUtils.condense_pattern_parameters()` for details.
            **kwargs:
                Simulation parameters. Missing values are filled from defaults.
                Type-coerced by `paramUtils.clean_parameters()`

                Condensed parameters:
                    fe_wavelengths (list[float]):
                        One value for single-wavelength mode, two values for Kα doublet.
                    fe_weights (list[float]):
                        Relative weights; must match length of fe_wavelengths.
                    two_theta_range (tuple[float, float]):
                        (start_2θ, end_2θ) in degrees.
                    step (float):
                        Step size in degrees.
                    U, V, W, X, Y, axial_S (float):
                        Peak-shape parameters passed to the TCH pseudo-Voigt and FCJ asymmetry models.
        """

        self.structure = Structure.from_file(cif_path)
        self.Z = _compute_Z(self.structure, cif_path)
        self.molWeight = float(self.structure.composition.weight / self.Z)
        self.cell_volume = self.structure.lattice.volume

        self.params = pUtl.default_params["pattern_condensed"]
        self.set_parameters(param_type=param_type, **kwargs)


    def _calculate_pattern(self,
                 fe_wavelengths,
                 fe_weights,
                 two_theta_range=(0, 90),
                 step=0.02,
                 U=0.0,
                 V=0.0,
                 W=0.012,
                 X=0.0,
                 Y=0.0,
                 axial_S=0.015):

        structure = self.structure
        Z = self.Z
        cell_volume = self.cell_volume

        # Build list of B values for each atom site
        atom_B = []
        pi2 = np.pi**2
        for site in structure.sites:
            props = site.properties
            if "B_iso" in props:
                B = props["B_iso"]
            elif "Uiso" in props:
                B = 8 * pi2 * props["Uiso"]
            elif "Ueq" in props:
                B = 8 * pi2 * props["Ueq"]
            else:
                B = 0.0
            atom_B.append(B)

        # Generate 2theta column and empty intensity column of same length.
        tmin, tmax = two_theta_range
        two_theta = np.arange(tmin, tmax + step, step)
        intensity = np.zeros_like(two_theta)
        fe_weights = np.array(fe_weights)/np.sum(fe_weights)
        
        # Generate intensity as the sum of all fe intensities by weights.
        for wl, wt in zip(fe_wavelengths, fe_weights):
            # Basic reflections calculated using pymatgen's XRDCalculator.get_pattern()
            xrd = XRDCalculator(wavelength=wl)
            pattern = xrd.get_pattern(structure, two_theta_range=two_theta_range, scaled=False)

            # Modify reflections with scattering factors
            for idx, (t0, I0) in enumerate(zip(pattern.x, pattern.y)):
                # Useful constants
                theta = np.radians(t0 / 2)
                sin_th = np.sin(theta)
                cos_th = np.cos(theta)
                    
                # Useful constants
                s = sin_th / wl
                pi2 = np.pi**2

                # Debye-Waller damping by B-factors
                DW_atoms = np.mean([np.exp(-2 * pi2 * B * s**2) for B in atom_B])

                # Modify base intensity with damping
                I0 *= DW_atoms #* DW_extra
                I0 /= Z
                I0 /= cell_volume

                # Caglioti broadening: Gaussian (H_G) and Lorentzian (HL) hybrid
                H_G = np.sqrt(U*np.tan(theta)**2 + V*np.tan(theta) + W)
                H_L = X*np.tan(theta) + Y/np.cos(theta)

                # Each peak is calculated indepedently as a function of all 2theta values.
                pv = _tch_pseudo_voigt(two_theta, t0, H_G, H_L)
                asym = _fcj_asymmetry(two_theta, t0, H_G, S=axial_S)

                # Peak is a normalized Voight-shape, with tailing added, multiplied by intensity and wavelength weight.
                # Each individual peak is constructed as a function of all 2theta values. They are all overlaid onto the intensity series.
                intensity += wt * I0 * pv * asym

        return two_theta, intensity
    
    def _refresh_pattern(self):
        self.two_theta, self.intensity = self._calculate_pattern(**self.params)

    def set_parameters(self, param_type="condensed", **kwargs):
        if param_type == "expanded":
            current = pUtl.expand_pattern_params(self.params)
            expanded = pUtl.clean_parameters(params=kwargs, defaults=current)
            self.params = pUtl.condense_pattern_parameters(expanded)
        else:
            current = self.params
            self.params = pUtl.clean_parameters(params=kwargs,defaults=current)

        self._refresh_pattern()

    def save_pattern(self, filepath):
        data = np.column_stack((self.two_theta, self.intensity))
        np.savetxt(filepath, data, header="TwoTheta Intensity", comments="")