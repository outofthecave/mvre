#!/usr/bin/python
# coding: UTF-8
# This program will never be Windows-compatible, since Windows' path separator 
# conflicts with the regex escape character.

import os
import re
import sys
from argparse import *
from posixpathre import *

SHORT_DESCR = "rename large amounts of files using regular expressions."
LONG_DESCR = """\
Automatically resolves backreferences in NEWNAME to groups in the pattern. 
The whole pattern can be referenced as group 0. Two formats of backreferences 
are accepted: `\\1' and `$1'.
Both PATTERN and NEWNAME may be absolute or relative file paths. Make sure to 
escape special characters like `.' in PATTERN to avoid interpretation as 
a regular expression. Escaping is not necessary in NEWNAME except for the 
backslash `\\' and the dollar sign `$'. The escape character is a single 
backslash `\\'."""
parser = ArgumentParser(description=SHORT_DESCR, epilog=LONG_DESCR)
parser.add_argument("-v", "--verbose", action="store_true", dest="verbose",
    default=False, help="be verbose")
parser.add_argument("-y", action="store_true", dest="assume_yes", 
    default=False, help="assume yes as the answer to all prompts")
parser.add_argument("pattern", metavar="PATTERN", type=str,
    help="match the existing filenames against this pattern")
parser.add_argument("new_name", metavar="NEWNAME", type=str,
    help="the new name for the files (backreferences to the pattern are "
    "resolved automatically)")

# matches any backreference, group 1 matches the group number
P_BACKREF = re.compile(r"[\\$]([0-9])")

PROMPT_USAGE = """\
y  yes, move this file
n  no, skip this file
a  move this file and assume 'yes' as the answer to all subsequent prompts
q  quit the program without moving this file
?  show this help message
"""



def askConfirmation(oldpath, newpath):
    """
    show a prompt to the user asking to confirm the deletion of a file."""
    global cl
    # if 'yes' is assumed for all prompts, there is no reason to ask the user
    if cl.assume_yes:
        return True
    else:
        # user may exit whenever they like
        while True:
            # ask the user for confirmation
            answer = raw_input("mv %s %s? [y/n/a/q/?] " % (oldpath, newpath))
            if answer.startswith("y"):
                return True
            elif answer.startswith("n"):
                return False
            elif answer.startswith("a"):
                cl.assume_yes = True
                return True
            elif answer.startswith("q"):
                # quit the whole program
                sys.exit(0)
            # '?' or invalid input
            else:
                print PROMPT_USAGE

def resolveBackrefs(new_name, matched, groups):
    """Replace all backreferences in `new_name' by the corresponding value 
    from groups or by the value of `matched' if the backref number is 0.
    """
    # TODO let enable simple calculations on the backrefs
    # e.g. mvre '(\d)' '${$1+1}' turns '1' into '2'
    backref_matches = re.finditer(P_BACKREF, new_name)
    resolved_name = ""
    prev_end = 0
    for match in backref_matches:
        resolved_name += new_name[prev_end:match.start()]
        backref_number = int(match.groups()[0])
        if backref_number == 0:
            replacement = matched
        elif backref_number-1 < len(groups):
            replacement = groups[backref_number-1]
        else:
            # references to non-existing groups are not expanded
            replacement = match.group()
        resolved_name += replacement
        prev_end = match.end()
    # the part after the last backref
    resolved_name += new_name[prev_end:]
    return resolved_name

def main(raw_cl_args):
    global cl
    cl = parser.parse_args(raw_cl_args)

    pathPattern = PathPattern(cl.pattern)
    matchingPaths = pathPattern.findPaths()
    for pathMatch in matchingPaths:
        old_name = pathMatch.path
        new_name = resolveBackrefs(cl.new_name, pathMatch.path, pathMatch.groups)
        if askConfirmation(old_name, new_name):
            command = "mv -i '%s' '%s'" % (old_name, new_name)
            if cl.verbose:
                print command
            os.system(command)

if __name__ == "__main__":
    main(sys.argv[1:])
