def html_it():
    """Run coverage and make an HTML report for main."""
    import coverage
    cov = coverage.coverage(include=["./*"])
    cov.start()
    import main         # pragma: nested
    cov.stop()          # pragma: nested
    cov.html_report(directory="../html_omit_1")

runfunc(html_it, rundir="src")
compare("gold_omit_1", "html_omit_1", size_within=10, file_pattern="*.html")
clean("html_omit_1")
