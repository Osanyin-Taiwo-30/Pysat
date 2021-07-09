#!/usr/bin/env python
# Full license can be found in License.md
# Full author list can be found in .zenodo.json file
# DOI:10.5281/zenodo.1199703
# ----------------------------------------------------------------------------

import datetime as dt
from io import StringIO
import logging
import pandas as pds
import pytest

import pysat
from pysat import constellations
from pysat.tests.registration_test_class import TestWithRegistration


class TestConstellationInitReg(TestWithRegistration):
    """Test the Constellation class initialization with registered Instruments.
    """
    @pytest.mark.parametrize("ikeys, ivals, ilen",
                             [(["platforms", "tags"], [["platname1"], [""]], 2),
                              (["names", "tags"], [["name2"], [""]], 2),
                              (["names"], [["name1", "name2"]], 15)])
    def test_construct_constellation(self, ikeys, ivals, ilen):
        """Construct a Constellation with good input
        """
        # Register fake Instrument modules
        pysat.utils.registry.register(self.module_names)

        # Initalize the Constellation using the desired kwargs
        const = pysat.Constellation(
            **{ikey: ivals[i] for i, ikey in enumerate(ikeys)})

        # Test that the appropriate number of Instruments were loaded. Each
        # fake Instrument has 5 tags and 1 inst_id.
        assert len(const.instruments) == ilen
        return

    def test_all_bad_construct_constellation(self):
        """Test raises ValueError when all inputs are unregistered
        """
        # Register fake Instrument modules
        pysat.utils.registry.register(self.module_names)

        # Raise ValueError
        with pytest.raises(ValueError) as verr:
            pysat.Constellation(platforms=['Executor'])

        assert str(verr).find("no registered packages match input") >= 0
        return

    def test_some_bad_construct_constellation(self):
        """Test partial load and log warning when some inputs are unregistered
        """
        # Initialize logging
        log_capture = StringIO()
        pysat.logger.addHandler(logging.StreamHandler(log_capture))
        pysat.logger.setLevel(logging.WARNING)

        # Register fake Instrument modules
        pysat.utils.registry.register(self.module_names)

        # Load the Constellation and capture log output
        const = pysat.Constellation(platforms=['Executor', 'platname1'],
                                    tags=[''])
        log_out = log_capture.getvalue()

        # Test the partial Constellation initialization
        assert len(const.instruments) == 2

        # Test the log warning
        assert log_out.find("unable to load some platforms") >= 0

        del log_capture, log_out, const
        return


