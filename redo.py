#!/usr/bin/env python3
import argparse
import doctest
import fnmatch
import os
import os.path
import subprocess
import sys
import pickle

# Things to do
# ============
#
# * Cross platform build support? How can I solve the different exe suffix of Windows and Linux?
#   Actually, the .exe suffix also works in Linux but is awful. Maybe the "virtual" targets comes
#   handy here. Perhaps we can have a "text.exe" target which will build the "test" file under
#   Posix and "test.exe" under Windows. Boh...
# * Generate a clean script and keep it updated
# * External documentation using AsciiDoc
# * Concurrent build??
# * Study on absolute paths

# {{{ Common data structures
# ==========================

class RedoException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class Graph(object):
    """
    This class reprents a DAG where nodes are target
    and arcs connect to targest t1->t2 if t1 depends 
    on t2
    
    >>> g = Graph()
    >>> g.store_dependency("a", "b")
    >>> for x in g.get_transitive_dependencies("a"): print x
    a
    b
    >>> g.store_dependency("c", "d")
    >>> for x in g.get_transitive_dependencies("c"): print x
    c
    d
    >>> g.store_dependency("c", "d")
    >>> for x in g.get_transitive_dependencies("c"): print x
    c
    d
    >>> g.clear_dependency_info_for("c")
    >>> for x in g.get_transitive_dependencies("c"): print x
    c
    """
    def __init__(self):
        self.store = {}
        self.node_assoclist = {}
        self.name_assoclist = {}

    def _ensure_node(self, t):
        t_idx = self.node_assoclist.get(t)
        if t_idx == None:
            t_idx = len(self.node_assoclist)
            self.node_assoclist[t] = t_idx
            self.name_assoclist[t_idx] = t
        return t_idx

    def store_dependency(self, t1, t2):
        """
        This method appends a dependency from t1 to t2
        is the dependency doesn't already exists
        """
        idx_t1 = self._ensure_node(t1)
        idx_t2 = self._ensure_node(t2)
        
        deplist = self.store.get(idx_t1)
        if deplist==None:
            self.store[idx_t1]=[idx_t2]
        else:
            if idx_t2 not in deplist:
                deplist.append(idx_t2)

    def clear_dependency_info_for(self, t):
        """
        This method will remove all the arcs from "t"
        """
        idx_t = self._ensure_node(t)
        if idx_t in self.store:
            self.store[idx_t]=[]

    def get_transitive_dependencies(self, t):
        """
        This method will iterate into the graph and find
        all the dependencies of the passed target
        """
        t_idx = self._ensure_node(t)
        to_check = [t_idx]
        checked = []
        while 1:
            if len(to_check)==0: break
            current = to_check[0]
            to_check = to_check[1:]
            
            checked.append(to_check)
            yield self.name_assoclist[current]
            
            deplist = self.store.get(current)
            if deplist!=None: to_check += deplist
          
    def to_tgf(self, file):
        """
        This method will iterate throught all the
        arcs
        """
        fileList = []
        for key in self.node_assoclist.keys():
            print (self.node_assoclist[key], key, file=file)
            
        print ("#", file=file)
        
        for source in self.store.keys():
            for dest in self.store[source]:
                print (source,dest, file=file)

