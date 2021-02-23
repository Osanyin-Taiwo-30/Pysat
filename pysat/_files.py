#!/usr/bin/env python
# Full license can be found in License.md
# Full author list can be found in .zenodo.json file
# DOI:10.5281/zenodo.1199703
# ----------------------------------------------------------------------------

import datetime as dt
from functools import partial
import numpy as np
import os
import warnings

import pandas as pds

import pysat  # Needed to access pysat.params across reimports
from pysat.utils import files as futils
from pysat.utils.time import filter_datetime_input
from pysat.instruments.methods import general

logger = pysat.logger


class Files(object):
    """Maintains collection of files and associated methods.

    Parameters
    ----------
    inst : pysat.Instrument
        Instrument object
    directory_format : str or NoneType
        Directory naming structure in string format. Variables such as
        platform, name, and tag will be filled in as needed using python
        string formatting. The default directory structure would be
        expressed as '{platform}/{name}/{tag}/{inst_id}'. If None, the default
        directory structure is used (default=None)
    update_files : boolean
        If True, immediately query filesystem for instrument files and
        store (default=False)
    file_format : str or NoneType
        File naming structure in string format.  Variables such as year,
        month, and inst_id will be filled in as needed using python string
        formatting.  The default file format structure is supplied in the
        instrument list_files routine. (default=None)
    write_to_disk : boolean
        If true, the list of Instrument files will be written to disk.
        (default=True)
    ignore_empty_files : boolean
        If True, the list of files found will be checked to ensure the
        filesizes are greater than zero. Empty files are removed from the
        stored list of files. (default=False)

    Attributes
    ----------
    home_path : str
        Path to the pysat information directory.
    data_path : str
        Path to the top-level directory containing instrument files,
        selected from data_paths.
    data_paths: list of str
        Available paths that pysat will use when looking for files. The
        class uses the first directory with relevant data, stored in data_path.
    files : pds.Series
        Series of data files, indexed by file start time
    inst_info : dict
        Contains pysat.Instrument parameters 'platform', 'name', 'tag',
        and 'inst_id', identifying the source of the files.
    list_files_creator : functools.partial or NoneType
        Experimental feature for Instruments that internally generate data
        and thus don't have a defined supported date range.
    list_files_rtn : method
        Method used to locate relevant files on the local system. Provided
        by associated pysat.Instrument object.
    multi_file_day : boolean
        Flag copied from associated pysat.Instrument object that indicates
        when data for day n may be found in files for days n-1, or n+1
    start_date : datetime or NoneType
        Date of first file, used as default start bound for instrument
        object, or None if no files are loaded.
    stop_date : datetime or NoneType
        Date of last file, used as default stop bound for instrument
        object, or None if no files are loaded.
    stored_file_name : str
        Name of the hidden file containing the list of archived data files
        for this instrument.
    sub_dir_path : str
        `directory_format` string formatted for the local system.


    Note
    ----
    Interfaces with the `list_files` method for a given instrument
    support module to create an ordered collection of files in time,
    used primarily by the pysat.Instrument object to identify files
    to be loaded. The Files class mediates access to the files by
    datetime and contains helper methods for determining the presence of
    new files and filtering out empty files.

    User should generally use the interface provided by a pysat.Instrument
    instance. Exceptions are the classmethod from_os, provided to assist
    in generating the appropriate output for an instrument routine.

    Examples
    --------
    ::

        # convenient file access
        inst = pysat.Instrument(platform=platform, name=name, tag=tag,
                                inst_id=inst_id)
        # first file
        inst.files[0]

        # files from start up to stop (exclusive on stop)
        start = dt.datetime(2009,1,1)
        stop = dt.datetime(2009,1,3)
        print(inst.files[start:stop])

        # files for date
        print(inst.files[start])

        # files by slicing
        print(inst.files[0:4])

        # get a list of new files
        # new files are those that weren't present the last time
        # a given instrument's file list was stored
        new_files = inst.files.get_new()

        # search pysat appropriate directory for instrument files and
        # update Files instance.
        inst.files.refresh()

    """

    # -----------------------------------------------------------------------
    # Define the magic methods

    def __init__(self, inst, directory_format=None, update_files=False,
                 file_format=None, write_to_disk=True,
                 ignore_empty_files=False):

        # Set the hidden variables
        self.update_files = update_files

        # Location of directory to store file information in
        self.home_path = os.path.join(pysat.pysat_dir, 'instruments')

        # Assign base default dates and an empty list of files
        self.start_date = None
        self.stop_date = None
        self.files = pds.Series(None, dtype='object')

        # Grab Instrument info
        self.inst_info = {'platform': inst.platform, 'name': inst.name,
                          'tag': inst.tag, 'inst_id': inst.inst_id,
                          'inst_module': inst.inst_module}
        self.list_files_rtn = inst._list_files_rtn

        self.multi_file_day = inst.multi_file_day

        # Begin with presumption that the list_files_rtn is a typical
        # function that returns a Series of filenames. Some generated
        # data sets employ a function that creates filenames on-the-fly.
        self.list_files_creator = None

        # Set the location of stored files
        self.stored_file_name = '_'.join((self.inst_info['platform'],
                                          self.inst_info['name'],
                                          self.inst_info['tag'],
                                          self.inst_info['inst_id'],
                                          'stored_file_info.txt'))

        # Set the path for sub-directories under pysat data path
        if directory_format is None:
            # Assign stored template if user doesn't provide one.
            directory_format = pysat.params['directory_format']
        self.directory_format = directory_format

        # Set the user-specified file format
        self.file_format = file_format

        # Construct the subdirectory path
        self.sub_dir_path = os.path.normpath(
            self.directory_format.format(**self.inst_info))

        # Ensure we have at least one path for pysat data directory
        if len(pysat.params['data_dirs']) == 0:
            raise NameError(" ".join(("pysat's `data_dirs` hasn't been set.",
                                      "Please set a top-level directory",
                                      "path to store data using",
                                      "`pysat.params['data_dirs'] = path`")))

        # Get list of potential data directory paths from pysat. Construct
        # possible locations for data. Ensure path always ends with directory
        # separator.
        self.data_paths = [os.path.join(pdir, self.sub_dir_path)
                           for pdir in pysat.params['data_dirs']]
        self.data_paths = [os.path.join(os.path.normpath(pdir), '')
                           for pdir in self.data_paths]

        # Only one of the above paths will actually be used when loading data.
        # The actual value of data_path is determined in refresh().
        # If there are files present, then that path is stored along with a
        # list of found files in ~/.pysat. This stored info is retrieved by
        # _load. We start here with the first directory for cases where there
        # are no files.
        self.data_path = self.data_paths[0]

        # Set the preference of writing the file list to disk or not
        self.write_to_disk = write_to_disk
        if not self.write_to_disk:
            # Use blank memory rather than loading from disk
            self._previous_file_list = pds.Series([], dtype='a')
            self._current_file_list = pds.Series([], dtype='a')

        # Set the preference to ignore or include empty files
        self.ignore_empty_files = ignore_empty_files

        if self.inst_info['platform'] != '':
            # Only load filenames if this is associated with a real
            # pysat.Instrument instance, not pysat.Instrument().
            if self.update_files:
                # Refresh filenames as directed by user
                self.refresh()
            else:
                # Load stored file info
                file_info = self._load()
                if file_info.empty:
                    # Didn't find stored information. Search local system.
                    # If list_files_rtn returns a dict to create
                    # filenames as needed that is handled in refresh.
                    self.refresh()
                else:
                    # Attach the data loaded
                    self._attach_files(file_info)
        return

    def __repr__(self):
        """ Representation of the class and its current state
        """
        inst_repr = pysat.Instrument(**self.inst_info).__repr__()

        out_str = "".join(["pysat.Files(", inst_repr, ", directory_format=",
                           "'{:}'".format(self.directory_format),
                           ", update_files=",
                           "{:}, file_format=".format(self.update_files),
                           "{:}, ".format(self.file_format.__repr__()),
                           "write_to_disk={:}, ".format(self.write_to_disk),
                           "ignore_empty_files=",
                           "{:})".format(self.ignore_empty_files)])

        return out_str

    def __str__(self):
        """ Description of the class and its contents
        """

        num_files = len(self.files)
        output_str = 'Local File Statistics\n'
        output_str += '---------------------\n'
        output_str += 'Number of files: {:d}\n'.format(num_files)

        if num_files > 0:
            output_str += 'Date Range: '
            output_str += self.files.index[0].strftime('%d %B %Y')
            output_str += ' --- '
            output_str += self.files.index[-1].strftime('%d %B %Y')

        return output_str

    def __getitem__(self, key):
        """ Retrieve items from the files attribute

        Parameters
        ----------
        key : int, list, slice, dt.datetime
            Key for locating files from a pandas Series indexed by time

        Returns
        -------
        out : pds.Series
           Subset of the files as a Series

        Raises
        ------
        IndexError
            If data is outside of file bounds

        Note
        ----
        Slicing via date and index filename is inclusive slicing, date and
        index are normal non-inclusive end point

        """
        if self.list_files_creator is not None:
            # Return filename generated on demand
            out = self.list_files_creator(key)

        elif isinstance(key, slice):
            try:
                try:
                    # Assume key is integer (including list or slice)
                    out = self.files.iloc[key]
                except TypeError:
                    # The key must be something else, use alternative access
                    out = self.files.loc[key]
            except IndexError as err:
                raise IndexError(''.join((str(err), '\n',
                                          'Date requested outside file ',
                                          'bounds.')))

            if isinstance(key.start, dt.datetime):
                # Enforce exclusive slicing on datetime
                if len(out) > 1:
                    if out.index[-1] >= key.stop:
                        out = out[:-1]
                elif len(out) == 1:
                    if out.index[0] >= key.stop:
                        out = pds.Series([], dtype='a')
        else:
            try:
                # Assume key is integer (including list or slice)
                out = self.files.iloc[key]
            except TypeError:
                # The key must be something else, use alternative access
                out = self.files.loc[key]

        return out

    # -----------------------------------------------------------------------
    # Define the hidden methods

    def _filter_empty_files(self, path):
        """Update the file list (self.files) with empty files removed

        Parameters
        ----------
        path : str
            Path to top-level containing files
        """

        keep_index = []
        for i, fname in enumerate(self.files):
            # Create full path for each file
            full_fname = os.path.join(path, fname)

            # Ensure the file exists
            if os.path.isfile(full_fname):
                # Check for size
                if os.path.getsize(full_fname) > 0:
                    # Store if not empty
                    keep_index.append(i)

        # Remove filenames as needed
        dropped_num = len(self.files.index) - len(keep_index)
        if dropped_num > 0:
            logger.warning(' '.join(('Removing {:d}'.format(dropped_num),
                                     'empty files from Instrument list.')))
            self.files = self.files.iloc[keep_index]

        return

    def _attach_files(self, files_info):
        """Attaches stored file lists to self.files

        Parameters
        ---------
        files_info : pds.Series
            Stored file information, filenames indexed by datetime

        Note
        ----
        Updates the file list (files), start_date, and stop_date attributes
        of the Files class object.

        """

        if not files_info.empty:
            # Attach data
            self.files = files_info

            # Ensure times are unique.
            self._ensure_unique_file_datetimes()

            # Filter for empty files.
            if self.ignore_empty_files:
                self._filter_empty_files(path=self.data_path)

            # Extract date information from first and last files
            if not self.files.empty:
                self.start_date = filter_datetime_input(self.files.index[0])
                self.stop_date = filter_datetime_input(self.files.index[-1])
            else:
                # No files found
                self.start_date = None
                self.stop_date = None
        else:
            # No files found
            self.start_date = None
            self.stop_date = None

            # Convert to object type if Series is empty.  This allows for
            # `==` equality checks with strings
            self.files = files_info.astype(np.dtype('O'))

        return

    def _ensure_unique_file_datetimes(self):
        """Update the file list (self.files) to ensure uniqueness"""

        # Check if files are unique.
        unique_files = len(self.files.index.unique()) == len(self.files)

        if not self.multi_file_day and not unique_files:
            # Give user feedback about the issue
            estr = ''.join(['Duplicate datetimes in stored filename ',
                            'information.\nKeeping one of each ',
                            'of the duplicates, dropping the rest. ',
                            'Please ensure the file datetimes ',
                            'are unique at the microsecond level.'])
            logger.warning(estr)
            ind = self.files.index.duplicated()
            logger.warning(self.files.index[ind].unique())

            # Downselect to unique file datetimes
            idx = np.unique(self.files.index, return_index=True)
            self.files = self.files.iloc[idx[1]]

        return

    def _store(self):
        """Store currently loaded filelist for instrument onto filesystem
        """

        stored_name = self.stored_file_name

        # Check if current file data is different than stored file list. If so,
        # move file list to previous file list, store current to file. If not,
        # do nothing
        stored_files = self._load(update_path=False)
        if len(stored_files) != len(self.files):
            # The number of items is different, things are new
            new_flag = True
        else:
            # The number of items is the same, check specifically for equality
            if stored_files.eq(self.files).all():
                new_flag = False
            else:
                # Stored and new data are not equal, there are new files
                new_flag = True

        if new_flag:
            if self.write_to_disk:
                # Save the previous data in a backup file
                prev_name = os.path.join(self.home_path, 'archive', stored_name)
                stored_files.to_csv(prev_name,
                                    date_format='%Y-%m-%d %H:%M:%S.%f',
                                    header=[self.data_path])

                # Overwrite the old reference file with the new file info
                self.files.to_csv(os.path.join(self.home_path, stored_name),
                                  date_format='%Y-%m-%d %H:%M:%S.%f',
                                  header=[self.data_path])
            else:
                # Update the hidden File attributes
                self._previous_file_list = stored_files
                self._current_file_list = self.files.copy()

        return

    def _load(self, prev_version=False, update_path=True):
        """Load stored filelist

        Parameters
        ----------
        prev_version : boolean
            if True, will load previous version of file list
        update_path : boolean
            If True, the path written to stored info will be
            assigned to self.data_path. (default=True)

        Returns
        -------
        pandas.Series
            File path names, indexed by datetime. Series is empty if no
            files are found.

        """

        fname = self.stored_file_name
        if prev_version:
            # Archived file list storage filename
            fname = os.path.join(self.home_path, 'archive', fname)
        else:
            # Current file list storage filename
            fname = os.path.join(self.home_path, fname)

        if os.path.isfile(fname) and (os.path.getsize(fname) > 0):
            if self.write_to_disk:
                # Load data stored on the local drive.
                loaded = pds.read_csv(fname, index_col=0, parse_dates=True,
                                      squeeze=True, header=0)
                if update_path:
                    # Store the data_path from the .csv onto Files
                    self.data_path = loaded.name

                # Ensure the name of returned Series is None for consistency
                loaded.name = None

                return loaded
            else:
                # Grab content from memory rather than local disk.
                if prev_version:
                    return self._previous_file_list
                else:
                    return self._current_file_list
        else:
            # Storage file not present.
            return pds.Series([], dtype='a')

    def _remove_data_dir_path(self, file_series=None):
        """Remove the data directory path from filenames

        Parameters
        ----------
        file_series : pds.Series or NoneType
            Series of filenames (potentially with file paths)
            (default=None)

        Returns
        -------
        pds.series or None
            If `file_series` is a Series, removes the data path from the
            filename, if present.  Returns None if `path_input` is None.

        """
        out = None
        if file_series is not None:
            # Ensure there is a directory divider at the end of the path
            split_str = os.path.join(self.data_path, '')

            # Remove the data path from all filenames in the Series
            out = file_series.apply(lambda x: x.split(split_str)[-1])

        return out

    # -----------------------------------------------------------------------
    # Define the public methods and properties

    def refresh(self):
        """Update list of files, if there are changes.

        Note
        ----
        Calls underlying list_files_rtn for the particular science instrument.
        Typically, these routines search in the pysat provided path,
        pysat_data_dir/platform/name/tag/, where pysat_data_dir is set by
        pysat.utils.set_data_dir(path=path).

        """

        # Let interested users know pysat is searching for
        info_str = '{platform} {name} {tag} {inst_id}'.format(
            **self.inst_info)
        info_str = " ".join(("pysat is searching for", info_str, "files."))
        info_str = " ".join(info_str.split())  # Remove duplicate whitespace
        logger.info(info_str)

        # Check all potential directory locations for files.
        # Stop as soon as we find some.
        for path in self.data_paths:
            new_files = self.list_files_rtn(tag=self.inst_info['tag'],
                                            inst_id=self.inst_info['inst_id'],
                                            data_path=path,
                                            format_str=self.file_format)

            # Check if list_files_rtn is actually returning filename or a
            # dict to be passed to filename creator function.
            if isinstance(new_files, dict):
                self.list_files_creator = partial(general.filename_creator,
                                                  **new_files)

                # Instrument iteration methods require a date range.
                self.start_date = filter_datetime_input(new_files['start_date'])
                self.stop_date = filter_datetime_input(new_files['stop_date'])

                # To really support iteration, we may need to create a generator
                # function that'll create a fake list of files as needed.
                # It would have to function in place of self.files. Is
                # there truly a point to this?
                return

            # Ensure the name of returned Series is None for consistency
            new_files.name = None

            # If we find some files, this is the one directory we store.
            # If I don't remove the directory paths then loading by filename
            # becomes more of a challenge. Plus, more memory to store, more
            # difficult for a human to parse when browsing a list, etc. The
            # approach here provides for most of the potential functionality
            # of multiple directories while still leaving the 'single' directory
            # focus and features of the original pysat intact.
            if not new_files.empty:
                self.data_path = path
                new_files = self._remove_data_dir_path(new_files)
                break

        # Feedback to info on number of files located
        logger.info('Found {:d} local files.'.format(len(new_files)))

        if not new_files.empty:
            # Sort files to ensure they are in order
            new_files = new_files.sort_index()
        elif pysat.params['warn_empty_file_list']:
            # Warn user if no files found, if pysat.param set
            pstrs = "\n".join(self.data_paths)
            estr = "".join(("Unable to find any files that match the supplied ",
                            "template: ", self.file_format, "\n",
                            "In the following directories: \n", pstrs))
            logger.warning(estr)

        # Attach Series of files to the class object
        self._attach_files(new_files)

        # Store to disk, if enabled for this class
        self._store()
        return

    def set_top_level_directory(self, path):
        """Sets top-level data directory.

        Sets a valid self.data_path using provided top-level directory
        path and the associated pysat subdirectories derived from the
        directory_format attribute as stored in self.sub_dir_path.

        Parameters
        ----------
        path : str
            Top-level path to use when looking for files. Must be in
            pysat.params['data_dirs']

        Note
        ----
        If there are Instrument files on the system under a top-level
        directory other than `path`, then, under certain conditions,
        self.data_path may be later updated by the object to point back
        to the directory with files.

        """

        if path not in pysat.params['data_dirs']:
            estr = "Supplied path not in `pysat.params['data_dirs']`"
            raise ValueError(estr)
        else:
            self.data_path = os.path.join(path, self.sub_dir_path)

        return

    def get_new(self):
        """List new files since last recorded file state.

        Returns
        -------
        pandas.Series
           A datetime-index Series of all new fileanmes since the last known
           change to the files.

        Note
        ----
        pysat stores filenames in the user_home/.pysat directory. Filenames are
        stored if there is a change and either update_files is True at
        instrument object level or files.refresh() is called.

        """

        # Refresh file series
        self.refresh()

        # Load current and previous set of files
        new_file_series = self._load(update_path=False)
        old_file_series = self._load(prev_version=True, update_path=False)

        # Select files that are in the new series and not the old series
        new_files = new_file_series[-new_file_series.isin(old_file_series)]

        return new_files

    def get_index(self, fname):
        """Return index for a given filename.

        Parameters
        ----------
        fname : string
            Filename for the desired time index

        Note
        ----
        If fname not found in the file information already attached
        to the instrument.files instance, then a files.refresh() call
        is made.

        """

        idx, = np.where(fname == self.files)
        if len(idx) == 0:
            # Filename not in index, try reloading files from disk
            self.refresh()
            idx, = np.where(fname == np.array(self.files))

            if len(idx) == 0:
                raise ValueError(' '.join(('Could not find "{:}"'.format(fname),
                                           'in available file list. Valid',
                                           'Example:', self.files.iloc[0])))

        # Return a scalar rather than array - otherwise introduces array to
        # index warnings.
        return idx[0]

    def get_file_array(self, start, stop):
        """Return a list of filenames between and including start and stop.

        Parameters
        ----------
        start: array_like or single string
            filenames for start of returned filelist
        stop: array_like or single string
            filenames inclusive of the ending of list provided by the stop time

        Returns
        -------
        files : list
            A list of filenames between and including start and stop times
            over all intervals.

        Note
        ----
        `start` and `stop` must be of the same type: both array-like or both
        strings

        """

        starts = np.asarray(start)
        if starts.shape == ():
            starts = [starts.tolist()]
        elif starts.shape[0] > 1:
            starts = starts.squeeze().tolist()
        elif starts.shape[0] == 1:
            starts = starts.tolist()

        stops = np.asarray(stop)
        if stops.shape == ():
            stops = [stops.tolist()]
        elif stops.shape[0] > 1:
            stops = stops.squeeze().tolist()
        elif stops.shape[0] == 1:
            stops = stops.tolist()

        # Selection is treated differently if start/stop are iterable or not
        files = []
        for (sta, stp) in zip(starts, stops):
            id1 = self.get_index(sta)
            id2 = self.get_index(stp)
            files.extend(self.files.iloc[id1:(id2 + 1)])

        return files

    @classmethod
    def from_os(cls, data_path=None, format_str=None,
                two_digit_year_break=None, delimiter=None):
        """
        Produces a list of files and and formats it for Files class.

        Parameters
        ----------
        data_path : string
            Top level directory to search files for. This directory
            is provided by pysat to the instrument_module.list_files
            functions as data_path.
        format_str : string with python format codes
            Provides the naming pattern of the instrument files and the
            locations of date information so an ordered list may be produced.
            Supports 'year', 'month', 'day', 'hour', 'minute', 'second',
            'version', 'revision', and 'cycle'
            Ex: 'cnofs_cindi_ivm_500ms_{year:4d}{month:02d}{day:02d}_v01.cdf'
        two_digit_year_break : int or None
            If filenames only store two digits for the year, then
            '1900' will be added for years >= two_digit_year_break
            and '2000' will be added for years < two_digit_year_break.
            If None, then four-digit years are assumed. (default=None)
        delimiter : string or NoneType
            Delimiter string upon which files will be split (e.g., '.'). If
            None, filenames will be parsed presuming a fixed width format.
            (default=None)

        Returns
        -------
        pds.Series
            A Series of filenames indexed by time. See
            `pysat.utils.files.process_parsed_filenames` for details.

        Note
        ----
        Requires fixed_width or delimited filename

        Does not produce a Files instance, but the proper output from
        instrument_module.list_files method.

        The '?' may be used to indicate a set number of spaces for a variable
        part of the name that need not be extracted.
        'cnofs_cindi_ivm_500ms_{year:4d}{month:02d}{day:02d}_v??.cdf'

        """

        if data_path is None:
            raise ValueError(" ".join(("Must supply instrument directory path",
                                       "(dir_path)")))

        # Parse format string to figure out which search string should be used
        # to identify files in the filesystem. Different option required if
        # filename is delimited
        wildcard = False if delimiter is None else True
        search_dict = futils.construct_searchstring_from_format(
            format_str, wildcard=wildcard)
        search_str = search_dict['search_string']

        # Perform the local file search
        files = futils.search_local_system_formatted_filename(data_path,
                                                              search_str)

        # Use the file list to extract the information. Pull data from the
        # areas identified by format_str
        if delimiter is None:
            stored = futils.parse_fixed_width_filenames(files, format_str)
        else:
            stored = futils.parse_delimited_filenames(files, format_str,
                                                      delimiter)

        # Process the parsed filenames and return a properly formatted Series
        return futils.process_parsed_filenames(stored, two_digit_year_break)

