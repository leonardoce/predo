redo.utils.cmd (["dmd", "-c", "-of" + basename + ".obj", "-deps=" + basename + ".dep", basename])
deps = redo.utils.parse_dmd_dependency_file(basename + ".dep")
redo.if_changed (*deps)
