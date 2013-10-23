import os
import posixpath
import re

# TODO cf. /usr/lib/python2.7/posixpath.py

class PathPattern(object):
    """A regex pattern describing a filesystem path. Only compatible with 
    Posix. Can be used with unicode strings.
    Since the dot character is ambiguous, the following rules apply: a 
    single dot or two consecutive dots are not treated as a regular 
    expression iff they occur between slashes. Dots at the beginning or 
    inside a larger name must be escaped.
    `/lib/../boot' and `/lib/\\.\\./boot' match `/boot', not `/lib/xy/boot'
    `/boot/.' and `/boot/\\.' match `/boot', not `/boot/x'
    `/boot/.foo' matches `/boot/.foo', as well as `/boot/xfoo'
    `/boot/\\.foo' matches `/boot/.foo', but not `/boot/xfoo'
    No symbolic links are resolved.
    """
    # TODO add handling of regex flags

    # matches an environment variable in a string
    _varprog = re.compile(r'\$(\w+|\{[^}]*\})')
    
    # matches any symbol that is treated specially in regexps
    P_REGEX_SPECIAL = re.compile(r"[.+*?\[\]\{\}\\^$]+")
    
    # matches any escape sequence
    P_ESCAPE_SPECIAL = re.compile(r"(\n|\r|\t|\\\\)+")

    # type of compiled regexps
    COMP_REGEX_TYPE = type(P_REGEX_SPECIAL)

    def __init__(self, pattern):
        """pattern: string, compiled regex, or PathPattern
        """
        if isinstance(pattern, PathPattern):
            self.p = str(pattern.p)
        elif isinstance(pattern, PathPattern.COMP_REGEX_TYPE):
            self.p = str(pattern.pattern)
        elif isinstance(pattern, str):
            self.p = pattern
        else:
            raise TypeError("pattern must be a string, a compiled regex, or "
                "a PathPattern, not " + type(pattern))

    def __eq__(self, other):
        other = PathPattern(other)
        return self.p == other.p
    
    def __str__(self):
        return str(self.p)
    
    def __repr__(self):
        return repr(self.p)

    def isabs(self):
        """Returns True iff the path patterns starts with the path 
        separator.
        """
        return self.p.startswith('/')

    def abspath(self):
        """Return an absolute self."""
        path = self.p
        if not self.isabs():
            if isinstance(path, unicode):
                cwd = os.getcwdu()
            else:
                cwd = os.getcwd()
            path = posixpath.join(cwd, path)
        return PathPattern(path).normpath()

    def join(self, *others, **kwargs):
        """The same as os.path.join(), but for patterns. Converts instances 
        of other classes to instances of this class.
        keyword arguments:
        inversed: if True, others are prepended to self rather than 
            appended. Defaults to False.
        """
        inversed = kwargs.get("inversed", False)
        if inversed:
            (first, rest) = (others[-1], reversed(others[:-1]) + [self])
        else:
            (first, rest) = (self, others)
        path = PathPattern(first)
        for chunk in rest:
            chunk = PathPattern(chunk)
            if chunk.isabs():
                path = chunk
            elif path == '' or path.endswith('/'):
                path +=  chunk
            else:
                path += '/' + chunk
        return path

    # Expand paths beginning with '~' or '~user'.
    # '~' means $HOME; '~user' means that user's home directory.
    # If the path doesn't begin with '~', or if the user or $HOME is unknown,
    # the path is returned unchanged (leaving error reporting to whatever
    # function is called with the expanded path as argument).
    def expanduser(self):
        """Expand ~ and ~user constructions.  If user or $HOME is unknown,
        do nothing."""
        path = self.p
        if not path.startswith('~'):
            return self
        i = path.find('/', 1)
        if i < 0:
            i = len(path)
        if i == 1:
            if 'HOME' not in os.environ:
                import pwd
                userhome = pwd.getpwuid(os.getuid()).pw_dir
            else:
                userhome = os.environ['HOME']
        else:
            import pwd
            try:
                pwent = pwd.getpwnam(path[1:i])
            except KeyError:
                return self
            userhome = pwent.pw_dir
        userhome = userhome.rstrip('/') or userhome
        return PathPattern(userhome + path[i:])

    def expandvars(self):
        """Expand shell variables of form $var and ${var}.  Unknown variables
        are left unchanged."""
        path = self.p
        if '$' not in path:
            return self
        i = 0
        while True:
            m = PathPattern._varprog.search(path, i)
            if not m:
                break
            i, j = m.span(0)
            name = m.group(1)
            if name.startswith('{') and name.endswith('}'):
                name = name[1:-1]
            if name in os.environ:
                tail = path[j:]
                path = path[:i] + os.environ[name]
                i = len(path)
                path += tail
            else:
                i = j
        return PathPattern(path)

    # Normalize a path, e.g. A//B, A/./B and A/foo/../B all become A/B.
    # It should be understood that this may change the meaning of the path
    # if it contains symbolic links!
    def normpath(self):
        """Normalize path, eliminating double slashes, etc."""
        path = self.p
        # Preserve unicode (if path is unicode)
        slash, dot = (u'/', u'.') if isinstance(path, unicode) else ('/', '.')
        if path == '':
            return PathPattern(dot)
        initial_slashes = int(path.startswith('/'))
        # POSIX allows one or two initial slashes, but treats three or more
        # as single slash.
        if (initial_slashes and
            path.startswith('//') and not path.startswith('///')):
            initial_slashes = 2
        comps = path.split('/')
        new_comps = []
        for comp in comps:
            if comp in ('', '.', r'\.'):
                continue
            if ((comp != '..' and comp != r'\.\.') or 
                (not initial_slashes and not new_comps) or
                (new_comps and (new_comps[-1] == '..' or 
                    new_comps[-1] == r'\.\.'))):
                new_comps.append(comp)
            elif new_comps:
                new_comps.pop()
        comps = new_comps
        path = slash.join(comps)
        if initial_slashes:
            path = slash*initial_slashes + path
        if path:
            return PathPattern(path)
        else:
            return PathPattern(dot)

    def getTokens(self):
        """Return a list of PathPatterns, one for each node in this path.
        """
        tokenStrings = self.p.split('/')
        tokens = []
