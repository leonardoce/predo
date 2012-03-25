redo.if_changed("main.o", "functions.o")
redo.utils.cmd("gcc -o t01 main.o functions.o")