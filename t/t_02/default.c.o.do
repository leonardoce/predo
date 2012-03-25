redo.if_changed(basename)
redo.utils.cmd(["gcc", "-c", "-o", basename + ".o", basename])