#        if self.p.startswith("/"):
#            tokens.append(PathPattern("/"))
        for token in tokenStrings:
            if token:
                tokens.append(PathPattern(token))
        return tokens

    def containsRegex(self):
        """Return True iff this PathPattern contains any special regex 
        symbols.
        """
        return re.search(PathPattern.P_REGEX_SPECIAL, self.p) is not None

    def containsEscape(self):
        """Returns True iff this PathPattern contains any escape sequence.
        """
        return re.search(PathPattern.P_ESCAPE_SPECIAL, self.p) is not None

    def isDot(self):
        """Return True iff this PathPattern is a link to the current 
        directory.
        """
        return self.p == r"." or self.p == r"\."

    def isDotDot(self):
        """Return True iff this PathPattern is a link to the parent 
        directory.
        """
        return self.p == r".." or self.p == r"\.\."

    def matches(self, path):
        """Returns true iff this PathPattern's regex matches the entire 
        argument.
        """
        regex = re.compile(self.p)
        matchObj = re.match(regex, path)
        if matchObj is None:
            return False
        else:
            return matchObj.end() == len(path)

    def match(self, path):
        """Returns a PathMatch object iff this PathPattern's regex matches 
        the entire argument, None otherwise.
        """
        regex = re.compile(self.p)
        matchObj = re.match(regex, path)
        if matchObj is not None and matchObj.end() == len(path):
            pathMatch = PathMatch(path, groups=matchObj.groups())
            return pathMatch
        else:
            return None

    def findPaths(self):
        """Return a list of PathMatch objects for all paths on this system 
        that match this PathPattern.
        """
        pattern = self.expanduser().expandvars().normpath()
        tokenIter = iter(pattern.getTokens())
#        print pattern.getTokens()
        try:
            token = next(tokenIter)
        except StopIteration as error:
            if pattern == "/":
                # only the FS root matches '/'
                return ["/"]
            elif not pattern:
                # the empty pattern matches the CWD
                return ["."]
            else:
                raise error
        numMatchesCur = 1
        numMatchesNext = 0
        if pattern.isabs():
            pathQ = [PathMatch("/")]
        else:
            pathQ = [PathMatch(".")]
        # ALTERNATIVE:
        # for token in tokens:
        #   while pathQ:
        #     process and put matches on separate list
        #   load paths from separate list
        while pathQ:
            if numMatchesCur < 1:
                try:
                    token = next(tokenIter)
                except StopIteration:
#                    print "except StopIteration: break"
                    break
                numMatchesCur = numMatchesNext
                numMatchesNext = 0
#            print "token =", repr(token)
#            print "pathQ =", pathQ
            curPath = pathQ.pop(0)
            numMatchesCur -= 1
            # follow references to the parent dir
            if token.isDotDot():
                newPath = posixpath.join(curPath.path, "..")
                newPath = posixpath.normpath(newPath)
                pathQ.append(PathMatch(newPath))
                numMatchesNext += 1
            # follow all matching directories down the FS tree
            else:
                try:
                    ls = os.listdir(curPath.path)
                except OSError as err:
#                    print err
                    continue
#                print "ls", curPath
                for item in sorted(ls):
                    pathMatch = token.match(item)
                    if pathMatch:
                        newPath = posixpath.join(curPath.path, item)
                        newPath = posixpath.normpath(newPath)
                        newGroups = curPath.groups + pathMatch.groups
                        newPathMatch = PathMatch(newPath, groups=newGroups)
                        pathQ.append(newPathMatch)
                        numMatchesNext += 1
        return pathQ



class PathMatch(object):
    """similar to an SRE_Match object, a PathMatch is the result of 
    matching a regular expression against a path.
    """
    
    def __init__(self, path, groups=()):
        """path: a matching Posix path.
        groups: a tuple containing the substrings matching the groups.
        """
        self.path = path
        self.groups = groups
    
    def __str__(self):
        return str(self.path)



if __name__ == "__main__":
    """
    `/lib/../boot' and `/lib/\\.\\./boot' match `/boot', not `/lib/xy/boot'
    `/boot/.' and `/boot/\\.' match `/boot', not `/boot/x'
    `/boot/.foo' matches `/boot/.foo', as well as `/boot/xfoo'
    `/boot/\\.foo' matches `/boot/.foo', but not `/boot/xfoo'
    """
    import sys
    p = PathPattern(sys.argv[1])
    for pathMatch in p.findPaths():
        print pathMatch, pathMatch.groups


