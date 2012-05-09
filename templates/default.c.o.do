redo.utils.cmd(["gcc", "-c", "-o", basename + ".o", basename])
deps_string = redo.utils.cmd_output(["gcc", "-M", basename])
deps = redo.utils.parse_makefile_dependency(deps_string)
deps.append (basename)
redo.if_changed(*deps)