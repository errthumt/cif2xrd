# cif2xrd
A python package for simulating X-ray powder diffraction patterns from CIF files. Adds peak broadening and phase fraction scaling to existing pymatgen features.

The main modules, `cif2xrd.pattern` and `cif2xrd.paramUtils` are usable in any python environment >= 3.10
**This project is actively being developed with more documentation to follow.**

The `cif2xrd.originlab` module is usable only in the embedded python in OriginLab's OriginPro software. It wraps the main simulation modules into commands that can import simulated data directly into OriginPro, as well as apply useful transformations, like:
* Dynamically scaling by phase fraction.
* Adding dynamic X columns in Q-space instead of 2θ.
* Square or Square-root intensities.
* Import experimental data in matching format (currently only supported for Rigaku *.RAS file format)

`cif2xrd.originlab` is specifically designed to work with my [Origin-PXRD](https://errthumt.github.io/Origin-PXRD/) plugin, which utilizes the module to add dropdown menus and other features to OriginPro.