class FileCache(object):
    """
    This class will contain the latest modification
    time of files
    """
    def __init__(self):
        self.store = {}
        self.changed_status = {}
        
    def reset_changed_cache(self):
        """
        Reset the changed files cache
        """
        self.changed_status = {}
        
    def stamp(self, fileName, fileType):
        """
        Memorize the timestamp of a file
        """
        self.store[fileName] = {"timestamp":os.path.getmtime(fileName), "fileType":fileType}

    def is_changed(self, fileName):
        """
        Check a file with the timestamp. If it
        is changed or if the file wasn't timestamped
        then return true. Else false.
        """
        if not self.is_known(fileName): raise RedoException("I don't know this target: " + fileName)
        if not os.path.exists(fileName): return True
        
        if fileName in self.changed_status:
            return self.changed_status[fileName]
            
        mt = os.path.getmtime(fileName)
        
        if not (fileName in self.store):
            result = True
        else:
            result = mt!=self.store[fileName]["timestamp"]
            
        self.changed_status[fileName] = result
        return result
        
    def is_known(self, fileName):
        """
        Return true if this fileName is known in this
        cache file
        """
        status = (fileName in self.store)
        return status
        
    def get_type(self, fileName):
        """
        Return the file type of the fileName passed.
        If this file isn't in the store return None
        """
        dict = self.store[fileName]
        if dict!=None: 
            return dict["fileType"]
        else:
            return None


    def get_destinations(self):
        """
        Iterate throught the destinations
        """
        for target in self.store.keys():
            if self.store[target]["fileType"]=="d": yield target


    def get_files(self):
        """
        Iterate throught the filenames
        """
        return self.store.keys()
        
    def test_get_store(self):
        return self.store
        
# }}}        
        
# {{{ This functions will find the correct script for a target
# ============================================================

def generate_script_for__basenames(baseName):
    """
    This function will generate all the possible basenames
    for one target.

    >>> for x in generate_script_for__basenames("testing.c.o"): print x
    testing.c.o.do
    default.c.o.do
    default.c.do
    default.do
    """
    l = baseName.split(".")

    yield ".".join(l) + ".do"
    l[0]="default"
    for x in range(len(l),0,-1):
        yield ".".join(l[0:x]) + ".do"

def generate_scripts_for(fileName):
    """
    This function will generate all the possible script
    names for a target
    
    >>> for x in generate_scripts_for("a/b/c/d/testing.c.o"): print x
    a/b/c/d/testing.c.o.do
    a/b/c/d/default.c.o.do
    a/b/c/d/default.c.do
    a/b/c/d/default.do
    a/b/c/testing.c.o.do
    a/b/c/default.c.o.do
    a/b/c/default.c.do
    a/b/c/default.do
    a/b/testing.c.o.do
    a/b/default.c.o.do
    a/b/default.c.do
    a/b/default.do
    a/testing.c.o.do
    a/default.c.o.do
    a/default.c.do
    a/default.do
    testing.c.o.do
    default.c.o.do
    default.c.do
    default.do
    """
    
    (directory, baseName) = os.path.split(fileName)

    last_directory = directory
    while 1:
        for currBase in generate_script_for__basenames(baseName):
            if last_directory=="":
                yield currBase
            else:
                yield last_directory + "/" + currBase
        
        (next_directory, name) = os.path.split(last_directory)
        if next_directory==last_directory: break
        last_directory = next_directory

def find_script_for(target):
    tests = []
    for x in generate_scripts_for(target):
        tests.append(x)
        if os.path.exists(x):
            return x

    msg = "Cannot find script for target " + target + "\n"
    msg += "Tryed: \n" + "\n".join(tests)
    raise RedoException(msg)

# }}}

# {{{ Logging commands
# ====================

# {{{ Logging subsystem
# ~~~~~~~~~~~~~~~~~~~~~
class Logging(object):
    def __init__(self):
        self.logging_clean = True
        self.logging_cmd = False
        self.logging_target = True
        self.logging_debug = False

    def configure_from_logging_level(self, loglevel):
        self.logging_clean = False
        self.logging_cmd = False
        self.logging_target = False
        self.logging_debug = False
        
        if loglevel >=1:
            self.logging_target = True
            self.logging_clean = True
        if loglevel >=2:
            self.logging_cmd = True
        if loglevel >=3:
            self.logging_debug = True
        
    def format_command(self, cmdArgs):
        """
        Get the readable format of a command argument
        """
        def format_arg(x):
            if " " in x or "\"" in x:
                return "\"" + x.replace("\"", "\\\"") + "\""
            else:
                return x
                
        if type([])==type(cmdArgs):
            verboseCmd = " ".join(map(format_arg, cmdArgs))
        else:
            verboseCmd = cmdArgs
        return verboseCmd
        
    def clean(self, target):
        if not self.logging_clean: return
        print ("Cleaning", target)
        
    def command(self, cmdArgs):
        if not self.logging_cmd: return
        verboseCmd = self.format_command(cmdArgs)
        print (verboseCmd)
        
    def error(self, exc):
        print ("ERROR: ", str(exc), file=sys.stderr)
        
    def target(self, depth, name):
        if not self.logging_target: return
        print (" "*depth, name)
        
    def debug(self, msg):
        if not self.logging_debug: return
        print (">",msg)
