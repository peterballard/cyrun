# Copyright Peter Ballard, 2018
# Free to reuse and modify GPL
# Based on https://github.com/cython/cython/blob/master/tests/run/line_profile_test.srctree version downloaded Tue Aug 07 11:50:05 ACST 2018
# Adapted by Peter Ballard to work with cyrun.py,
# so it needs a compatible version of cyrun.py, i.e. internal version 1.15 or greater.

"""
Usage - see usage() below

This also works on a Python file, which doesn't seem to need any of these.

The cython file needs:

1. the following line at the top:

# cython: linetrace=True

2. an "import cython" statement.

3. The following line immediately before the function to be profiled:

@cython.binding(True)

4. Due to a bug/feature in the profiling code, the function to be profiled
should not be the last function in the cython file.
It can help to put a dummy function at the end of the cython file.
"""

import sys

# This 3rd party module may need to be downloaded
# on Mac OS I did this with "pip install line_profiler" at the bash shell
import line_profiler

def usage():
    sys.stdout.write("Usage\n")
    sys.stdout.write(" $ python cyprofiler.py <cyfile> <function_to_profile> '<function_call>'\n")
    sys.stdout.write("   <cyfile> is the name of the python or cython file. Suffix is optional.\n")
    sys.stdout.write("   <function_to_profile> and the function in <function_call> need not be the same function, but both  must both be in cyfile\n")
    sys.stdout.write("   <function_call> should take the form <function>() or <function>(<args>), and it's almost always a good idea to put single quotes around it\n")
    sys.exit(1)

if len(sys.argv) < 3:
    usage()
cyfile = sys.argv[1].replace(".pyx", "").replace(".py", "")
module_to_profile = sys.argv[2]
module_call = sys.argv[3]

# I'm sure the code below could be done more efficiently using the "imp" module,
# but since this is just for profiling, it probably doesn't matter.

exec("import " + cyfile)
full_module_to_profile = cyfile + "." + module_to_profile
sys.stdout.write("profiled module: %s\n" % full_module_to_profile)
exec("func = %s" % full_module_to_profile)
profile = line_profiler.LineProfiler(func)

# module_call looks something like "bailey.bailey_fs(1000, 1.0)"
b1 = module_call.find("(")
if b1 < 0:
    sys.stdout.write("last argument must be a function call\n")
    usage()
else:
    module_to_run = module_call[:b1]
    argstring = module_call[b1:]
    if argstring[-1] != ")":
        sys.stdout.write("last argument is a function call so must end with a right parenthesis\n")
        usage()
    elif argstring=="()":
        cmd = "profile.runcall(%s.%s)" % (cyfile, module_to_run)
    else:
        cmd = "profile.runcall(%s.%s, %s)" % (cyfile, module_to_run, argstring[1:-1])
sys.stdout.write("profiler call:   %s\n" % cmd)
exec(cmd)

profile.print_stats()
