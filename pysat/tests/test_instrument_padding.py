"""Unit tests for the padding methods in `pysat.Instrument`."""

import datetime as dt
from importlib import reload
import numpy as np

import pandas as pds
import pytest

import pysat
import pysat.instruments.pysat_testing
import pysat.instruments.pysat_testing2d
import pysat.instruments.pysat_testing2d_xarray
import pysat.instruments.pysat_testing_xarray
from pysat.utils import generate_instrument_list
from pysat.utils.time import filter_datetime_input


class TestDataPaddingbyFile(object):
    """Unit tests for pandas `pysat.Instrument` with data padding by file."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing)
        self.testInst = pysat.Instrument(platform='pysat', name='testing',
                                         clean_level='clean',
                                         pad={'minutes': 5},
                                         update_files=True)
        self.testInst.bounds = ('2008-01-01.nofile', '2010-12-31.nofile')

        self.rawInst = pysat.Instrument(platform='pysat', name='testing',
                                        clean_level='clean',
                                        update_files=True)
        self.rawInst.bounds = self.testInst.bounds
        self.delta = dt.timedelta(seconds=0)
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.rawInst, self.delta
        return

    def eval_index_start_end(self):
        """Evaluate the start and end of the test `index` attributes."""

        assert self.testInst.index[0] == (self.rawInst.index[0] - self.delta), \
            "failed to pad the start of the `testInst` object"
        assert (self.testInst.index[-1]
                == (self.rawInst.index[-1] + self.delta)), \
            "failed to pad the end of the `testInst` object"

        if self.delta > dt.timedelta(seconds=0):
            assert len(self.testInst.index) > len(self.rawInst.index), \
                "padded instrument does not have enough data"
        else:
            assert len(self.testInst.index) == len(self.rawInst.index), \
                "unpadded instrument has extra or is missing data"
        return

    def test_fname_data_padding(self):
        """Test data padding load by filename."""

        self.testInst.load(fname=self.testInst.files[1], verifyPad=True)
        self.rawInst.load(fname=self.testInst.files[1])
        self.delta = dt.timedelta(minutes=5)
        self.eval_index_start_end()
        return

    def test_fname_data_padding_next(self):
        """Test data padding load by filename using `.next()`."""

        self.testInst.load(fname=self.testInst.files[1], verifyPad=True)
        self.testInst.next(verifyPad=True)
        self.rawInst.load(fname=self.testInst.files[2])
        self.delta = dt.timedelta(minutes=5)
        self.eval_index_start_end()
        return

    def test_fname_data_padding_multi_next(self):
        """Test data padding load by filename using `.next()` multiple times."""

        self.testInst.load(fname=self.testInst.files[1])
        self.testInst.next()
        self.testInst.next(verifyPad=True)
        self.rawInst.load(fname=self.testInst.files[3])
        self.delta = dt.timedelta(minutes=5)
        self.eval_index_start_end()
        return

    def test_fname_data_padding_prev(self):
        """Test data padding load by filename using `.prev()`."""

        self.testInst.load(fname=self.testInst.files[2], verifyPad=True)
        self.testInst.prev(verifyPad=True)
        self.rawInst.load(fname=self.testInst.files[1])
        self.delta = dt.timedelta(minutes=5)
        self.eval_index_start_end()
        return

    def test_fname_data_padding_multi_prev(self):
        """Test data padding load by filename using `.prev()` multiple times."""

        self.testInst.load(fname=self.testInst.files[10])
        self.testInst.prev()
        self.testInst.prev(verifyPad=True)
        self.rawInst.load(fname=self.testInst.files[8])
        self.delta = dt.timedelta(minutes=5)
        self.eval_index_start_end()
        return

    def test_fname_data_padding_jump(self):
        """Test data padding by filename after loading non-consecutive file."""

        self.testInst.load(fname=self.testInst.files[1], verifyPad=True)
        self.testInst.load(fname=self.testInst.files[10], verifyPad=True)
        self.rawInst.load(fname=self.testInst.files[10])
        self.delta = dt.timedelta(minutes=5)
        self.eval_index_start_end()
        return

    def test_fname_data_padding_uniqueness(self):
        """Ensure uniqueness data padding when loading by file."""

        self.testInst.load(fname=self.testInst.files[1], verifyPad=True)
        assert (self.testInst.index.is_unique)
        return

    def test_fname_data_padding_all_samples_present(self):
        """Ensure all samples present when padding and loading by file."""

        self.testInst.load(fname=self.testInst.files[1], verifyPad=True)
        self.delta = pds.date_range(self.testInst.index[0],
                                    self.testInst.index[-1], freq='S')
        assert (np.all(self.testInst.index == self.delta))
        return

    def test_fname_data_padding_removal(self):
        """Ensure padded samples nominally dropped, loading by file."""

        self.testInst.load(fname=self.testInst.files[1])
        self.rawInst.load(fname=self.testInst.files[1])
        self.eval_index_start_end()
        return


class TestDataPaddingbyFileXarray(TestDataPaddingbyFile):
    """Unit tests for xarray `pysat.Instrument` with data padding by file."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing_xarray)
        self.testInst = pysat.Instrument(platform='pysat',
                                         name='testing_xarray',
                                         clean_level='clean',
                                         pad={'minutes': 5},
                                         update_files=True)
        self.testInst.bounds = ('2008-01-01.nofile', '2010-12-31.nofile')

        self.rawInst = pysat.Instrument(platform='pysat',
                                        name='testing_xarray',
                                        clean_level='clean',
                                        update_files=True)
        self.rawInst.bounds = self.testInst.bounds
        self.delta = dt.timedelta(seconds=0)
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.rawInst, self.delta
        return


