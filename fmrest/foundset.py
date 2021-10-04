u"""Foundset class for collections of Records"""

from __future__ import absolute_import
import itertools
from .utils import cache_generator
from .record import Record

class Foundset(object):
    u"""A set of Record instances

    Foundsets are used for both find results and portal data (related records)
    """
    def __init__(self, records, info = {}):
        u"""Initialize the Foundset class.

        The foundset is cached while being consumed, so that subsequent iterations are possible.

        Parameters
        ----------
        records : generator
            Generator of Record instances representing the records in a foundset or
            related records from a portal.
        info : dictionary
            Dictionary of information about the foundset. This is 1:1 the dictionary that
            is delivered by FMS for any foundset.
        """
        self._records = records
        self._consumed = False
        self._info = info

        # We hold the list of cached values and the state of completion in a list
        # idea: https://codereview.stackexchange.com/a/178780/151724
        self._cache = [[], False]

        # cache_generator will yield the values and handle the caching
        self._iter = cache_generator(self._records, self._cache)

    def __iter__(self):
        u"""Make foundset iterable.

        Returns iter for list of records already consumed from generator, or a chained object
        of cache list plus still-to-consume records. This makes sure foundsets can be properly used
        as a list.
        """

        if self._cache[1]:
            # all values have been cached
            return iter(self._cache[0])

        return itertools.chain(self._cache[0], self._iter)

    def __getitem__(self, index):
        u"""Return item at index in the iterator. If it's already cached, then return cached version.
        Otherwise consume until found.

        Parameters
        ----------
        index : int
        """
        while index >= len(self._cache[0]):
            try:
                self._iter.next()
            except StopIteration:
                break

        return self._cache[0][index]

    def __repr__(self):
        return u'<Foundset consumed_records={} is_complete={}>'.format(
            len(self._cache[0]), self.is_complete
        )

    @property
    def is_complete(self):
        u"""Returns True if all values have been consumed. Otherwise False."""
        return self._cache[1]

    @property
    def info(self):
        u"""Returns data that is contained in the dataInfo section of the FMS response."""
        return self._info

    def to_df(self):
        u"""Returns a Pandas DataFrame of the Foundset. Must have Pandas installed.

        Note that portal data is not returned as part of the DataFrame.
        """
        try:
            import pandas as pd
        except ImportError, ex:
            raise Exception(
                u"You need to have Pandas installed to use this feature. "
                u"You can install it like this: 'pip install pandas'"
            )

        return pd.DataFrame(
            [r.to_dict(ignore_portals=True) for r in self]
        )