# }}}

# {{{ Current logging subsystem
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
_default_logging_subsystem = Logging()
def get_logging_subsystem():
    return _default_logging_subsystem
# }}}

# }}}

# {{{ Utilities passed to scripts
# ===============================

class Utilities(object):
    def __init__(self):
        self.logging = get_logging_subsystem()
        
    def parse_makefile_dependency(self, deps):    
        """
        Parse the passed string as a makefile 
        dependency. Useful for parsing the output
        of "gcc -M". This function will return a list
        of every dependent file
        """
        # let's hope in the utf8 encoding
        if type(deps)==type(b""): deps = deps.decode("utf-8")
        deps = deps.split("\n")[1:]
        deps_collection = []
        for dep in deps:
            dep = dep.strip()
            if len(dep)>0:
                if dep[-1]=="\\": dep = dep[0:-1]
                dep = dep.strip()
                
                if os.path.exists(dep):
                    deps_collection.append(dep)
                
        return deps_collection

    def parse_dmd_dependency_file(self, depFile):
        """
        Read a depFile generated by dmd -deps=depFile
        directive from the DMD2 compiler
        """
        
        dipendenze = []

        f = open(depFile)
        for linea in f:
          linea = linea.strip()
          inizio = linea.find("(")
          fine = linea.find(")")
    
          if inizio==-1 or fine==-1:
            throw(Exception(linea))
      
          linea = linea[inizio+1:fine]  
          linea = linea.replace("\\\\", "\\")
          if linea not in dipendenze:
            dipendenze.append(linea)
    	
          return dipendenze
        
    def find_files(self, directory, pattern):
        """
        Kinda-glob but recursive
        """
        for root, dirs, files in os.walk(directory):
            for basename in files:
                if fnmatch.fnmatch(basename, pattern):
                    filename = os.path.join(root, basename)
                    yield filename    
        
    def find_executable(self, executable, path=None):
        """
        Try to find 'executable' in the directories listed in 'path' (a
        string listing directories separated by 'os.pathsep'; defaults to
        os.environ['PATH']).  Returns the complete filename or None if not
        found
        """
        if path is None:
            path = os.environ['PATH']
        paths = path.split(os.pathsep)
        extlist = ['']
        if os.name == 'os2':
            (base, ext) = os.path.splitext(executable)
            # executable files on OS/2 can have an arbitrary extension, but
            # .exe is automatically appended if no dot is present in the name
            if not ext:
                executable = executable + ".exe"
        elif sys.platform == 'win32':
            pathext = os.environ['PATHEXT'].lower().split(os.pathsep)
            (base, ext) = os.path.splitext(executable)
            if ext.lower() not in pathext:
                extlist = pathext
        for ext in extlist:
            execname = executable + ext
            if os.path.isfile(execname):
                return execname
            else:
                for p in paths:
                    f = os.path.join(p, execname)
                    if os.path.isfile(f):
                        return f
        else:
            return None    
        
    def cmd(self, args):
        """
        Run a command. The command and the output will be
        shown only of the result of the command is wrong
        """
        self.logging.command(args)
        try:
            if type(args)==type([]):
                errorcode = subprocess.call(args)
            else:
                errorcode = subprocess.call(args, shell=True)
        except Exception as e:
            raise RedoException(str(e))
            
        if errorcode!=0:
            self.logging.error(self.logging.format_command(args))
            raise RedoException("compilation failed with exit code " + str(errorcode))
                

    def cmd_output(self, args):
        """
        Run a command and capture the stdout which will be
        returned as a string
        """
        self.logging.command(args)
        try:
            if type(args)==type([]):
                return subprocess.check_output(args)
            else:
                return subprocess.check_output(args, shell=True)
        except Exception as e:
            raise RedoException(str(e))
