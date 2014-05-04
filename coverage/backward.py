"""Add things to old Pythons so I can pretend they are newer."""

# This file does lots of tricky stuff, so disable a bunch of lintisms.
# pylint: disable=F0401,W0611,W0622
# F0401: Unable to import blah
# W0611: Unused import blah
# W0622: Redefining built-in blah

import os, re, sys

# Pythons 2 and 3 differ on where to get StringIO.
try:
    from cStringIO import StringIO
    BytesIO = StringIO
except ImportError:
    from io import StringIO, BytesIO

# What's a string called?
try:
    string_class = basestring
except NameError:
    string_class = str

# Where do pickles come from?
try:
    import cPickle as pickle
except ImportError:
    import pickle

# range or xrange?
try:
    range = xrange
except NameError:
    range = range

# A function to iterate listlessly over a dict's items.
try:
    {}.iteritems
except AttributeError:
    def iitems(d):
        """Produce the items from dict `d`."""
        return d.items()
else:
    def iitems(d):
        """Produce the items from dict `d`."""
        return d.iteritems()

# Reading Python source and interpreting the coding comment is a big deal.
if sys.version_info >= (3, 0):
    # Python 3.2 provides `tokenize.open`, the best way to open source files.
    import tokenize
    try:
        open_python_source = tokenize.open     # pylint: disable=E1101
    except AttributeError:
        from io import TextIOWrapper
        detect_encoding = tokenize.detect_encoding  # pylint: disable=E1101
        # Copied from the 3.2 stdlib:
        def open_python_source(fname):
            """Open a file in read only mode using the encoding detected by
            detect_encoding().
            """
            buffer = open(fname, 'rb')
            encoding, _ = detect_encoding(buffer.readline)
            buffer.seek(0)
            text = TextIOWrapper(buffer, encoding, line_buffering=True)
            text.mode = 'r'
            return text
else:
    def open_python_source(fname):
        """Open a source file the best way."""
        return open(fname, "rU")


# Python 3.x is picky about bytes and strings, so provide methods to
# get them right, and make them no-ops in 2.x
if sys.version_info >= (3, 0):
    def to_bytes(s):
        """Convert string `s` to bytes."""
        return s.encode('utf8')

    def to_string(b):
        """Convert bytes `b` to a string."""
        return b.decode('utf8')

    def binary_bytes(byte_values):
        """Produce a byte string with the ints from `byte_values`."""
        return bytes(byte_values)

    def byte_to_int(byte_value):
        """Turn an element of a bytes object into an int."""
        return byte_value

    def bytes_to_ints(bytes_value):
        """Turn a bytes object into a sequence of ints."""
        # In Py3, iterating bytes gives ints.
        return bytes_value

else:
    def to_bytes(s):
        """Convert string `s` to bytes (no-op in 2.x)."""
        return s

    def to_string(b):
        """Convert bytes `b` to a string (no-op in 2.x)."""
        return b

    def binary_bytes(byte_values):
        """Produce a byte string with the ints from `byte_values`."""
        return "".join(chr(b) for b in byte_values)

    def byte_to_int(byte_value):
        """Turn an element of a bytes object into an int."""
        return ord(byte_value)

    def bytes_to_ints(bytes_value):
        """Turn a bytes object into a sequence of ints."""
        for byte in bytes_value:
            yield ord(byte)

# Md5 is available in different places.
try:
    import hashlib
    md5 = hashlib.md5
except ImportError:
    import md5
    md5 = md5.new
