# Attempted generic cython caller.
# Usage: python cyrun.py <cython_file_name>.py
# First stable version (except comments) 19-12-2014
# Lots of changes 17-10-2015
# More changes 24/25-10-2015

import sys
import re
import time
import os
import subprocess

def message(verbose, s, s2=""):
    if verbose==1 or verbose>1 and s2=="":
        sys.stderr.write(s)
    elif verbose>1:
        sys.stderr.write(s2)

###########
# build 
"""
example code
input:

#cy+
#cpdef count(int a):
#cy-
def count(a):
    #cy+
    #cdef double x, y
    #cy.

output:

#cy+
cpdef count(int a):
#cy-
#def count(a):
    #cy+
    cdef double x, y
    #cy.

Can also use #cy: to cythonise a single line without impacting later lines

"""

# fname will end in .py
# writes to prefix+fname+"x"
def build(fname, prefix, switch_verbose): 
    ip = open(fname, "r")
    olist = []
    olist.append("########################\n")
    olist.append("# Automatically created from %s by cyrun.py on %s\n" % (fname, time.asctime()))
    olist.append("########################\n")
    add = 0
    for line in ip.readlines():
        command = line.lstrip() # remove leading whitespace
        if command[:3]=="#cy":
            #olist.append(line) <-- rewriting the #cy directive is too messy, IMO
            if command[:4]=="#cy:":
                olist.append(line.replace("#cy:", "", 1))
            elif command[:4]=="#cy+":
                add = 1 # add for cython - remove first "#"
            elif command[:4]=="#cy-":
                add = -1 # remove for cython - add a "#" before first non-whitespac
            elif command[:4]=="#cy.":
                add = 0 # do nothing
            else:
                raise Exception("unrecognised conversion line\n" + line)
        elif line.count("#cy<"):
            words = line.split("#")
            if words[1][:3]=="cy<":
                extra = words[1][3:]
                whitespace = (len(line) - len(line.lstrip())) * " "
                olist.append(whitespace + extra + line.lstrip())
            else:
                # '#cy<' ignored if it's not the first comment
                pass
        else:
            if add==1:
                olist.append(line.replace("#", "", 1))
            elif add==-1:
                pass # remove line
            else:
                olist.append(line)
    ip.close()
    imports = []
    for i in range(len(olist)):
        line = olist[i]
        words = line.split("#")[0].split()
        if len(words)>=2 and words[0]=="import":
            if os.path.exists(words[1]+".py"):
                imports.append(words[1])
                words = line.split()
                olist[i] = "import " + prefix + " ".join(words[1:]) + "\n"
    message(switch_verbose, "", "%s imports = %s\n" % (fname, imports))
    for i in range(len(olist)):
        line = olist[i]
        for impfile in imports:
            # need to parse carefully so that we don't modify strings
            #if line.find(impfile + ".")==0:
            #    line = prefix + line
            #olist[i] = re.sub(r"(\W)"+impfile+r"\.", r"\1" + prefix+impfile+".", olist[i])
            for loops in range(line.count(impfile+".")): # line.count(impfile+".") is max possible replacements
                inquotes = 0
                for j in range(len(line)):
                    if inquotes==0 and line[j]=="'" and (j==0 or line[j-1]!="\\"):
                        inquotes = 1 # single quotes
                    elif inquotes==1 and line[j]=="'" and line[j-1]!="\\":
                        inquotes = 0 # end single quotes
                    elif inquotes==0 and line[j]=='"' and (j==0 or line[j-1]!="\\"):
                        inquotes = 2 # double quotes
                    elif inquotes==2 and line[j]=='"' and line[j-1]!="\\":
                        inquotes = 0 # end double quotes
                    elif (inquotes==0 and line[j:j+len(impfile)+1]==impfile+"."
                          and (j==0 or re.match(r"\W", line[j-1]))): # i.e. preceding char is not in [a-zA-Z0-9_]
                        line = line[:j] + prefix + line[j:]
                        break
            olist[i] = line
                    
    op = open(prefix+fname+"x", "w")
    for line in olist:
        op.write(line)
    op.close()