# }}}
        
# {{{ Redo commands
# =================

class Redo(object):
    def __init__(self):
        self.graph = Graph()
        self.file_cache = FileCache()
        self.contexts = []
        self.logging = get_logging_subsystem()
        self.utils = Utilities()
        self.built_targets = []
        self._current_db_version = 1

    # Read and write graph to file
    # ----------------------------
    
    def write_status_to_file(self, fileName):
        """
        Write the current build status to a file
        """
        self.file_cache.reset_changed_cache()
        self.built_targets = []
        
        f = open(fileName, "wb")
        pickle.dump(self._current_db_version, f)
        pickle.dump(self.graph, f)
        pickle.dump(self.file_cache, f)
        f.close()
        
    def read_status_from_file(self, fileName):
        """
        Read the current build status to a file
        """
        f = open(fileName, "rb")
        dbver = pickle.load(f)
        
        if dbver!=self._current_db_version:
            raise RedoException("Wrong _redo.db version. Please regenerate it from scratch")
            
        self.graph = pickle.load(f)
        self.file_cache = pickle.load(f)
        f.close()
        self.rootdir = os.path.dirname(fileName)

    # Script execution and contexts
    # -----------------------------

    def _create_context(self, scriptName, targetName):
        context = {"target":targetName, 
            "basename":os.path.splitext(targetName)[0], 
            "redo":self,
            "scriptname":scriptName
        }
        return context
        
    def _exec_script(self, scriptName, targetName):
        (scriptPath, scriptBasename) = os.path.split(scriptName)
        
        cwd = os.getcwd()
        if scriptPath != "": os.chdir(scriptPath)
        ctx = self._create_context(scriptName, targetName)
        self.contexts.append(ctx)
        self.logging.target(len(self.contexts), targetName)
        try:
            exec(compile(open(scriptBasename).read(), scriptBasename, 'exec'), ctx)
        finally:
            self.contexts.pop()
            os.chdir(cwd)
            
    def _current_context(self):
        return self.contexts[-1]
        
    # Redo commands
    # -------------
            
    def redo(self, targetName):
        """
        This function will always rebuild the target
        "targetName"
        """
        targetName = os.path.abspath(targetName)
        
        if targetName not in self.built_targets:
            scriptName = find_script_for(targetName)
            self.file_cache.stamp(scriptName, "s")
            self.graph.store_dependency(targetName, scriptName)
            self._exec_script(scriptName, targetName)
            self.built_targets.append(targetName)
            
            if os.path.exists(targetName):
                self.file_cache.stamp(targetName, "d")

    def if_changed(self, *targetNames):
        """
        This function will append to the current target
        a dependency versus name choosen in "targetNames" and
        will rebuild it if the dependencies are outdate.
        """
        self.graph.clear_dependency_info_for(self._current_context()["target"])
        self.graph.store_dependency(self._current_context()["target"], self._current_context()["scriptname"])
        for argument in targetNames:
            self._if_changed_file(argument)
        
    def _if_changed_file(self, argument):
        """
        As if_changed but for only one file
        """
        argument = os.path.abspath(argument)
        if not self.file_cache.is_known(argument):
            if os.path.exists(argument):
                currentType = "s"
            else:
                currentType = "d"
        else:
            currentType = self.file_cache.get_type(argument)

        current = self._current_context()["target"]
        if argument != current: 
            self.graph.store_dependency(current, argument)

        if currentType=="s":
            self.file_cache.stamp(argument, currentType)
        elif currentType=="d" and (not self.file_cache.is_known(argument)):
            self.redo(argument)
        elif currentType=="d" and self.file_cache.is_known(argument):
            to_rebuild = False
            to_rebuild_cause = ""
            for dep in self.graph.get_transitive_dependencies(argument):
                if self.file_cache.is_changed(dep):
                    to_rebuild = True
                    to_rebuild_cause = dep
                    break
                    
            if to_rebuild:
                # print "target",argument,"must be rebuild because",to_rebuild_cause,"changed"
                self.redo(argument)

    def clean(self):
        for target in self.file_cache.get_destinations():
            if os.path.exists(target):
                self.logging.clean(target)
                os.unlink(target)
                
    def tgf_graph(self):
        """
        This function output a graph description in TGF 
        format.
        """
        self.graph.to_tgf(sys.stdout)