# --------------------------------------------------------
#   Utilities supporting the Files Object (all deprecated)


def process_parsed_filenames(stored, two_digit_year_break=None):
    """Accepts dict with data parsed from filenames and creates
    a pandas Series object formatted for the Files class.

    .. deprecated:: 3.0.0
      This function will be removed in pysat 4.0.0, please use the version under
      pysat.utils.files

    Parameters
    ----------
    stored : orderedDict
        Dict produced by parse_fixed_width_filenames or
        parse_delimited_filenames
    two_digit_year_break : int
        If filenames only store two digits for the year, then
        '1900' will be added for years >= two_digit_year_break
        and '2000' will be added for years < two_digit_year_break.

    Returns
    -------
    pandas.Series
        Series, indexed by datetime, with file strings

    Note
    ----
    If two files have the same date and time information in the filename then
    the file with the higher version/revision/cycle is used. Series returned
    only has one file der datetime. Version is required for this filtering,
    revision and cycle are optional.

    """

    funcname = "process_parsed_filenames"
    warnings.warn(' '.join(["_files.{:s} is".format(funcname),
                            "deprecated and will be removed in a future",
                            "version. Please use",
                            "pysat.utils.files.{:s}.".format(funcname)]),
                  DeprecationWarning, stacklevel=2)

    return futils.process_parsed_filenames(stored, two_digit_year_break)


