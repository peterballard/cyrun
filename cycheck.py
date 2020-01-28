# cycheck.py
# Check for undeclared cython variables by running
#   python cycheck.py <cython_file.pyx>

import sys

#######################################
# Code from strip_comments.py
# Modified by P. Ballard 13-Feb-2017
# Inserted into cycheck.py 16-Feb-2018

'''
Comment Remover
Licensed under MIT
Copyright (c) 2011 Isaac Muse <isaacmuse@gmail.com>
https://gist.github.com/facelessuser/5750103

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''
#import sys
import re

LINE_PRESERVE = re.compile(r"\r?\n", re.MULTILINE)

PY_PATTERN = re.compile(
    r"""
          (?P<comments>
              \s*\#(?:[^\r\n])*                 # single line comments
          )
        | (?P<code>
                "{3}(?:\\.|[^\\])*"{3}          # triple double quotes
              | '{3}(?:\\.|[^\\])*'{3}          # triple single quotes
              | "(?:\\.|[^"\\])*"               # double quotes
              | '(?:\\.|[^'])*'                 # single quotes
              | .[^\#"']*                       # everything else
          )
    """,
    re.VERBOSE | re.MULTILINE | re.DOTALL
)

# "(?:\\.|[^"\\])*"               # purely to fix emacs coloring

def _strip_regex(pattern, text, preserve_lines):
    def remove_comments(group, preserve_lines=False):
        return ''.join([x[0] for x in LINE_PRESERVE.findall(group)]) if preserve_lines else ''

    def evaluate(m, preserve_lines):
        g = m.groupdict()
        return g["code"] if g["code"] is not None else remove_comments(g["comments"], preserve_lines)

    return ''.join(map(lambda m: evaluate(m, preserve_lines), pattern.finditer(text)))


# modified (removed OO, rename) by PGB
def stripstring(text, preserve_lines=False):
    return _strip_regex(
        PY_PATTERN,
        text,
        preserve_lines
    )

# added by P. Ballard
def stripfile(fname):
    #fname = sys.argv[1]
    ip = open(fname, "r")
    s = ip.read()
    ip.close()
    s2 = stripstring(s)
    return s2

# end of strip_comments.py
################################

TYPES = ("double", "int", "long")

def function_start(words):
    if (len(words)>=2
        and ( (words[0]=="cpdef")
              or (words[0]=="cdef" and words[1] not in TYPES and not words[1].count(".ndarray")))):
        return True
    else:
        return False

def extract_functions(lines):
    list_of_lists = []
    list = []
    for line in lines:
        words = line.split()
        if function_start(words):
            if len(list):
                list_of_lists.append(tuple(list))
            list = [line]
        elif len(list):
            list.append(line)
        else:
            # don't append if list hasn't already begun
            pass
    if len(list):
        list_of_lists.append(tuple(list))
    return list_of_lists

def check_function(lines):
    #sys.stdout.write("checking function of %d lines\n" % (len(lines)))
    defined = []
    used = []
    doing_func = 0
    funcname = ""
    for line in lines:
        words = line.split()
        if function_start(words):
            doing_func = 1
            newfuncname = words[1].split("(")[0]
            if funcname != "":
                raise Exception, "Second function in check_function: %s and %s\n" % (funcname, newfuncname)
            funcname = newfuncname
        if doing_func:
            for i in range(len(words)):
                if i < len(words)-1 and words[i] in TYPES:
                    # strip comma, parethesis, colon
                    # and everything after equals
                    varname = words[i+1].replace(",","").replace(")","").replace(":","").split("=")[0]
                    if varname in defined:
                        sys.stdout.write("Warning func var %s already defined: %s\n" % (varname, line.rstrip()))
                    else:
                        # function inputs are both defined and 'used'
                        defined.append(varname)
                        used.append(varname)
            if len(words) and words[-1][-1]==":":
                doing_func = 0
                continue
        else:
            if len(words)>=3 and words[0]=="cdef" and (words[1] in TYPES or words[1].count(".ndarray")):
                for word in words[2:]:
                    for ch in ["=", "(", ")", "[", "]"]:
                        if word.count(ch):
                            # this word is part of an array def or something like that, so not a varname
                            break
                    else:
                        varname = word.replace(",", "")
                        if varname in defined:
                            sys.stdout.write("Warning cdef var %s already defined: %s\n" % (varname, line.rstrip()))
                        else:
                            defined.append(varname)
            elif len(words)>=2 and (words[0]=="for" or words[1]=="="):
                # tuple assigments with spaces are ignored, really should handle them
                if words[0]=="for":
                    word = words[1]
                else:
                    word = words[0]
                if word[0]=="(" and word[-1]==")" or word[0]=="[" and word[-1]=="]":
                    vars = word[1:-1].split(",")
                else:
                    vars = word.split(",")
                for fullvarname in vars:
                    varname = fullvarname.split("[")[0] # in case it's an array/dict index
                    if varname not in used:
                        # used more than once is ok, of course
                        used.append(varname)
    defined.sort()
    used.sort()
    if len(defined)==0:
        sys.stdout.write("Warning, nothing defined in %s\n" % funcname)
    #sys.stdout.write("defined but not used:")
    #for varname in defined:
    #    if varname not in used:
    #        sys.stdout.write(" " + varname)
    #sys.stdout.write("\n")
    undefined = []
    for varname in used:
        if varname not in defined:
            undefined.append(varname)
    sys.stdout.write("%s (%d defined, %d used), %d used but not defined:"
                     % (funcname, len(defined), len(used), len(undefined)))
    for varname in undefined:
        sys.stdout.write(" " + varname)
    sys.stdout.write("\n")
    verbose = 1
    if verbose:
        sys.stdout.write("defined = %s\n" % defined)
        sys.stdout.write("used = %s\n" % used)
        sys.stdout.write("\n")
    

filename = sys.argv[1]
if filename[-4:]!=".pyx":
    sys.stdout.write("Warning: cycheck runs on cython file, which usually ends in .pyx\n")
s = stripfile(filename)
lines = s.splitlines()
#sys.stdout.write("len(lines) = %d\n" % len(lines))
list_of_lists = extract_functions(lines)
#sys.stdout.write("len(list_of_lists) = %d\n" % len(list_of_lists))
for list in list_of_lists:
    check_function(list)
    
