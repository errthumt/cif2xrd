import originpro as op

op.lt_exec(op.get_lt_str('cleanup$'))

op.lt_exec('string cleanup$ = "";') # Reset cleanup command variable