def parse_fixed_width_filenames(files, format_str):
    """Parses list of files, extracting data identified by format_str

    .. deprecated:: 3.0.0
      This function will be removed in pysat 4.0.0, please use the version under
      pysat.utils.files

    Parameters
    ----------
    files : list
        List of files
    format_str : string with python format codes
        Provides the naming pattern of the instrument files and the
        locations of date information so an ordered list may be produced.
        Supports 'year', 'month', 'day', 'hour', 'minute', 'second', 'version',
        'revision', and 'cycle'
        Ex: 'instrument_{year:4d}{month:02d}{day:02d}_v{version:02d}.cdf'

    Returns
    -------
    OrderedDict
        Information parsed from filenames
        'year', 'month', 'day', 'hour', 'minute', 'second', 'version',
        'revision', 'cycle'
        'files' - input list of files

    """

    funcname = "parse_fixed_width_filenames"
    warnings.warn(' '.join(["_files.{:s} is".format(funcname),
                            "deprecated and will be removed in a future",
                            "version. Please use",
                            "pysat.utils.files.{:s}.".format(funcname)]),
                  DeprecationWarning, stacklevel=2)

    return futils.parse_fixed_width_filenames(files, format_str)


def parse_delimited_filenames(files, format_str, delimiter):
    """Parses list of files, extracting data identified by format_str

    .. deprecated:: 3.0.0
      This function will be removed in pysat 4.0.0, please use the version under
      pysat.utils.files

    Parameters
    ----------
    files : list
        List of files
    format_str : string with python format codes
        Provides the naming pattern of the instrument files and the
        locations of date information so an ordered list may be produced.
        Supports 'year', 'month', 'day', 'hour', 'minute', 'second', 'version',
        'revision', 'cycle'
        Ex: 'instrument_{year:4d}{month:02d}{day:02d}_v{version:02d}.cdf'
    delimiter : string
        Delimiter string upon which files will be split (e.g., '.')

    Returns
    -------
    OrderedDict
        Information parsed from filenames
        'year', 'month', 'day', 'hour', 'minute', 'second', 'version',
        'revision', 'cycle'
        'files' - input list of files
        'format_str' - formatted string from input

    """

    funcname = "parse_delimited_filenames"
    warnings.warn(' '.join(["_files.{:s} is".format(funcname),
                            "deprecated and will be removed in a future",
                            "version. Please use",
                            "pysat.utils.files.{:s}.".format(funcname)]),
                  DeprecationWarning, stacklevel=2)

    return futils.parse_delimited_filenames(files, format_str, delimiter)


