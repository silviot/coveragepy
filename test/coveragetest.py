"""Base test case class for coverage testing."""

import imp, os, random, re, shutil, sys, tempfile, textwrap, unittest

import coverage
from coverage.backward import set, sorted, StringIO # pylint: disable-msg=W0622
from backtest import run_command


class Tee(object):
    """A file-like that writes to all the file-likes it has."""

    def __init__(self, *files):
        """Make a Tee that writes to all the files in `files.`"""
        self.files = files
        
    def write(self, data):
        """Write `data` to all the files."""
        for f in self.files:
            f.write(data)


class CoverageTest(unittest.TestCase):
    """A base class for Coverage test cases."""

    def __init__(self, *args, **kwargs):
        super(CoverageTest, self).__init__(*args, **kwargs)
        self.run_in_temp_dir = True

    def setUp(self):
        if self.run_in_temp_dir:
            # Create a temporary directory.
            self.noise = str(random.random())[2:]
            self.temp_root = os.path.join(tempfile.gettempdir(), 'test_coverage')
            self.temp_dir = os.path.join(self.temp_root, self.noise)
            os.makedirs(self.temp_dir)
            self.old_dir = os.getcwd()
            os.chdir(self.temp_dir)
    
            # Preserve changes to PYTHONPATH.
            self.old_pypath = os.environ.get('PYTHONPATH', '')
    
            # Modules should be importable from this temp directory.
            self.old_syspath = sys.path[:]
            sys.path.insert(0, '')
    
            # Keep a counter to make every call to check_coverage unique.
            self.n = 0

        # Use a Tee to capture stdout.
        self.old_stdout = sys.stdout
        self.captured_stdout = StringIO()
        sys.stdout = Tee(sys.stdout, self.captured_stdout)
        
    def tearDown(self):
        if self.run_in_temp_dir:
            # Restore the original sys.path and PYTHONPATH
            sys.path = self.old_syspath
            os.environ['PYTHONPATH'] = self.old_pypath

            # Get rid of the temporary directory.
            os.chdir(self.old_dir)
            shutil.rmtree(self.temp_root)
        
        # Restore stdout.
        sys.stdout = self.old_stdout

    def stdout(self):
        """Return the data written to stdout during the test."""
        return self.captured_stdout.getvalue()

    def make_file(self, filename, text):
        """Create a temp file.
        
        `filename` is the file name, and `text` is the content.
        
        """
        assert self.run_in_temp_dir
        text = textwrap.dedent(text)
        
        # Create the file.
        f = open(filename, 'w')
        f.write(text)
        f.close()

    def import_module(self, modname):
        """Import the module named modname, and return the module object."""
        modfile = modname + '.py'
        f = open(modfile, 'r')
        
        for suff in imp.get_suffixes():
            if suff[0] == '.py':
                break
        try:
            # pylint: disable-msg=W0631
            # (Using possibly undefined loop variable 'suff')
            mod = imp.load_module(modname, f, modfile, suff)
        finally:
            f.close()
        return mod

    def get_module_name(self):
        """Return the module name to use for this test run."""
        # We append self.n because otherwise two calls in one test will use the
        # same filename and whether the test works or not depends on the
        # timestamps in the .pyc file, so it becomes random whether the second
        # call will use the compiled version of the first call's code or not!
        modname = 'coverage_test_' + self.noise + str(self.n)
        self.n += 1
        return modname
    
    # Map chars to numbers for arcz_to_arcs
    _arcz_map = {'.': -1}
    _arcz_map.update(dict([(c, ord(c)-ord('0')) for c in '123456789']))
    _arcz_map.update(dict(
        [(c, 10+ord(c)-ord('A')) for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
        ))
    
    def arcz_to_arcs(self, arcz):
        """Convert a compact textual representation of arcs to a list of pairs.
        
        The text has space-separated pairs of letters.  Period is -1, 1-9 are
        1-9, A-Z are 10 through 36.  The resulting list is sorted regardless of
        the order of the input pairs.
        
        ".1 12 2." --> [(-1,1), (1,2), (2,-1)]
        
        """
        arcs = []
        for a,b in arcz.split():
            arcs.append((self._arcz_map[a], self._arcz_map[b]))
        return sorted(arcs)

    def check_coverage(self, text, lines=None, missing="", excludes=None,
            report="", arcz=None, arcz_missing="", arcz_unpredicted=""):
        """Check the coverage measurement of `text`.
        
        The source `text` is run and measured.  `lines` are the line numbers
        that are executable, `missing` are the lines not executed, `excludes`
        are regexes to match against for excluding lines, and `report` is
        the text of the measurement report.
        
        For arc measurement, `arcz` is a string that can be decoded into arcs
        in the code (see `arcz_to_arcs` for the encoding scheme),
        `arcz_missing` are the arcs that are not executed, and
        `arcs_unpredicted` are the arcs executed in the code, but not deducible
        from the code.
        
        """
        # We write the code into a file so that we can import it.
        # Coverage wants to deal with things as modules with file names.
        modname = self.get_module_name()
        
        self.make_file(modname+".py", text)

        arcs = arcs_missing = arcs_unpredicted = None
        if arcz is not None:
            arcs = self.arcz_to_arcs(arcz)
            arcs_missing = self.arcz_to_arcs(arcz_missing or "")
            arcs_unpredicted = self.arcz_to_arcs(arcz_unpredicted or "")
            
        # Start up Coverage.
        cov = coverage.coverage(branch=(arcs_missing is not None))
        cov.erase()
        for exc in excludes or []:
            cov.exclude(exc)
        cov.start()

        # Import the python file, executing it.
        mod = self.import_module(modname)
        
        # Stop Coverage.
        cov.stop()

        # Clean up our side effects
        del sys.modules[modname]

        # Get the analysis results, and check that they are right.
        analysis = cov._analyze(mod)
        if lines is not None:
            if type(lines[0]) == type(1):
                self.assertEqual(analysis.statements, lines)
            else:
                for line_list in lines:
                    if analysis.statements == line_list:
                        break
                else:
                    self.fail("None of the lines choices matched %r" %
                                                        analysis.statements
                        )

            if missing is not None:
                if type(missing) == type(""):
                    self.assertEqual(analysis.missing_formatted(), missing)
                else:
                    for missing_list in missing:
                        if analysis.missing == missing_list:
                            break
                    else:
                        self.fail("None of the missing choices matched %r" %
                                                analysis.missing_formatted()
                            )

        if arcs is not None:
            self.assertEqual(analysis.arc_possibilities(), arcs)

            if arcs_missing is not None:
                self.assertEqual(analysis.arcs_missing(), arcs_missing)

            if arcs_unpredicted is not None:
                self.assertEqual(analysis.arcs_unpredicted(), arcs_unpredicted)

        if report:
            frep = StringIO()
            cov.report(mod, file=frep)
            rep = " ".join(frep.getvalue().split("\n")[2].split()[1:])
            self.assertEqual(report, rep)

    def assert_raises_msg(self, excClass, msg, callableObj, *args, **kwargs):
        """ Just like unittest.TestCase.assertRaises,
            but checks that the message is right too.
        """
        try:
            callableObj(*args, **kwargs)
        except excClass:
            _, exc, _ = sys.exc_info()
            excMsg = str(exc)
            if not msg:
                # No message provided: it passes.
                return  #pragma: no cover
            elif excMsg == msg:
                # Message provided, and we got the right message: it passes.
                return
            else:   #pragma: no cover
                # Message provided, and it didn't match: fail!
                raise self.failureException(
                    "Right exception, wrong message: got '%s' expected '%s'" %
                    (excMsg, msg)
                    )
        # No need to catch other exceptions: They'll fail the test all by
        # themselves!
        else:   #pragma: no cover
            if hasattr(excClass,'__name__'):
                excName = excClass.__name__
            else:
                excName = str(excClass)
            raise self.failureException(
                "Expected to raise %s, didn't get an exception at all" %
                excName
                )

    def nice_file(self, *fparts):
        """Canonicalize the filename composed of the parts in `fparts`."""
        fname = os.path.join(*fparts)
        return os.path.normcase(os.path.abspath(os.path.realpath(fname)))
    
    def run_command(self, cmd):
        """ Run the command-line `cmd`, print its output.
        """
        # Add our test modules directory to PYTHONPATH.  I'm sure there's too
        # much path munging here, but...
        here = os.path.dirname(self.nice_file(coverage.__file__, ".."))
        testmods = self.nice_file(here, 'test/modules')
        zipfile = self.nice_file(here, 'test/zipmods.zip')
        pypath = self.old_pypath
        if pypath:
            pypath += os.pathsep
        pypath += testmods + os.pathsep + zipfile
        os.environ['PYTHONPATH'] = pypath
        
        _, output = run_command(cmd)
        print(output)
        return output

    def assert_equal_sets(self, s1, s2):
        """Assert that the two arguments are equal as sets."""
        self.assertEqual(set(s1), set(s2))

    def assert_matches(self, s, regex):
        """Assert that `s` matches `regex`."""
        m = re.search(regex, s)
        if not m:
            raise self.failureException("%r doesn't match %r" % (s, regex))
