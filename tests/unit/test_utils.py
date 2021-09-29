from __future__ import absolute_import
import unittest
import datetime
from fmrest.utils import *

class UtilsTestCase(unittest.TestCase):
    u"""Utils test suite"""
    def setUp(self):
        pass

    def test_portal_params(self):
        u"""Test that portal param string is build correctly."""
        portals = [
            {
                u'name': u'Portal1',
                u'offset': 1,
                u'limit': 50
            },
            {
                u'name': u'Portal2',
                u'offset': 2,
                u'limit': 51
            }
        ]

        params = build_portal_params(portals, names_as_string=True)
        self.assertEqual(
            {u'portal': u'["Portal1", "Portal2"]',
             u'_offset.Portal1': 1,
             u'_limit.Portal1': 50,
             u'_offset.Portal2': 2,
             u'_limit.Portal2': 51},
            params)

        params = build_portal_params(portals)
        self.assertEqual(
            {u'portal': [u"Portal1", u"Portal2"],
             u'offset.Portal1': 1,
             u'limit.Portal1': 50,
             u'offset.Portal2': 2,
             u'limit.Portal2': 51},
            params)

    def test_build_script_params(self):
        u"""Test that simplified scripts object can be turned into FMSDAPI compatible one."""

        scripts_in = {
            u'prerequest': [u'script_prerequest', u'param_prerequest'],
            u'presort': [u'script_presort', u'param_presort'],
            u'after': [u'script_after', u'param_after']
        }

        scripts_out = {
            u'script.prerequest': u'script_prerequest',
            u'script.prerequest.param': u'param_prerequest',
            u'script.presort': u'script_presort',
            u'script.presort.param': u'param_presort',
            u'script': u'script_after',
            u'script.param': u'param_after'
        }

        self.assertEqual(
            build_script_params(scripts_in), scripts_out
        )

    def test_build_script_params_partial(self):
        u"""Test that only the script/param combos are returned that the user actually specified."""
        scripts_in = {u'after': [u'script_after', u'param_after']}
        scripts_out = {u'script': u'script_after', u'script.param': u'param_after'}

        self.assertEqual(build_script_params(scripts_in), scripts_out)

    def test_string_to_time_conversion(self):
        u"""Test that strings can be converted into their "guessed" original types."""

        self.assertEqual(
            convert_string_type(u'23:59:59'),
            datetime.timedelta(hours=23, minutes=59, seconds=59)
        )

        self.assertEqual(
            convert_string_type(u'48:61:01'),
            datetime.timedelta(days=2, hours=1, minutes=1, seconds=1)
        )

        self.assertEqual(
            convert_string_type(u'aa:bb:cc'),
            u'aa:bb:cc' #remains string
        )

    def test_string_to_datetime_conversion(self):
        u"""Test that strings can be converted into their "guessed" original types."""

        self.assertEqual(
            convert_string_type(u'12/24/2016'),
            datetime.datetime(2016, 12, 24)
        )

        self.assertEqual(
            convert_string_type(u'12/01/2017 20:45:30'),
            datetime.datetime(2017, 12, 1, 20, 45, 30)
        )

        self.assertEqual(
            convert_string_type(u'12/01/0001 20:45:30'),
            datetime.datetime(1, 12, 1, 20, 45, 30)
        )

    def test_string_to_number_conversion(self):
        u"""Test that strings can be converted into their "guessed" original types."""

        self.assertIsInstance(
            convert_string_type(u'42'),
            int
        )

        self.assertIsInstance(
            convert_string_type(u'42.1'),
            float
        )

        self.assertIsInstance(
            convert_string_type(u'no. 42'),
            unicode
        )

    def test_filename_from_url(self):
        u"""Test that we can extract the file name from a FM RC URL."""

        # filename without extension
        filename = u'7124058BDBFC7C4BB82331184A3C72BC4EB0C449FCF35DBA295B3A448FD142EB'
        self.assertEqual(
            filename_from_url(
                u'https://10.211.55.15/Streaming_SSL/MainDB/'
                u'7124058BDBFC7C4BB82331184A3C72BC4EB0C449FCF35DBA295B3A448FD142EB'
                u'?RCType=EmbeddedRCFileProcessor'),
            filename)

        # filename with extension
        filename = u'6DE110C449E23F7C196F87CC062046A7BE48927BBEB90F5B0A4BFA809A249075.mp4'
        self.assertEqual(
            filename_from_url(
                u'https://10.211.55.15/Streaming_SSL/MainDB/'
                u'6DE110C449E23F7C196F87CC062046A7BE48927BBEB90F5B0A4BFA809A249075.mp4'
                u'?RCType=EmbeddedRCFileProcessor'),
            filename)