class TestOffsetRightFileDataPaddingBasics(TestDataPaddingbyFile):
    """Unit tests for pandas `pysat.Instrument` with right offset data pad."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing)
        self.testInst = pysat.Instrument(platform='pysat', name='testing',
                                         clean_level='clean',
                                         update_files=True,
                                         sim_multi_file_right=True,
                                         pad={'minutes': 5})
        self.rawInst = pysat.Instrument(platform='pysat', name='testing',
                                        tag='',
                                        clean_level='clean',
                                        update_files=True,
                                        sim_multi_file_right=True)
        self.testInst.bounds = ('2008-01-01.nofile', '2010-12-31.nofile')
        self.rawInst.bounds = self.testInst.bounds
        self.delta = dt.timedelta(seconds=0)
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.rawInst, self.delta
        return


class TestOffsetRightFileDataPaddingBasicsXarray(TestDataPaddingbyFile):
    """Unit tests for xarray `pysat.Instrument` with right offset data pad."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing_xarray)
        self.testInst = pysat.Instrument(platform='pysat',
                                         name='testing_xarray',
                                         clean_level='clean',
                                         update_files=True,
                                         sim_multi_file_right=True,
                                         pad={'minutes': 5})
        self.rawInst = pysat.Instrument(platform='pysat',
                                        name='testing_xarray',
                                        clean_level='clean',
                                        update_files=True,
                                        sim_multi_file_right=True)
        self.testInst.bounds = ('2008-01-01.nofile', '2010-12-31.nofile')
        self.rawInst.bounds = self.testInst.bounds
        self.delta = dt.timedelta(seconds=0)
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.rawInst, self.delta
        return