def construct_searchstring_from_format(format_str, wildcard=False):
    """
    Parses format file string and returns string formatted for searching.

    .. deprecated:: 3.0.0
      This function will be removed in pysat 4.0.0, please use the version under
      pysat.utils.files

    Parameters
    ----------
    format_str : string with python format codes
        Provides the naming pattern of the instrument files and the
        locations of date information so an ordered list may be produced.
        Supports 'year', 'month', 'day', 'hour', 'minute', 'second', 'version',
        'revision', and 'cycle'
        Ex: 'cnofs_vefi_bfield_1sec_{year:04d}{month:02d}{day:02d}_v05.cdf'
    wildcard : bool
        if True, replaces the ? sequence with a * . This option may be well
        suited when dealing with delimited filenames.

    Returns
    -------
    dict
        'search_string' format_str with data to be parsed replaced with ?
        'keys' keys for data to be parsed
        'lengths' string length for data to be parsed
        'string_blocks' the filenames are broken down into fixed width
            segments and '' strings are placed in locations where data will
            eventually be parsed from a list of filenames. A standards
            compliant filename can be constructed by starting with
            string_blocks, adding keys in order, and replacing the '' locations
            with data of length length.

    Note
    ----
    The '?' may be used to indicate a set number of spaces for a variable
    part of the name that need not be extracted.
    'cnofs_cindi_ivm_500ms_{year:4d}{month:02d}{day:02d}_v??.cdf'

    """

    funcname = "construct_searchstring_from_format"
    warnings.warn(' '.join(["_files.{:s} is".format(funcname),
                            "deprecated and will be removed in a future",
                            "version. Please use",
                            "pysat.utils.files.{:s}.".format(funcname)]),
                  DeprecationWarning, stacklevel=2)

    return futils.construct_searchstring_from_format(format_str, wildcard)


def search_local_system_formatted_filename(data_path, search_str):
    """
    Parses format file string and returns string formatted for searching.

    .. deprecated:: 3.0.0
      This function will be removed in pysat 4.0.0, please use the version under
      pysat.utils.files

    Parameters
    ----------
    data_path : string
        Top level directory to search files for. This directory
        is provided by pysat to the instrument_module.list_files
        functions as data_path.
    search_str : string
        String to search local file system for
        Ex: 'cnofs_cindi_ivm_500ms_????????_v??.cdf'
            'cnofs_cinfi_ivm_500ms_*_v??.cdf'

    Returns
    -------
    list
        list of files matching the format_str

    Note
    ----
    The use of ?s (1 ? per character) rather than the full wildcard *
    provides a more specific filename search string that limits the
    false positive rate.

    """

    funcname = "search_local_system_formatted_filename"
    warnings.warn(' '.join(["_files.{:s} is".format(funcname),
                            "deprecated and will be removed in a future",
                            "version. Please use",
                            "pysat.utils.files.{:s}.".format(funcname)]),
                  DeprecationWarning, stacklevel=2)

    return futils.search_local_system_formatted_filename(data_path, search_str)
