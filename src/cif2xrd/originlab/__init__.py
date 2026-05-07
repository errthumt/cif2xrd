try:
    import originpro #type: ignore
except Exception:
    raise ImportError(
        "cif2xrd.originlab requires OriginPro's embedded Python environment. "
        "This submodule cannot be imported in a normal Python interpreter."
    )

from cif2xrd.originlab._cifUtils import import_cifs_from_xf, select_cifs_and_import

from cif2xrd.originlab._rasUtils import import_ras_from_xf, select_ras_and_import

def lt_cleanup():
    import originpro as op #type: ignore

    op.lt_exec(op.get_lt_str('cleanup$'))

    op.lt_exec('string cleanup$ = "";') # Reset cleanup command variable