class TestOffsetLeftFileDataPaddingBasics(TestDataPaddingbyFile):
    """Unit tests for pandas `pysat.Instrument` with left offset data pad."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing)
        self.testInst = pysat.Instrument(platform='pysat', name='testing',
                                         clean_level='clean',
                                         update_files=True,
                                         sim_multi_file_left=True,
                                         pad={'minutes': 5})
        self.rawInst = pysat.Instrument(platform='pysat', name='testing',
                                        clean_level='clean',
                                        update_files=True,
                                        sim_multi_file_left=True)
        self.testInst.bounds = ('2008-01-01.nofile', '2010-12-31.nofile')
        self.rawInst.bounds = self.testInst.bounds
        self.delta = dt.timedelta(seconds=0)
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.rawInst, self.delta
        return


class TestDataPadding(object):
    """Unit tests for pandas `pysat.Instrument` with data padding."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing)
        self.testInst = pysat.Instrument(platform='pysat', name='testing',
                                         clean_level='clean',
                                         pad={'minutes': 5},
                                         update_files=True)
        self.ref_time = dt.datetime(2009, 1, 2)
        self.ref_doy = 2
        self.delta = dt.timedelta(minutes=5)
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.ref_time, self.ref_doy
        return

    def eval_index_start_end(self):
        """Evaluate the start and end of the test `index` attributes."""

        assert (self.testInst.index[0]
                == self.testInst.date - self.delta), \
            "failed to pad the start of the `testInst` object"
        assert (self.testInst.index[-1] == self.testInst.date
                + dt.timedelta(hours=23, minutes=59, seconds=59)
                + self.delta), \
            "failed to pad the end of the `testInst` object"
        return

    def test_data_padding(self):
        """Ensure that pad works at the instrument level."""

        self.testInst.load(self.ref_time.year, self.ref_doy, verifyPad=True)
        self.eval_index_start_end()
        return

    @pytest.mark.parametrize('pad', [dt.timedelta(minutes=5),
                                     pds.DateOffset(minutes=5),
                                     {'minutes': 5}])
    def test_data_padding_offset_instantiation(self, pad):
        """Ensure pad can be used as datetime, pandas, or dict."""

        self.testInst = pysat.Instrument(platform='pysat', name='testing',
                                         clean_level='clean',
                                         pad=pad,
                                         update_files=True)
        self.testInst.load(self.ref_time.year, self.ref_doy, verifyPad=True)
        self.eval_index_start_end()
        return

    def test_data_padding_bad_instantiation(self):
        """Ensure error when padding input type incorrect."""

        with pytest.raises(ValueError) as err:
            pysat.Instrument(platform='pysat', name='testing',
                             clean_level='clean',
                             pad=2,
                             update_files=True)
        estr = ' '.join(('pad must be a dict, NoneType, datetime.timedelta,',
                         'or pandas.DateOffset instance.'))
        assert str(err).find(estr) >= 0
        return

    def test_data_padding_bad_load(self):
        """Test that data padding when loading all data is not allowed."""

        with pytest.raises(ValueError) as err:
            self.testInst.load()

        if self.testInst.multi_file_day:
            estr = '`load()` is not supported with multi_file_day'
        else:
            estr = '`load()` is not supported with data padding'
        assert str(err).find(estr) >= 0
        return

    def test_padding_exceeds_load_window(self):
        """Ensure error is padding window larger than loading window."""

        self.testInst = pysat.Instrument(platform='pysat', name='testing',
                                         clean_level='clean',
                                         pad={'days': 2},
                                         update_files=True)
        with pytest.raises(ValueError) as err:
            self.testInst.load(date=self.ref_time)
        estr = 'Data padding window must be shorter than '
        assert str(err).find(estr) >= 0
        return

    def test_yrdoy_data_padding_missing_earlier_days(self):
        """Test padding feature operates when there are missing prev days."""

        yr, doy = pysat.utils.time.getyrdoy(self.testInst.files.start_date)
        self.testInst.load(yr, doy, verifyPad=True)
        assert self.testInst.index[0] == self.testInst.date
        assert (self.testInst.index[-1]
                > self.testInst.date + dt.timedelta(days=1))

        self.testInst.load(yr, doy)
        assert self.testInst.index[0] == self.testInst.date
        assert (self.testInst.index[-1]
                < self.testInst.date + dt.timedelta(days=1))
        return

    def test_yrdoy_data_padding_missing_later_days(self):
        """Test padding feature operates when there are missing later days."""

        yr, doy = pysat.utils.time.getyrdoy(self.testInst.files.stop_date)
        self.testInst.load(yr, doy, verifyPad=True)
        assert self.testInst.index[0] < self.testInst.date
        assert (self.testInst.index[-1]
                < self.testInst.date + dt.timedelta(days=1))

        self.testInst.load(yr, doy)
        assert self.testInst.index[0] == self.testInst.date
        assert (self.testInst.index[-1]
                < self.testInst.date + dt.timedelta(days=1))
        return

    def test_yrdoy_data_padding_missing_earlier_and_later_days(self):
        """Test padding feature operates if missing earlier/later days."""

        # reduce available files
        self.testInst.files.files = self.testInst.files.files[0:1]
        yr, doy = pysat.utils.time.getyrdoy(self.testInst.files.start_date)
        self.testInst.load(yr, doy, verifyPad=True)
        assert self.testInst.index[0] == self.testInst.date
        assert (self.testInst.index[-1] < self.testInst.date
                + dt.timedelta(days=1))
        return

    def test_data_padding_next(self):
        """Test data padding with `.next()`."""

        self.testInst.load(self.ref_time.year, self.ref_doy, verifyPad=True)
        self.testInst.next(verifyPad=True)
        self.eval_index_start_end()
        return

    def test_data_padding_multi_next(self):
        """Test data padding with multiple `.next()`."""

        self.testInst.load(self.ref_time.year, self.ref_doy)
        self.testInst.next()
        self.testInst.next(verifyPad=True)
        self.eval_index_start_end()
        return

    def test_data_padding_prev(self):
        """Test data padding with `.prev()`."""

        self.testInst.load(self.ref_time.year, self.ref_doy, verifyPad=True)
        self.testInst.prev(verifyPad=True)
        self.eval_index_start_end()
        return

    def test_data_padding_multi_prev(self):
        """Test data padding with multiple `.prev()`."""

        self.ref_doy = 10
        self.testInst.load(self.ref_time.year, self.ref_doy)
        self.testInst.prev()
        self.testInst.prev(verifyPad=True)
        self.eval_index_start_end()
        return

    def test_data_padding_jump(self):
        """Test data padding -- do not understand."""
        self.testInst.load(self.ref_time.year, self.ref_doy, verifyPad=True)
        self.testInst.load(self.ref_time.year, self.ref_doy + 10,
                           verifyPad=True)
        self.eval_index_start_end()
        return

    def test_data_padding_uniqueness(self):
        """Test index after data padding is unique."""

        self.ref_doy = 1
        self.testInst.load(self.ref_time.year, self.ref_doy, verifyPad=True)
        assert (self.testInst.index.is_unique)
        return

    def test_data_padding_all_samples_present(self):
        """Test data padding when all samples are present."""

        self.ref_doy = 1
        self.testInst.load(self.ref_time.year, self.ref_doy, verifyPad=True)
        test_index = pds.date_range(self.testInst.index[0],
                                    self.testInst.index[-1], freq='S')
        assert (np.all(self.testInst.index == test_index))
        return

    def test_data_padding_removal(self):
        """Test data padding removal."""

        self.ref_doy = 1
        self.testInst.load(self.ref_time.year, self.ref_doy)
        self.delta = dt.timedelta(seconds=0)
        self.eval_index_start_end()
        return


