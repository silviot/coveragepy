"""Control of and utilities for debugging."""

import inspect
import os


# When debugging, it can be helpful to force some options, especially when
# debugging the configuration mechanisms you usually use to control debugging!
# This is a list of forced debugging options.
FORCED_DEBUG = []


class DebugControl(object):
    """Control and output for debugging."""

    def __init__(self, options, output):
        """Configure the options and output file for debugging."""
        self.options = options
        self.output = output

    def __repr__(self):
        return "<DebugControl options=%r output=%r>" % (
            self.options, self.output
            )

    def should(self, option):
        """Decide whether to output debug information in category `option`."""
        return (option in self.options or option in FORCED_DEBUG)

    def write(self, msg):
        """Write a line of debug output."""
        if self.should('pid'):
            msg = "pid %5d: %s" % (os.getpid(), msg)
        self.output.write(msg+"\n")
        self.output.flush()

    def write_formatted_info(self, header, info):
        """Write a sequence of (label,data) pairs nicely."""
        self.write(info_header(header))
        for line in info_formatter(info):
            self.write(" %s" % line)


def info_header(label):
    """Make a nice header string."""
    return "--{0:-<60s}".format(" "+label+" ")


def info_formatter(info):
    """Produce a sequence of formatted lines from info.

    `info` is a sequence of pairs (label, data).  The produced lines are
    nicely formatted, ready to print.

    """
    info = list(info)
    if not info:
        return
    label_len = max(len(l) for l, _d in info)
    for label, data in info:
        if data == []:
            data = "-none-"
        if isinstance(data, (list, set, tuple)):
            prefix = "%*s:" % (label_len, label)
            for e in data:
                yield "%*s %s" % (label_len+1, prefix, e)
                prefix = ""
        else:
            yield "%*s: %s" % (label_len, label, data)


def short_stack():                                          # pragma: debugging
    """Return a string summarizing the call stack.

    The string is multi-line, with one line per stack frame. Each line shows
    the function name, the file name, and the line number:

        ...
        start_import_stop : /Users/ned/coverage/trunk/tests/coveragetest.py @95
        import_local_file : /Users/ned/coverage/trunk/tests/coveragetest.py @81
        import_local_file : /Users/ned/coverage/trunk/coverage/backward.py @159
        ...

    """
    stack = inspect.stack()[:0:-1]
    return "\n".join("%30s : %s @%d" % (t[3], t[1], t[2]) for t in stack)


def dump_stack_frames():                                    # pragma: debugging
    """Print a summary of the stack to stdout."""
    print(short_stack())
