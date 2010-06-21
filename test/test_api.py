"""Tests for Coverage's api."""

import os, re, sys, textwrap

import coverage
from coverage.backward import StringIO

sys.path.insert(0, os.path.split(__file__)[0]) # Force relative import for Py3k
from coveragetest import CoverageTest


class SingletonApiTest(CoverageTest):
    """Tests of the old-fashioned singleton API."""

    def setUp(self):
        super(SingletonApiTest, self).setUp()
        # These tests use the singleton module interface.  Prevent it from
        # writing .coverage files at exit.
        coverage.use_cache(0)

    def do_report_work(self, modname):
        """Create a module named `modname`, then measure it."""
        coverage.erase()

        self.make_file(modname+".py", """\
            a = 1
            b = 2
            if b == 3:
                c = 4
                d = 5
                e = 6
            f = 7
            """)

        # Import the python file, executing it.
        coverage.start()
        self.import_local_file(modname)         # pragma: recursive coverage
        coverage.stop()                         # pragma: recursive coverage

    def test_simple(self):
        coverage.erase()

        self.make_file("mycode.py", """\
            a = 1
            b = 2
            if b == 3:
                c = 4
            d = 5
            """)

        # Import the python file, executing it.
        coverage.start()
        self.import_local_file("mycode")        # pragma: recursive coverage
        coverage.stop()                         # pragma: recursive coverage

        _, statements, missing, missingtext = coverage.analysis("mycode.py")
        self.assertEqual(statements, [1,2,3,4,5])
        self.assertEqual(missing, [4])
        self.assertEqual(missingtext, "4")

    def test_report(self):
        self.do_report_work("mycode2")
        coverage.report(["mycode2.py"])
        self.assertEqual(self.stdout(), textwrap.dedent("""\
            Name      Stmts   Miss  Cover   Missing
            ---------------------------------------
            mycode2       7      3    57%   4-6
            """))

    def test_report_file(self):
        # The file= argument of coverage.report makes the report go there.
        self.do_report_work("mycode3")
        fout = StringIO()
        coverage.report(["mycode3.py"], file=fout)
        self.assertEqual(self.stdout(), "")
        self.assertEqual(fout.getvalue(), textwrap.dedent("""\
            Name      Stmts   Miss  Cover   Missing
            ---------------------------------------
            mycode3       7      3    57%   4-6
            """))

    def test_report_default(self):
        # Calling report() with no morfs will report on whatever was executed.
        self.do_report_work("mycode4")
        coverage.report()
        rpt = re.sub(r"\s+", " ", self.stdout())
        self.assertTrue("mycode4 7 3 57% 4-6" in rpt)