class TestConstellationInit:
    """Test the Constellation class."""
    def setup(self):
        """Create instruments and a constellation for each test
        """
        self.instruments = constellations.single_test.instruments
        self.in_kwargs = {"instruments": self.instruments,
                          "const_module": constellations.single_test}
        self.const = None
        self.ref_time = pysat.instruments.pysat_testing._test_dates['']['']

    def teardown(self):
        """Clean up after each test
        """
        del self.const, self.instruments, self.in_kwargs, self.ref_time

    @pytest.mark.parametrize("ikey,ival,ilen",
                             [("const_module", None, 1),
                              ("instruments", None, 1),
                              (None, None, 2)])
    def test_construct_constellation(self, ikey, ival, ilen):
        """Construct a Constellation with good input
        """
        if ikey is not None:
            self.in_kwargs[ikey] = ival
        self.const = pysat.Constellation(**self.in_kwargs)
        assert len(self.const.instruments) == ilen
        return

    def test_init_constellation_bad_inst_module(self):
        """Test Constellation raises AttributeError with bad inst_module input.
        """
        with pytest.raises(AttributeError) as aerr:
            pysat.Constellation(const_module=self.instruments)

        assert str(aerr).find("missing required attribute 'instruments'")
        return

    def test_construct_raises_noniterable_error(self):
        """Attempt to construct a Constellation by const_module and list
        """
        with pytest.raises(ValueError) as verr:
            self.const = pysat.Constellation(instruments=self.instruments[0])

        assert str(verr).find("instruments argument must be list-like")
        return

    def test_construct_null(self):
        """Attempt to construct a Constellation with no arguments
        """
        self.const = pysat.Constellation()
        assert len(self.const.instruments) == 0
        return

    def test_getitem(self):
        """Test Constellation iteration through instruments attribute
        """
        self.in_kwargs['const_module'] = None
        self.const = pysat.Constellation(**self.in_kwargs)
        tst_get_inst = self.const[:]
        pysat.utils.testing.assert_lists_equal(self.instruments, tst_get_inst)
        return

    def test_repr_w_inst(self):
        """Test Constellation string output with instruments loaded
        """
        self.in_kwargs['const_module'] = None
        self.const = pysat.Constellation(**self.in_kwargs)
        out_str = self.const.__repr__()

        assert out_str.find("Constellation(instruments") >= 0
        return

    def test_str_w_inst(self):
        """Test Constellation string output with instruments loaded
        """
        self.in_kwargs['const_module'] = None
        self.const = pysat.Constellation(**self.in_kwargs)
        out_str = self.const.__str__()

        assert out_str.find("pysat Constellation ") >= 0
        assert out_str.find("Index Platform") > 0
        return

    def test_str_wo_inst(self):
        """Test Constellation string output without instruments.
        """
        self.const = pysat.Constellation()
        out_str = self.const.__str__()

        assert out_str.find("pysat Constellation ") >= 0
        assert out_str.find("No assigned Instruments") > 0
        return

    @pytest.mark.parametrize("common_index,cstr", [(True, "Common"),
                                                   (False, "Full")])
    def test_str_with_data(self, common_index, cstr):
        """Test Constellation string output with loaded data."""
        self.in_kwargs["common_index"] = common_index
        self.const = pysat.Constellation(**self.in_kwargs)
        self.const.load(date=self.ref_time)
        out_str = self.const.__str__()

        assert out_str.find("pysat Constellation ") >= 0
        assert out_str.find("{:s} time range".format(cstr)) > 0
        return

    def test_single_attachment_of_custom_function(self):
        """Test successful attachment of custom function
        """
        # Define a custom function
        def double_mlt(inst):
            dmlt = 2.0 * inst.data.mlt
            dmlt.name = 'double_mlt'
            inst.data[dmlt.name] = dmlt
            return

        # Initialize the constellation
        self.in_kwargs['const_module'] = None
        self.const = pysat.Constellation(**self.in_kwargs)

        # Add the custom function
        self.const.custom_attach(double_mlt, at_pos='end')
        self.const.load(date=self.ref_time)

        # Test the added value
        for inst in self.const:
            assert 'double_mlt' in inst.variables
            assert (inst['double_mlt'] == 2.0 * inst['mlt']).all()
        return


