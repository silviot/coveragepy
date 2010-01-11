@echo off
make --quiet testdata

for %%v in (23 24 25 26 27) do (
    call \ned\bin\switchpy %%v
    python setup.py -q develop
    set COVERAGE_TEST_TRACER=c
    nosetests %1 %2 %3 %4 %5 %6 %7 %8 %9
    del coverage\tracer.pyd
    set COVERAGE_TEST_TRACER=py
    nosetests %1 %2 %3 %4 %5 %6 %7 %8 %9
    )

call \ned\bin\switchpy 31
python setup.py -q develop
set COVERAGE_TEST_TRACER=c
python \python31\Scripts\nosetests3 %1 %2 %3 %4 %5 %6 %7 %8 %9
del coverage\tracer.pyd
set COVERAGE_TEST_TRACER=py
python \python31\Scripts\nosetests3 %1 %2 %3 %4 %5 %6 %7 %8 %9

make --quiet clean
