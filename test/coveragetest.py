"""Base test case class for coverage testing."""

import imp, os, random, sys, tempfile, textwrap, unittest
from cStringIO import StringIO

import path     # from http://www.jorendorff.com/articles/python/path/

import coverage


class CoverageTest(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory.
        self.noise = str(random.random())[2:]
        self.temproot = path.path(tempfile.gettempdir()) / 'test_coverage' 
        self.tempdir = self.temproot / self.noise
        self.tempdir.makedirs()
        self.olddir = os.getcwd()
        os.chdir(self.tempdir)

        # Modules should be importable from this temp directory.
        self.oldsyspath = sys.path[:]
        sys.path.insert(0, '')

        # Keep a counter to make every call to checkCoverage unique.
        self.n = 0
        
    def tearDown(self):
        sys.path = self.oldsyspath
        # Get rid of the temporary directory.
        os.chdir(self.olddir)
        self.temproot.rmtree()

    def makeFile(self, modname, text):
        """ Create a temp file with modname as the module name, and text as the
            contents.
        """
        text = textwrap.dedent(text)
        
        # Create the python file.
        f = open(modname + '.py', 'w')
        f.write(text)
        f.close()

    def importModule(self, modname):
        """ Import the module named modname, and return the module object.
        """
        modfile = modname + '.py'
        f = open(modfile, 'r')
        
        for suff in imp.get_suffixes():
            if suff[0] == '.py':
                break
        try:
            mod = imp.load_module(modname, f, modfile, suff)
        finally:
            f.close()
        return mod

    def getModuleName(self):
        # We append self.n because otherwise two calls in one test will use the
        # same filename and whether the test works or not depends on the
        # timestamps in the .pyc file, so it becomes random whether the second
        # call will use the compiled version of the first call's code or not!
        modname = 'coverage_test_' + self.noise + str(self.n)
        self.n += 1
        return modname
    
    def checkCoverage(self, text, lines, missing="", excludes=[], report=""):
        # We write the code into a file so that we can import it.
        # coverage.py wants to deal with things as modules with file names.
        modname = self.getModuleName()
        
        self.makeFile(modname, text)

        # Start up coverage.py
        coverage.erase()
        for exc in excludes:
            coverage.exclude(exc)
        coverage.start()

        # Import the python file, executing it.
        mod = self.importModule(modname)
        
        # Stop coverage.py
        coverage.stop()

        # Clean up our side effects
        del sys.modules[modname]

        # Get the analysis results, and check that they are right.
        _, clines, _, cmissing = coverage.analysis(mod)
        if lines is not None:
            if type(lines[0]) == type(1):
                self.assertEqual(clines, lines)
            else:
                for line_list in lines:
                    if clines == line_list:
                        break
                else:
                    self.fail("None of the lines choices matched %r" % clines)
        if missing is not None:
            if type(missing) == type(""):
                self.assertEqual(cmissing, missing)
            else:
                for missing_list in missing:
                    if cmissing == missing_list:
                        break
                else:
                    self.fail("None of the missing choices matched %r" % cmissing)

        if report:
            frep = StringIO()
            coverage.report(mod, file=frep)
            rep = " ".join(frep.getvalue().split("\n")[2].split()[1:])
            self.assertEqual(report, rep)

    def assertRaisesMsg(self, excClass, msg, callableObj, *args, **kwargs):
        """ Just like unittest.TestCase.assertRaises,
            but checks that the message is right too.
        """
        try:
            callableObj(*args, **kwargs)
        except excClass, exc:
            excMsg = str(exc)
            if not msg:
                # No message provided: it passes.
                return  #pragma: no cover
            elif excMsg == msg:
                # Message provided, and we got the right message: it passes.
                return
            else:   #pragma: no cover
                # Message provided, and it didn't match: fail!
                raise self.failureException("Right exception, wrong message: got '%s' expected '%s'" % (excMsg, msg))
        # No need to catch other exceptions: They'll fail the test all by themselves!
        else:   #pragma: no cover
            if hasattr(excClass,'__name__'):
                excName = excClass.__name__
            else:
                excName = str(excClass)
            raise self.failureException("Expected to raise %s, didn't get an exception at all" % excName)

    def nice_file(self, *fparts):
        return os.path.normcase(os.path.abspath(os.path.realpath(os.path.join(*fparts))))
    
    def run_command(self, cmd):
        """ Run the command-line `cmd`, print its output.
        """
        # Add our test modules directory to PYTHONPATH.  I'm sure there's too
        # much path munging here, but...
        here = os.path.dirname(self.nice_file(coverage.__file__, ".."))
        testmods = self.nice_file(here, 'test/modules')
        zipfile = self.nice_file(here, 'test/zipmods.zip')
        pypath = os.environ['PYTHONPATH']
        if pypath:
            pypath += os.pathsep
        pypath += testmods + os.pathsep + zipfile
        os.environ['PYTHONPATH'] = pypath
        
        stdin, stdouterr = os.popen4(cmd)
        output = stdouterr.read()
        print output
        return output
