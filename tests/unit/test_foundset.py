from __future__ import with_statement
from __future__ import absolute_import
import unittest
from fmrest.foundset import Foundset
from fmrest.record import Record
from itertools import izip

class FoundsetTestCase(unittest.TestCase):
    u"""Foundset test suite"""
    def setUp(self):
        pass

    def test_index_access(self):
        u"""Test that values in generator are accesible via their index. Values are cached,
        so we are actually testing that we can access the cached list."""
        sample_gen = (record for record in [
            Record([u'name', u'recordId'], [u'john doe', 1], True),
            Record([u'name', u'recordId'], [u'john smith', 2], True),
            Record([u'name', u'recordId'], [u'john wayne', 3], True)
        ])
        foundset = Foundset(sample_gen)

        self.assertEqual(foundset[1].name, u'john smith')

        # Accessing an out of range index of cached values should raise IndexError
        with self.assertRaises(IndexError):
            foundset[3]

    def test_list_builduing(self):
        u"""Test that building a list works with generated and cached values"""

        sample_gen = Foundset(i for i in [1, 2, 4, 5, 6, 7, 8])
        self.assertEqual(list(izip(sample_gen, sample_gen)), list(izip(sample_gen, sample_gen)))

    def test_info(self):
        u"""Test that info section is available."""
        info = {u'portalObjectName': u'sample', u'database': u'DB', u'table': u'Sample', u'foundCount': 69, u'returnedCount': 50}
        sample_gen = Foundset((i for i in [1, 2]), info)
        self.assertEqual(sample_gen.info, info)

    def test_empty_info(self):
        u"""Test that a foundset without 'dataInfo' section returns an empty info dictionary"""

        sample_gen = Foundset(i for i in [1, 2])
        self.assertEqual(sample_gen.info, {})