##### compile (only happens if required)
def compile(module, switch_verbose, python):
    compname = module + "_compile" + str(os.getpid())

    c = open(compname + ".py", "w")
    c.write("from distutils.extension import Extension\n") # for profiling
    c.write("from distutils.core import setup\n")
    c.write("from Cython.Build import cythonize\n")
    # using np.get_include (and import np) as advised at
    # http://stackoverflow.com/questions/2379898/make-distutils-look-for-numpy-header-files-in-the-correct-place
    c.write("import numpy as np\n")
    c.write("extensions = [Extension('%s', ['%s.pyx'], define_macros=[('CYTHON_TRACE', '1')])]\n"
             % (module, module))
    c.write('setup( include_dirs = [np.get_include()],\n')
    #c.write('       ext_modules = cythonize("%s.pyx")\n' % module) # did this before adding profiling in rev 1.15
    c.write('       ext_modules = cythonize(extensions)\n') # for profiling
    c.write('     )\n')
    c.close()

    #os.system('CFLAGS="" ' + python + ' %s.py build_ext --inplace > %s.log 2>&1' % (compname, compname))
    compcmd =  python + ' %s.py build_ext --inplace > %s.log 2>&1' % (compname, compname)
    status = os.system(compcmd)
    if status:
        sys.stderr.write("cython compiled failed, see %s.log\n" % compname)
        sys.stderr.write("compile command was: %s\n" % compcmd)
        sys.exit(status)
    # tidy up
    if switch_verbose <= 1:
        os.remove(compname + ".py")
        os.remove(compname + ".log")

# recursively find all local modules which are used
# (by local, I mean module.py is in the current dir)
# Input is a  module names (no .py),
# Output is list of module names (no .py)
def find_imports(topmod):
    olist = []
    f = open(topmod+".py")
    for line in f.readlines():
        words = line.split()
        if len(words) and words[0]=="import":
            submod = words[1].split("#")[0] # just a trick to remove anything after "#"
            if os.path.exists(submod+".py"):
                sublist = find_imports(submod)
                sublist.append(submod)
                # don't include duplicates
                for item in sublist:
                    if item not in olist:
                        olist.append(item)
    f.close()
    return olist

def help():
    sys.stdout.write("How to include cython code in your .py file:\n")
    sys.stdout.write("\n")
    sys.stdout.write("First non-white characters '#cy' are directives:\n")
    sys.stdout.write("#cy+ = begin code to add for cython, i.e. remove first '#' on subsequent lines\n")
    sys.stdout.write("#cy- = begin code to remove for cython\n")
    sys.stdout.write("#cy. = end of a #cy+ or #cy- block\n")
    sys.stdout.write("#cy: = insert this single line, i.e. remove '#cy:' for cython\n")
    sys.stdout.write("\n")
    sys.stdout.write("#cy< as first comment: for cython, insert text between '#cy<' and next '#' before first non-white in line\n")
    sys.stdout.write("   (for easy insertion of type declarations in large function calls)\n")
    sys.stdout.write("\n")
    sys.stdout.write("For command line usage (as opposed to this mini how-to), use the -cyu switch\n")
    sys.exit(0)

# Note: prefix switch with -cy should not cause a conflict with actual Python flags
# because python doesn't have a -y switch,
# and python -c switch must be followed by commands
def usage(status):
    sys.stdout.write("Usage:\n")
    sys.stdout.write("   $ python cyrun.py [cyswitches] <command_line>\n")
    sys.stdout.write("cyswitches:\n")
    sys.stdout.write(" --cyx prefix = prefix of generated files. Default is 'cyrun_'\n")
    sys.stdout.write(" --cyp python = Name of python. Default is 'python'\n")
    sys.stdout.write(" --cyq = work quietly. Default is 2 lines of status to stderr\n")
    sys.stdout.write(" --cyv = work verbosely (extra stderr messages)\n")
    sys.stdout.write(" --cyh = display coding help, and exit\n")
    sys.stdout.write(" --cyu = display this message, and exit\n")
    sys.stdout.write(" Then <command_line> is cythonised, i.e. the first python file or module, and any local imported modules, are converted to cython,\n")
    sys.stdout.write(" and the subprocess 'python <cythonised(command_line)>' is launched.\n")
    sys.exit(status)

