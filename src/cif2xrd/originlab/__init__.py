try:
    import originpro #type: ignore
except Exception:
    raise ImportError(
        "cif2xrd.originlab requires OriginPro's embedded Python environment. "
        "This submodule cannot be imported in a normal Python interpreter."
    )

from cif2xrd.originlab._cifUtils import import_cifs_from_xf