class TestConstellationFunc:
    """Test the Constellation class attributes and methods."""
    def setup(self):
        """Create instruments and a constellation for each test
        """
        self.inst = list(constellations.testing.instruments)
        self.const = pysat.Constellation(instruments=self.inst)
        self.ref_time = pysat.instruments.pysat_testing._test_dates['']['']
        self.attrs = ["platforms", "names", "tags", "inst_ids", "instruments",
                      "bounds", "empty", "empty_partial", "index_res",
                      "common_index", "date", "yr", "doy", "yesterday", "today",
                      "tomorrow", "variables"]

    def teardown(self):
        """Clean up after each test
        """
        del self.inst, self.const, self.ref_time, self.attrs

    def test_has_required_attrs(self):
        """Ensure the instrument has all required attributes present."""

        for req_attr in self.attrs:
            assert hasattr(self.const, req_attr)
        return

    @pytest.mark.parametrize("test_ind", [0, 1, 2, 3])
    def test_equal_length_attrs(self, test_ind):
        """Ensure each instruments-length attribute is the correct length."""
        comp_len = len(self.const.instruments)
        assert len(getattr(self.const, self.attrs[test_ind])) == comp_len
        return

    def test_bounds_passthrough(self):
        """Ensure bounds are applied to each instrument within Constellation"""

        # Set bounds
        stop_date = self.ref_time + dt.timedelta(days=365)
        self.const.bounds = (self.ref_time, stop_date)

        # Ensure constellation reports correct dates
        assert self.const.bounds[0:2] == ([self.ref_time], [stop_date])

        # Test bounds are the same for all instruments
        for instrument in self.const:
            assert instrument.bounds == self.const.bounds
        return

    def test_empty_data_index(self):
        """ Test the empty index attribute."""
        # Test the attribute with no loaded data
        assert isinstance(self.const.index, pds.Index)
        assert len(self.const.index) == 0
        return

    def test_empty_data_date(self):
        """Test the date property when no data is loaded."""
        assert self.const.date is None
        return

    def test_empty_variables(self):
        """Test the variables property when no data is loaded."""
        assert len(self.const.variables) == 0
        return

    def test_empty_flag_data_empty(self):
        """ Test the status of the empty flag for unloaded data."""
        assert self.const.empty
        assert self.const.empty_partial
        return

    def test_empty_flag_data_empty_partial_load(self):
        """ Test the status of the empty flag for partially loaded data."""
        # Load only one instrument and test the status flag
        self.const.instruments[0].load(date=self.ref_time)
        assert self.const.empty_partial
        assert not self.const.empty
        return

    def test_empty_flag_data_not_empty_partial_load(self):
        """Test the alt status of the empty flag for partially loaded data."""
        # Load only one instrument and test the status flag for alternate flag
        self.const.instruments[0].load(date=self.ref_time)
        assert not self.const._empty(all_inst=False)
        return

    def test_empty_flag_data_not_empty(self):
        """ Test the status of the empty flag for loaded data."""
        # Load data and test the status flag
        self.const.load(date=self.ref_time)
        assert not self.const.empty
        return

    @pytest.mark.parametrize("ikwarg", [{"common_index": False},
                                        {"index_res": 60.0}])
    def test_full_data_index(self, ikwarg):
        """ Test the empty index attribute."""
        # Test the attribute with loaded data
        self.const = pysat.Constellation(instruments=self.inst, **ikwarg)
        self.const.load(date=self.ref_time)
        assert isinstance(self.const.index, pds.Index)
        assert self.const.index[0] == self.ref_time

        if "index_res" in ikwarg.keys():
            assert self.const.index.freq == pds.DateOffset(
                seconds=ikwarg['index_res'])
        return

    def test_today_yesterday_and_tomorrow(self):
        """ Test the correct instantiation of yesterday/today/tomorrow dates
        """
        for cinst in self.const.instruments:
            assert cinst.today() == self.const.today()
            assert cinst.yesterday() == self.const.yesterday()
            assert cinst.tomorrow() == self.const.tomorrow()
        return

    def test_full_data_date(self):
        """Test the date property when no data is loaded."""
        # Test the attribute with loaded data
        self.const.load(date=self.ref_time)

        assert self.const.date == self.ref_time
        return

    def test_full_variables(self):
        """Test the variables property when no data is loaded."""
        # Test the attribute with loaded data
        self.const.load(date=self.ref_time)

        assert len(self.const.variables) > 0
        assert 'uts_pysat_testing' in self.const.variables
        assert 'x' in self.const.variables
        return

    def test_download(self):
        """Check that instruments are downloadable."""
        self.const.download(self.ref_time, self.ref_time)
        for inst in self.const.instruments:
            assert len(inst.files.files) > 0
        return

    def test_get_unique_attr_vals_bad_attr(self):
        """Test raises AttributeError for bad input value."""
        with pytest.raises(AttributeError) as aerr:
            self.const._get_unique_attr_vals('not_an_attr')

        assert str(aerr).find("does not have attribute") >= 0
        return

    def test_get_unique_attr_vals_bad_type(self):
        """Test raises AttributeError for bad input attribute type."""
        with pytest.raises(TypeError) as terr:
            self.const._get_unique_attr_vals('empty')

        assert str(terr).find("attribute is not list-like") >= 0
        return