class TestDataPaddingXarray(TestDataPadding):
    """Unit tests for xarray `pysat.Instrument` with data padding."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing_xarray)
        self.testInst = pysat.Instrument(platform='pysat',
                                         name='testing_xarray',
                                         clean_level='clean',
                                         pad={'minutes': 5},
                                         update_files=True)
        self.ref_time = dt.datetime(2009, 1, 2)
        self.ref_doy = 2
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.ref_time, self.ref_doy
        return


class TestMultiFileRightDataPaddingBasics(TestDataPadding):
    """Unit tests for pandas `pysat.Instrument` with right offset data pad."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing)
        self.testInst = pysat.Instrument(platform='pysat', name='testing',
                                         clean_level='clean',
                                         update_files=True,
                                         sim_multi_file_right=True,
                                         pad={'minutes': 5})
        self.testInst.multi_file_day = True
        self.ref_time = dt.datetime(2009, 1, 2)
        self.ref_doy = 2
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.ref_time, self.ref_doy
        return


class TestMultiFileRightDataPaddingBasicsXarray(TestDataPadding):
    """Unit tests for xarray `pysat.Instrument` with right offset data pad."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing_xarray)
        self.testInst = pysat.Instrument(platform='pysat',
                                         name='testing_xarray',
                                         clean_level='clean',
                                         update_files=True,
                                         sim_multi_file_right=True,
                                         pad={'minutes': 5})
        self.testInst.multi_file_day = True
        self.ref_time = dt.datetime(2009, 1, 2)
        self.ref_doy = 2
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.ref_time, self.ref_doy
        return


class TestMultiFileLeftDataPaddingBasics(TestDataPadding):
    """Unit tests for pandas `pysat.Instrument` with left offset data pad."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing)
        self.testInst = pysat.Instrument(platform='pysat',
                                         name='testing',
                                         clean_level='clean',
                                         update_files=True,
                                         sim_multi_file_left=True,
                                         pad={'minutes': 5})
        self.testInst.multi_file_day = True
        self.ref_time = dt.datetime(2009, 1, 2)
        self.ref_doy = 2
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.ref_time, self.ref_doy
        return


