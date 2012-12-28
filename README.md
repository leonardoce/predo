P-Redo Build System
===================
Leonardo Cecchi <leonardoce@interfree.it>

Introduction
------------

This is a simple build system inspired by DJB Redo (http://cr.yp.to/redo.html):
DJB Redo is driven by shell scripts and P-Redo is driven by Python scripts.

This build system will make you work with pleasure on Windows and on Linux.


Prerequisite
------------

* Python 3.1 or better

License
-------

This software is released under the simplified BSD license.


Installing
----------

To install P-Redo all you have to do is put it somewhere on the PATH
and then you are set.

Tutorial
--------

P-Redo mantains the dependency info in a Direct Acyclic Graph which is
memorized on an internal database. So, first of all, you should create
your database in your project main directory using:

```
$ redo.py init
$ ls _redo.db
_redo.db
```

This command will create a +_redo.db+ file which contains the initial
database which will be populated with the dependencies in your
projects.

Now, let's say you want to compile your basic C hello world using
P-Redo. Let's say you have an +hello.c+ like this:

```
#include <stdio.h>

int main(int argc, char **argv) {
  printf("This is a simple test.\n");
  return 0;
}
```

To compile it to an object file you should create a +default.c.o+ like
this:

```
redo.if_changed(basename) <1>
redo.utils.cmd(["gcc", "-c", "-o", basename + ".o", basename]) <2>
```

The +default.c.o+ will be applied when a file like +a.c.o+ is needed
by the build system.

This little script basically says, on <1>, that this same script has
to be re-executed when the source code has changed. To cite the
filename the script uses the predefined variable +basename+ which is
the basename the name of the target being processed without the last
extension so, if you are building +hello.c.o+ the basename will be
+hello.c+.

The second line (<2>) says the command needed to compile the file.

Let's try it using the +build+ subcommand:

```
$ redo.py build hello.c.o
  /home/leonardo/src/predo/t/t_02/hello.c.o
$ ls hello.c.o
hello.c.o
```

Wow! It seem to be working. Now I should link this object file with
all the associated libraries to an executable. Instead of a default
build-script I will use a specific one and create this +hello.do+
script file:

```
redo.if_changed("hello.c.o")
redo.utils.cmd("gcc -o hello hello.c.o")
```

At this point, the meaning of the script should be obvious. The target
must be rebuild when the +hello.c.o+ file changes and the second line
it's simply the command needed to link it. Let's try:

```
$ redo.py build hello
  /home/leonardo/src/predo/t/t_02/hello
$ ./hello
This is a simple test.
$ 
```

It seems to be ok. As you see P-Redo hasn't rebuild +hello.c.o+ file
because if was already build.

If I need I could also use P-Redo to clean all the generated files:

```
$ redo.py clean
Cleaning /home/leonardo/src/predo/t/t_02/hello.c.o
Cleaning /home/leonardo/src/predo/t/t_02/hello
$ 
```

We haven't considered yet the dependencies from the header files,
which are a bit of trouble for +make+, because there actually depends
from the header files used in your source files. We can use the +-M+
flag of the GNU compiler:

```
$ gcc -M hello.c
hello.o: hello.c \
 c:\mingw\bin\../lib/gcc/mingw32/4.6.2/../../../../include/stdio.h \
 c:\mingw\bin\../lib/gcc/mingw32/4.6.2/../../../../include/_mingw.h \
 c:\mingw\bin\../lib/gcc/mingw32/4.6.2/include/stddef.h \
 c:\mingw\bin\../lib/gcc/mingw32/4.6.2/include/stdarg.h \
 c:\mingw\bin\../lib/gcc/mingw32/4.6.2/../../../../include/sys/types.h

$
```

and use this output to populate the dependency graph using the
predefined P-Redo functions modifying +default.c.o+:

```
redo.utils.cmd(["gcc", "-c", "-o", basename + ".o", basename])
deps_string = redo.utils.cmd_output(["gcc", "-M", basename])
deps = redo.utils.parse_makefile_dependency(deps_string)
deps.append (basename)
redo.if_changed(*deps)
```

