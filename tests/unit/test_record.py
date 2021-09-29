from __future__ import with_statement
from __future__ import absolute_import
import unittest
from fmrest.record import Record

class RecordTestCase(unittest.TestCase):
    u"""Record test suite"""
    def setUp(self):
        pass

    def test_key_value_mismatch_handling(self):
        u"""Test that Record cannot be initialized with a key-value length mismatch."""
        with self.assertRaises(ValueError):
            Record([u'key1', u'key2'], [1])

        with self.assertRaises(ValueError):
            Record([u'key1'], [1, 2])

    def test_key_access(self):
        u"""Test that Record keys and values can be accessed."""
        assert_name = u'David'
        assert_drink = u'Coffee'

        record = Record([u'name', u'drink'], [assert_name, assert_drink])

        self.assertEqual(record.keys(), [u'name', u'drink'])
        self.assertEqual(record.values(), [assert_name, assert_drink])
        
        self.assertEqual(record.name, assert_name)
        self.assertEqual(record[u'name'], assert_name)

        self.assertEqual(record.drink, assert_drink)
        self.assertEqual(record[u'drink'], assert_drink)

        with self.assertRaises(KeyError):
            record[u'city']

        with self.assertRaises(AttributeError):
            record.city

    def test_dirty_record_flagging(self):
        u"""Test that a record gets flagged as dirty when you change its value."""
        assert_name = u'David'
        assert_drink = u'Coffee'

        # setting the same value should not flag as dirty
        record = Record([u'name', u'drink'], [assert_name, assert_drink])
        record.name = u'David'
        self.assertFalse(record.is_dirty)

        # ... again for dict access
        record = Record([u'name', u'drink'], [assert_name, assert_drink])
        record[u'name'] = u'David'
        self.assertFalse(record.is_dirty)

        # now do change the value
        record = Record([u'name', u'drink'], [assert_name, assert_drink])
        record.name = u'Caspar'
        self.assertTrue(record.is_dirty)

        record = Record([u'name', u'drink'], [assert_name, assert_drink])
        record[u'name'] = u'Caspar'
        self.assertTrue(record.is_dirty)

    def test_key_error_on_invalid_keys(self):
        u"""Test that trying to set a non-existing key will raise an error."""
        record = Record([u'name'], [u'David'])

        with self.assertRaises(AttributeError):
            record.drink = u'Dr. Pepper'

        with self.assertRaises(KeyError):
            record[u'city'] = u'Hamburg'

    def test_setting_class_slots(self):
        u"""Test that slots can be set w/o being intercepted and written to the modification dict."""
        record = Record([u'name'], [u'David'])
        record._keys = [u'drink']

        self.assertIn(u'drink', record.keys())

    def test_modification_tracking(self):
        u"""Test that record modifications are tracked."""
        fake_modifications = {
            u'drink': u'Dr. Pepper',
            u'city': u'New York'
        }

        record = Record([u'name', u'drink', u'city'], [u'David', u'Coffee', u'Hamburg'])
        record.name = u'David' # should not be flagged as it is the same value
        record.drink = u'Dr. Pepper'
        record.city = u'New York'

        self.assertEqual(fake_modifications, record.modifications())

    def test_setting_portal_data_error(self):
        u"""Test that attempting to set portal data raises an error.
        Once supported, this test can be replaced by a test, that verifies portal data can be set.
        """
        record = Record([u'name', u'portal_notes'], [u'David', u'dummy'])

        with self.assertRaises(KeyError):
            record[u'portal_notes'] = 1234

    def test_dict_conversion(self):
        u"""Test that a record can be converted into a dict structure."""
        record = Record(
            [u'name', u'drink', u'city', u'recordId', u'modId', u'portal_notes', u'portal_addresses'],
            [u'David', u'Coffee', u'Hamburg', 1, 2, u'dummy', u'dummy2']
        )

        fake_dict = {
            u'name': u'David',
            u'drink': u'Coffee',
            u'city': u'Hamburg',
            u'recordId': 1,
            u'modId': 2,
            u'portal_notes': u'dummy',
            u'portal_addresses': u'dummy2'
        }

        self.assertEqual(record.to_dict(), fake_dict)

        # test without portals
        fake_dict.pop(u'portal_notes')
        fake_dict.pop(u'portal_addresses')
        self.assertEqual(record.to_dict(ignore_portals=True), fake_dict)

        # test without internal ids
        fake_dict.pop(u'recordId')
        fake_dict.pop(u'modId')
        self.assertEqual(record.to_dict(ignore_portals=True, ignore_internal_ids=True), fake_dict)

    def test_pop_values(self):
        u"""Test that we can pop values from the record."""

        record = Record([u'name', u'drink', u'city'], [u'David', u'Coffee', u'Hamburg'])

        self.assertEqual(record.pop(u'drink'), u'Coffee')
        self.assertEqual(record.keys(), [u'name', u'city'])
        self.assertEqual(record.values(), [u'David', u'Hamburg'])

        self.assertEqual(record.pop(u'not existing'), None)