class ApiTest(CoverageTest):
    """Api-oriented tests for Coverage."""

    def test_unexecuted_file(self):
        cov = coverage.coverage()

        self.make_file("mycode.py", """\
            a = 1
            b = 2
            if b == 3:
                c = 4
            d = 5
            """)

        self.make_file("not_run.py", """\
            fooey = 17
            """)

        # Import the python file, executing it.
        cov.start()
        self.import_local_file("mycode")        # pragma: recursive coverage
        cov.stop()                              # pragma: recursive coverage

        _, statements, missing, _ = cov.analysis("not_run.py")
        self.assertEqual(statements, [1])
        self.assertEqual(missing, [1])

    def test_filenames(self):

        self.make_file("mymain.py", """\
            import mymod
            a = 1
            """)

        self.make_file("mymod.py", """\
            fooey = 17
            """)

        # Import the python file, executing it.
        cov = coverage.coverage()
        cov.start()
        self.import_local_file("mymain")        # pragma: recursive coverage
        cov.stop()                              # pragma: recursive coverage

        filename, _, _, _ = cov.analysis("mymain.py")
        self.assertEqual(os.path.basename(filename), "mymain.py")
        filename, _, _, _ = cov.analysis("mymod.py")
        self.assertEqual(os.path.basename(filename), "mymod.py")

        filename, _, _, _ = cov.analysis(sys.modules["mymain"])
        self.assertEqual(os.path.basename(filename), "mymain.py")
        filename, _, _, _ = cov.analysis(sys.modules["mymod"])
        self.assertEqual(os.path.basename(filename), "mymod.py")

        # Import the python file, executing it again, once it's been compiled
        # already.
        cov = coverage.coverage()
        cov.start()
        self.import_local_file("mymain")        # pragma: recursive coverage
        cov.stop()                              # pragma: recursive coverage

        filename, _, _, _ = cov.analysis("mymain.py")
        self.assertEqual(os.path.basename(filename), "mymain.py")
        filename, _, _, _ = cov.analysis("mymod.py")
        self.assertEqual(os.path.basename(filename), "mymod.py")

        filename, _, _, _ = cov.analysis(sys.modules["mymain"])
        self.assertEqual(os.path.basename(filename), "mymain.py")
        filename, _, _, _ = cov.analysis(sys.modules["mymod"])
        self.assertEqual(os.path.basename(filename), "mymod.py")

    def test_ignore_stdlib(self):
        self.make_file("mymain.py", """\
            import mymod, colorsys
            a = 1
            hls = colorsys.rgb_to_hls(1.0, 0.5, 0.0)
            """)

        self.make_file("mymod.py", """\
            fooey = 17
            """)

        # Measure without the stdlib.
        cov1 = coverage.coverage()
        self.assertEqual(cov1.config.cover_pylib, False)
        cov1.start()
        self.import_local_file("mymain")        # pragma: recursive coverage
        cov1.stop()                             # pragma: recursive coverage

        # some statements were marked executed in mymain.py
        _, statements, missing, _ = cov1.analysis("mymain.py")
        self.assertNotEqual(statements, missing)
        # but none were in colorsys.py
        _, statements, missing, _ = cov1.analysis("colorsys.py")
        self.assertEqual(statements, missing)

        # Measure with the stdlib.
        cov2 = coverage.coverage(cover_pylib=True)
        cov2.start()
        self.import_local_file("mymain")        # pragma: recursive coverage
        cov2.stop()                             # pragma: recursive coverage

        # some statements were marked executed in mymain.py
        _, statements, missing, _ = cov2.analysis("mymain.py")
        self.assertNotEqual(statements, missing)
        # and some were marked executed in colorsys.py
        _, statements, missing, _ = cov2.analysis("colorsys.py")
        self.assertNotEqual(statements, missing)

    def test_exclude_list(self):
        cov = coverage.coverage()
        cov.clear_exclude()
        self.assertEqual(cov.get_exclude_list(), [])
        cov.exclude("foo")
        self.assertEqual(cov.get_exclude_list(), ["foo"])
        cov.exclude("bar")
        self.assertEqual(cov.get_exclude_list(), ["foo", "bar"])
        self.assertEqual(cov.exclude_re, "(foo)|(bar)")
        cov.clear_exclude()
        self.assertEqual(cov.get_exclude_list(), [])

    def test_datafile_default(self):
        # Default data file behavior: it's .coverage
        self.make_file("datatest1.py", """\
            fooey = 17
            """)

        self.assertSameElements(os.listdir("."), ["datatest1.py"])
        cov = coverage.coverage()
        cov.start()
        self.import_local_file("datatest1")     # pragma: recursive coverage
        cov.stop()                              # pragma: recursive coverage
        cov.save()
        self.assertSameElements(os.listdir("."),
                            ["datatest1.py", "datatest1.pyc", ".coverage"])

    def test_datafile_specified(self):
        # You can specify the data file name.
        self.make_file("datatest2.py", """\
            fooey = 17
            """)

        self.assertSameElements(os.listdir("."), ["datatest2.py"])
        cov = coverage.coverage(data_file="cov.data")
        cov.start()
        self.import_local_file("datatest2")     # pragma: recursive coverage
        cov.stop()                              # pragma: recursive coverage
        cov.save()
        self.assertSameElements(os.listdir("."),
                            ["datatest2.py", "datatest2.pyc", "cov.data"])

    def test_datafile_and_suffix_specified(self):
        # You can specify the data file name and suffix.
        self.make_file("datatest3.py", """\
            fooey = 17
            """)

        self.assertSameElements(os.listdir("."), ["datatest3.py"])
        cov = coverage.coverage(data_file="cov.data", data_suffix="14")
        cov.start()
        self.import_local_file("datatest3")     # pragma: recursive coverage
        cov.stop()                              # pragma: recursive coverage
        cov.save()
        self.assertSameElements(os.listdir("."),
                            ["datatest3.py", "datatest3.pyc", "cov.data.14"])

    def test_datafile_from_rcfile(self):
        # You can specify the data file name in the .coveragerc file
        self.make_file("datatest4.py", """\
            fooey = 17
            """)
        self.make_file(".coveragerc", """\
            [run]
            data_file = mydata.dat
            """)

        self.assertSameElements(os.listdir("."),
                                            ["datatest4.py", ".coveragerc"])
        cov = coverage.coverage()
        cov.start()
        self.import_local_file("datatest4")     # pragma: recursive coverage
        cov.stop()                              # pragma: recursive coverage
        cov.save()
        self.assertSameElements(os.listdir("."),
                ["datatest4.py", "datatest4.pyc", ".coveragerc", "mydata.dat"])

    def test_empty_reporting(self):
        # Used to be you'd get an exception reporting on nothing...
        cov = coverage.coverage()
        cov.erase()
        cov.report()


class OmitIncludeTest(CoverageTest):
    """Test using `omit` and `include` when measuring code."""

    def test_nothing_specified(self):
        self.make_file("a.py", """\
            a = 1
            """)
        self.make_file("b.py", """\
            import a
            b = 1
            """)

        cov = coverage.coverage()
        cov.start()
        self.import_local_file("b")
        cov.stop()
        lines = cov.data.summary()
        self.assertEqual(lines['a.py'], 1)
        self.assertEqual(lines['b.py'], 2)

    def test_include(self):
        self.make_file("a.py", """\
            a = 1
            """)
        self.make_file("b.py", """\
            import a
            b = 1
            """)

        cov = coverage.coverage(include=["a.py"])
        cov.start()
        self.import_local_file("b")
        cov.stop()
        lines = cov.data.summary()
        self.assertEqual(lines['a.py'], 1)
        self.assert_('b.py' not in lines)

    def test_omit(self):
        self.make_file("a.py", """\
            a = 1
            """)
        self.make_file("b.py", """\
            import a
            b = 1
            """)

        cov = coverage.coverage(omit=["a*"])
        cov.start()
        self.import_local_file("b")
        cov.stop()
        lines = cov.data.summary()
        self.assert_('a.py' not in lines)
        self.assertEqual(lines['b.py'], 2)

    def test_omit_and_include(self):
        self.make_file("aa.py", """\
            a = 1
            """)
        self.make_file("ab.py", """\
            import aa
            b = 1
            """)

        cov = coverage.coverage(include=["a*"], omit=["aa.py"])
        cov.start()
        self.import_local_file("ab")
        cov.stop()
        lines = cov.data.summary()
        self.assert_('aa.py' not in lines)
        self.assertEqual(lines['ab.py'], 2)
