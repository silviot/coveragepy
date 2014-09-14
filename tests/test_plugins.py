"""Tests for plugins."""

import os.path

import coverage
from coverage.codeunit import CodeUnit
from coverage.parser import CodeParser
from coverage.plugin import Plugins, overrides

from tests.coveragetest import CoverageTest


class FakeConfig(object):
    """A fake config for use in tests."""

    def __init__(self, plugin, options):
        self.plugin = plugin
        self.options = options
        self.asked_for = []

    def get_plugin_options(self, module):
        """Just return the options for `module` if this is the right module."""
        self.asked_for.append(module)
        if module == self.plugin:
            return self.options
        else:
            return {}


class PluginUnitTest(CoverageTest):
    """Test Plugins.load_plugins directly."""

    def test_importing_and_configuring(self):
        self.make_file("plugin1.py", """\
            from coverage import CoveragePlugin

            class Plugin(CoveragePlugin):
                def __init__(self, options):
                    super(Plugin, self).__init__(options)
                    self.this_is = "me"
            """)

        config = FakeConfig("plugin1", {'a':'hello'})
        plugins = list(Plugins.load_plugins(["plugin1"], config))

        self.assertEqual(len(plugins), 1)
        self.assertEqual(plugins[0].this_is, "me")
        self.assertEqual(plugins[0].options, {'a':'hello'})
        self.assertEqual(config.asked_for, ['plugin1'])

    def test_importing_and_configuring_more_than_one(self):
        self.make_file("plugin1.py", """\
            from coverage import CoveragePlugin

            class Plugin(CoveragePlugin):
                def __init__(self, options):
                    super(Plugin, self).__init__(options)
                    self.this_is = "me"
            """)
        self.make_file("plugin2.py", """\
            from coverage import CoveragePlugin

            class Plugin(CoveragePlugin):
                pass
            """)

        config = FakeConfig("plugin1", {'a':'hello'})
        plugins = list(Plugins.load_plugins(["plugin1", "plugin2"], config))

        self.assertEqual(len(plugins), 2)
        self.assertEqual(plugins[0].this_is, "me")
        self.assertEqual(plugins[0].options, {'a':'hello'})
        self.assertEqual(plugins[1].options, {})
        self.assertEqual(config.asked_for, ['plugin1', 'plugin2'])

    def test_cant_import(self):
        with self.assertRaises(ImportError):
            _ = Plugins.load_plugins(["plugin_not_there"], None)

    def test_ok_to_not_define_plugin(self):
        self.make_file("plugin2.py", """\
            from coverage import CoveragePlugin

            Nothing = 0
            """)
        plugins = list(Plugins.load_plugins(["plugin2"], None))
        self.assertEqual(plugins, [])


class PluginTest(CoverageTest):
    """Test plugins through the Coverage class."""

    def test_plugin_imported(self):
        # Prove that a plugin will be imported.
        self.make_file("my_plugin.py", """\
            with open("evidence.out", "w") as f:
                f.write("we are here!")
            """)

        self.assert_doesnt_exist("evidence.out")
        _ = coverage.Coverage(plugins=["my_plugin"])

        with open("evidence.out") as f:
            self.assertEqual(f.read(), "we are here!")

    def test_missing_plugin_raises_import_error(self):
        # Prove that a missing plugin will raise an ImportError.
        with self.assertRaises(ImportError):
            cov = coverage.Coverage(plugins=["foo"])
            cov.start()

    def test_bad_plugin_isnt_hidden(self):
        # Prove that a plugin with an error in it will raise the error.
        self.make_file("plugin_over_zero.py", """\
            1/0
            """)
        with self.assertRaises(ZeroDivisionError):
            _ = coverage.Coverage(plugins=["plugin_over_zero"])

    def test_importing_myself(self):
        self.make_file("simple.py", """\
            import try_xyz
            a = 1
            b = 2
            """)
        self.make_file("try_xyz.py", """\
            c = 3
            d = 4
            """)

        cov = coverage.Coverage(plugins=["tests.test_plugins"])

        # Import the python file, executing it.
        self.start_import_stop(cov, "simple")

        _, statements, missing, _ = cov.analysis("simple.py")
        self.assertEqual(statements, [1,2,3])
        self.assertEqual(missing, [])
        _, statements, _, _ = cov.analysis("/src/try_ABC.zz")
        self.assertEqual(statements, [105, 106, 107, 205, 206, 207])


class Plugin(coverage.CoveragePlugin):
    def trace_judge(self, disp):
        if "xyz.py" in disp.original_filename:
            disp.trace = True
            disp.source_filename = os.path.join(
                "/src",
                os.path.basename(
                    disp.original_filename.replace("xyz.py", "ABC.zz")
                )
            )

    def line_number_range(self, frame):
        lineno = frame.f_lineno
        return lineno*100+5, lineno*100+7

    def code_unit_class(self, filename):
        return PluginCodeUnit

class PluginCodeUnit(CodeUnit):
    def get_parser(self, exclude=None):
        return PluginParser()

class PluginParser(CodeParser):
    def parse_source(self):
        return set([105, 106, 107, 205, 206, 207]), set([])


class OverridesTest(CoverageTest):
    """Test plugins.py:overrides."""

    run_in_temp_dir = False

    def test_overrides(self):
        class SomeBase(object):
            """Base class, two base methods."""
            def method1(self):
                pass

            def method2(self):
                pass

        class Derived1(SomeBase):
            """Simple single inheritance."""
            def method1(self):
                pass

        self.assertTrue(overrides(Derived1(), "method1", SomeBase))
        self.assertFalse(overrides(Derived1(), "method2", SomeBase))

        class FurtherDerived1(Derived1):
            """Derive again from Derived1, inherit its method1."""
            pass

        self.assertTrue(overrides(FurtherDerived1(), "method1", SomeBase))
        self.assertFalse(overrides(FurtherDerived1(), "method2", SomeBase))

        class FurtherDerived2(Derived1):
            """Override the overridden method."""
            def method1(self):
                pass

        self.assertTrue(overrides(FurtherDerived2(), "method1", SomeBase))
        self.assertFalse(overrides(FurtherDerived2(), "method2", SomeBase))

        class Mixin(object):
            """A mixin that overrides method1."""
            def method1(self):
                pass

        class Derived2(Mixin, SomeBase):
            """A class that gets the method from the mixin."""
            pass

        self.assertTrue(overrides(Derived2(), "method1", SomeBase))
        self.assertFalse(overrides(Derived2(), "method2", SomeBase))