switch_verbose = 1
prefix = "cyrun_"
python = "python"
i = 1
while i < len(sys.argv):
    arg = sys.argv[i]
    i += 1
    if arg=="--cyq":
        switch_verbose = 0
    elif arg=="--cyv":
        switch_verbose = 2
    elif arg=="--cyx":
        prefix = sys.argv[i]
        i += 1
        if re.match(r"\W", prefix):
            sys.stderr.write("only chars [a-zA-Z0-9_] allowed in prefix %s\n" % prefix)
            usage(1)
    elif arg=="--cyp":
        python = sys.argv[i]
        i += 1
    elif arg=="--cyh":
        help()
    elif arg=="--cyu":
        usage(0)
    else:
        argv = sys.argv[i-1:]
        break
i = 0
cmd = python
topmod = ""
while i < len(argv):
    arg = argv[i]
    i += 1
    if arg=="-m" and topmod=="":
        cmd = cmd + " " + arg
        arg = argv[i]
        i += 1
        topmod = arg
        cmd = cmd + " " + prefix+arg
    elif arg[-3:]==".py":
        if topmod=="":
            topmod = arg.replace(".py", "")
            f = open(topmod+".py", "r")
            for line in f.readlines():
                # for some reason, cython commands can't be in the top level file.
                # So if there are any, create a wrapper file "cyrun_cyrun_<topmod>.pyx"
                # consisting of a single line, an import statement
                if line[:3]=="#cy":
                    wrapper = prefix+prefix+arg+"x"
                    if (os.path.exists(wrapper)
                        and os.path.getmtime(wrapper) > os.path.getmtime(topmod+".py")):
                        pass # no need to remake
                    else:
                        message(switch_verbose, "creating wrapper file " + wrapper + "\n")
                        f2 = open(wrapper, "w")
                        f2.write("########################\n")
                        f2.write("# Automatically created by cyrun.py on %s\n" % time.asctime())
                        f2.write("########################\n")
                        f2.write("import %s%s\n" % (prefix, topmod))
                        f2.close()
                    cmd = cmd + " " + wrapper
                    break
            else:
                cmd = cmd + " " + prefix+arg+"x"
            f.close()
        else:
            sys.stderr.write("Warning: 2nd python file %s will not be cythonised\n" % arg)
            cmd = cmd + " " + arg
    else:
        cmd = cmd + " " + arg

if topmod=="":
    sys.stderr.write("No python file supplied\n")
    usage(1)

#### create .pyx files, if needed
submods = find_imports(topmod)

message(switch_verbose, "Building: ", "Building:\n")
nothing_new = 1
for module in submods + [topmod]:
    if (os.path.exists(prefix+module+".pyx")
        and os.path.getmtime(prefix+module+".pyx") > os.path.getmtime(module+".py")):
        pass # pyx is up to date - do nothing
    else:
        message(switch_verbose, prefix+module+".pyx ")
        build(module+".py", prefix, switch_verbose)
        nothing_new = 0
message(switch_verbose, "\n")

#### compile all local modules used
message(switch_verbose, "Compiling (if needed): ")
for module in submods + [topmod]:
    message(switch_verbose, prefix+"%s.pyx " % module)
    compile(prefix+module, switch_verbose, python)
message(switch_verbose, "(done).\n")

##### run
# subprocess module replaces os.system
message(switch_verbose, "", "# " + cmd + "\n")
subprocess.call(cmd, shell=True)