class TestMultiFileLeftDataPaddingBasicsXarray(TestDataPadding):
    """Unit tests for xarray `pysat.Instrument` with left offset data pad."""

    def setup(self):
        """Set up the unit test environment for each method."""

        reload(pysat.instruments.pysat_testing_xarray)
        self.testInst = pysat.Instrument(platform='pysat',
                                         name='testing_xarray',
                                         clean_level='clean',
                                         update_files=True,
                                         sim_multi_file_left=True,
                                         pad={'minutes': 5})
        self.testInst.multi_file_day = True
        self.ref_time = dt.datetime(2009, 1, 2)
        self.ref_doy = 2
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        del self.testInst, self.ref_time, self.ref_doy
        return


class TestInstListGeneration(object):
    """Tests to ensure the instrument test class is working as expected."""

    def setup(self):
        """Set up the unit test environment for each method."""

        self.test_library = pysat.instruments
        return

    def teardown(self):
        """Clean up the unit test environment after each method."""

        # reset pysat instrument library
        reload(pysat.instruments)
        reload(pysat.instruments.pysat_testing)
        del self.test_library
        return

    def test_import_error_behavior(self):
        """Test that instrument list works if a broken instrument is found."""

        self.test_library.__all__.append('broken_inst')
        # This instrument does not exist.  The routine should run without error
        inst_list = generate_instrument_list(self.test_library)
        assert 'broken_inst' in inst_list['names']
        for dict in inst_list['download']:
            assert 'broken_inst' not in dict['inst_module'].__name__
        for dict in inst_list['no_download']:
            assert 'broken_inst' not in dict['inst_module'].__name__
        return

    def test_for_missing_test_date(self):
        """Test that instruments without _test_dates are added to the list."""

        del self.test_library.pysat_testing._test_dates
        # If an instrument does not have the _test_dates attribute, it should
        # still be added to the list for other checks to be run
        # This will be caught later by InstTestClass.test_instrument_test_dates
        assert not hasattr(self.test_library.pysat_testing, '_test_dates')
        inst_list = generate_instrument_list(self.test_library)
        assert 'pysat_testing' in inst_list['names']
        return
