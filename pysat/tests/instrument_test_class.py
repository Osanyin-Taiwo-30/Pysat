"""Standardized class and functions to test instruments for pysat libraries.

Note
----
Not directly called by pytest, but imported as part of test_instruments.py.
Can be imported directly for external instrument libraries of pysat instruments.

"""

import warnings

import pysat.tests.classes.cls_instrument_library as cls_inst_lib


def initialize_test_inst_and_date(inst_dict):
    """Initialize the instrument object to test and date.

    .. deprecated:: 3.0.2
        `initialize_test_inst_and_date` will be removed in pysat 3.2.0, it is
        moved to `pysat.tests.classes.cls_instrument_library`.

    Parameters
    ----------
    inst_dict : dict
        Dictionary containing specific instrument info, generated by
        generate_instrument_list

    Returns
    -------
    test_inst : pysat.Instrument
        instrument object to be tested
    date : dt.datetime
        test date from module

    """

    warnings.warn(" ".join(["`initialize_test_inst_and_date` has been moved to",
                            "`pysat.tests.classes.cls_instrument_library`.",
                            "The link here will be removed in 3.2.0+."]),
                  DeprecationWarning, stacklevel=2)
    return cls_inst_lib.initialize_test_inst_and_date(inst_dict)


class InstTestClass(cls_inst_lib.InstLibTests):
    """Provide standardized tests for pysat instrument libraries.

    .. deprecated:: 3.0.2
        `InstTestClass` will be removed in pysat 3.2.0, it is replaced by
        `pysat.tests.classes.cls_instrument_library.InstLibTests`.

    Note
    ----
    Uses class level setup and teardown so that all tests use the same
    temporary directory. We do not want to geneate a new tempdir for each test,
    as the load tests need to be the same as the download tests.

    Not directly run by pytest, but inherited through test_instruments.py

    Users will need to run `apply_marks_to_tests` before setting up the test
    class.

    """

    def __init_subclass__(self):
        """Throw a warning if used as a subclass."""

        warnings.warn(" ".join(
            ["`InstTestClass` has been deprecated and will be removed in",
             "3.2.0+.  Please update code to use the `InstLibTests` class",
             "under `pysat.tests.classes.cls_instrument_library`."]),
            DeprecationWarning, stacklevel=2)
        warnings.warn(" ".join(
            ["`test_load` now uses `@pytest.mark.load_options` in place",
             "of `@pytest.mark.download`.  The old behavior will be removed in",
             "3.2.0+.  Please update code or use the new"
             "`InstLibTests.initialize_test_package` function",
             "under `pysat.tests.classes.cls_instrument_library`."]),
            DeprecationWarning, stacklevel=2)