# }}}        
            
# {{{ Redo database management
# ============================

def redo_database_default_name():
    "Return the default name of the redo database"
    return "_redo.db"

def find_redo_database():
    """
    This function will search for a redo database in the current
    directory and in all the parent directories
    """
    thisDirectory = os.path.abspath(os.getcwd())
    db_name = redo_database_default_name()
    tests = []
    
    curdir = thisDirectory
    while 1:
        curdb = os.path.join(curdir, db_name)
        tests.append(curdb)
        if os.path.exists(curdb):
            return curdb
            
        (n_curdir,_) = os.path.split(curdir)
        if n_curdir==curdir: break
        curdir = n_curdir
        
    msg = "Cannot find redo database. You must create it using the \"init\" command. I tryed\n"
    for x in tests: msg += x + "\n"
    raise RedoException (msg)
# }}}

# {{{ Main commands
# =================

def main_test():
    print ("testing...")
    doctest.testmod()
    
def main_clean():
    redo = Redo()
    dbname = find_redo_database()
    redo.read_status_from_file(dbname)
    redo.clean()
    redo.write_status_to_file(dbname)

def main_graph():
    redo = Redo()
    dbname = find_redo_database()
    redo.read_status_from_file(dbname)
    redo.tgf_graph()

def main_init():
    redo = Redo()
    default_db = redo_database_default_name()
    if not os.path.exists(default_db):
        redo.write_status_to_file(default_db)
    else:
        get_logging_subsystem().error("Database file (" + default_db + ") already exists")
        
def main_redo(targetName):
    redo = Redo()
    dbname = find_redo_database()
    redo.read_status_from_file(dbname)
    try:
        redo.redo(targetName)
    finally:
        redo.write_status_to_file(dbname)

def main_argparse():
    # Main command parser
    parser = argparse.ArgumentParser(prog=sys.argv[0])
    parser.add_argument("--logging-level", dest="logging_level", type=int, 
        nargs=1, help="0 means quiet, 5 means really verbose. The default is 1", 
        default=1)
    subparsers = parser.add_subparsers(help="sub-command help", dest="command_name")
    
    # Parser for the "init" command
    parser_init = subparsers.add_parser("init", help="create a new redo database file")
    
    # Parser for the "clean" command
    parser_init = subparsers.add_parser("clean", help="remove all the generated targets")
    
    # Parser for the "tgf" command
    parser_tgf = subparsers.add_parser("tgf", help="generate a tgf file from the build system graph")
    
    # Parser for the "build" command
    parser_build = subparsers.add_parser("build", help="build a target")
    parser_build.add_argument("target", help="target to build")
    
    # Parse the command line arguments
    parameters = parser.parse_args(sys.argv[1:])
    
    # Configuring the logging subsystem
    if type(parameters.logging_level)==type([]):
        log_level = parameters.logging_level[0]
    else:
        log_level = parameters.logging_level

    get_logging_subsystem().configure_from_logging_level(log_level)
    
    # Invoke the right command
    if parameters.command_name == "init":
        main_init()
    elif parameters.command_name == "clean":
        main_clean()
    elif parameters.command_name == "tgf":
        main_tgf()
    elif parameters.command_name == "build":
        main_redo(parameters.target)
    

if __name__=="__main__": 
    # Check the current python version.
    # It must be at least 2.7 because we use "argparse"
    # to parse the command line arguments
    if sys.version_info.major<2 or (sys.version_info.major==2 and sys.version_info.minor<7):
        print ("This software requires Python 2.7 or better! Please update your Python interpreter", file=stderr)
    else:
        try:
            main_argparse()
        except RedoException as e:
            print (e, file=sys.stderr)

# }}}
