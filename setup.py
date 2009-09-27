# setup.py for coverage.

"""Code coverage measurement for Python

Coverage.py measures code coverage, typically during test execution. It uses the
code analysis tools and tracing hooks provided in the Python standard library to
determine which lines are executable, and which have been executed.

Coverage.py runs on Pythons 2.3 through 3.1.

Documentation is at `nedbatchelder.com <%s>`_.  Code repository and issue
tracker are at `bitbucket.org <http://bitbucket.org/ned/coveragepy>`_.

"""

# This file is used unchanged under all versions of Python, 2.x and 3.x.

classifiers = """
Environment :: Console
Intended Audience :: Developers
License :: OSI Approved :: BSD License
Operating System :: OS Independent
Programming Language :: Python
Topic :: Software Development :: Quality Assurance
Topic :: Software Development :: Testing
"""

# Pull in the tools we need.
import sys

if sys.hexversion < 0x03000000:
    # In Py 2.x, use setuptools.
    from ez_setup import use_setuptools
    use_setuptools()
    
    from setuptools import setup
    from distutils.core import Extension

    more_setup_args = dict(
        entry_points = {
            'console_scripts': [
                'coverage = coverage:main',
                ]
            },
        
        # We need to get HTML assets from our htmlfiles dir.
        zip_safe = False,
        )
else:
    # No setuptools yet for Py 3.x, so do without.
    from distutils.core import setup, Extension

    more_setup_args = dict(
        scripts = [
            'scripts/coverage',
            ],
        )


# Get or massage our metadata.

from coverage import __url__, __version__

doclines = (__doc__ % __url__).split('\n')

classifier_list = [c for c in classifiers.split("\n") if c]

if 'a' in __version__:
    devstat = "3 - Alpha"
elif 'b' in __version__:
    devstat = "4 - Beta"
else:
    devstat = "5 - Production/Stable"
classifier_list.append("Development Status :: " + devstat)

# Set it up!

setup(
    name = 'coverage',
    version = __version__,

    packages = [
        'coverage',
        ],

    package_data = {
        'coverage': [
            'htmlfiles/*.*',
            ]
        },

    ext_modules = [
        Extension("coverage.tracer", sources=["coverage/tracer.c"])
        ],
    
    author = 'Ned Batchelder',
    author_email = 'ned@nedbatchelder.com',
    description = doclines[0],
    long_description = '\n'.join(doclines[2:]),
    keywords = 'code coverage testing',
    license = 'BSD',
    classifiers = classifier_list,
    url = __url__,
    
    **more_setup_args
    )
