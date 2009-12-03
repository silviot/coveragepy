.. _api:

============
Coverage API
============

:history: 20090524T134300, brand new docs.
:history: 20090613T164000, final touches for 3.0

The API to coverage.py is very simple, contained in a single module called
coverage containing a single class, also called coverage. Methods on the
coverage object correspond to operations available in the command line
interface. For example, a simple use would be::

    import coverage

    cov = coverage.coverage()
    cov.start()

    # .. run your code ..

    cov.stop()
    cov.save()


The coverage module
-------------------

.. module:: coverage

.. autoclass:: coverage
    :members:
