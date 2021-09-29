u"""Server test suite"""
from __future__ import with_statement
from __future__ import absolute_import
import os
import unittest
import requests
import fmrest
import json
from fmrest.record import Record
from fmrest.const import FMSErrorCode
from fmrest.exceptions import RecordError, FileMakerError

# Settings for fmrest test database 'Contacts'
# Running theses tests requires you to have a FileMaker Server running
# (if you want to change credentials when hosting the test db, please use the env vars to do so)
URL = os.getenv(u'URL', u'https://macvm2.local')
ACCOUNT_NAME = os.getenv(u'ACCOUNT_NAME', u'admin')
ACCOUNT_PASS = os.getenv(u'ACCOUNT_PASS', u'admin')
DATABASE = os.getenv(u'DATABASE', u'Contacts')
LAYOUT = os.getenv(u'LAYOUT', u'Contacts')
VERIFY_SSL = os.getenv(u'VERIFY_SSL', os.path.dirname(os.path.realpath(__file__)) + u'/CA.pem')
AUTO_RELOGIN = False

SECOND_DS = os.getenv(u'SECOND_DS', u'secondDataSource')
SECOND_DS_ACCOUNT_NAME = os.getenv(u'SECOND_DS_ACCOUNT_NAME', u'admin2')
SECOND_DS_ACCOUNT_PASS = os.getenv(u'SECOND_DS_ACCOUNT_PASS', u'admin2')

class ServerTestCase(unittest.TestCase):
    u"""Server test suite"""
    def setUp(self):

        # disable urlib warnings as we are testing with non verified certs
        requests.packages.urllib3.disable_warnings()

        self._fms = fmrest.Server(url=URL,
                                  user=ACCOUNT_NAME,
                                  password=ACCOUNT_PASS,
                                  database=DATABASE,
                                  layout=LAYOUT,
                                  verify_ssl=VERIFY_SSL,
                                  auto_relogin=AUTO_RELOGIN
                                 )
    def test_login(self):
        u"""Test that login returns string token on success."""
        with self._fms as server:
            self.assertIsInstance(server.login(), unicode)

    def test_login_data_sources(self):
        u"""Test login with second data source."""
        fms = fmrest.Server(url=URL,
                            user=ACCOUNT_NAME,
                            password=ACCOUNT_PASS,
                            database=DATABASE,
                            layout=LAYOUT,
                            verify_ssl=VERIFY_SSL,
                            data_sources=[
                                {u'database': SECOND_DS,
                                 u'username': SECOND_DS_ACCOUNT_NAME,
                                 u'password': SECOND_DS_ACCOUNT_PASS}
                            ]
                           )
        with fms as server:
            server.login()
            record = server.get_record(1, portals=[{u'name': u'secondDataSource'}])
            # read test value from second data source
            self.assertEqual(record.portal_secondDataSource[0][u'secondDataSource::id'], 1)

    def test_logout(self):
        u"""Test that server accepts logout request."""
        self._fms.login()
        self.assertTrue(self._fms.logout())

    def test_create_get_delete_record(self):
        u"""Create a record, get it, delete it. Assert all steps work in succession."""
        with self._fms as server:
            server.login()

            #create a test record and get its ID
            record_id = server.create_record({u'name': u'FileMaker サーバ', u'date': u'04.11.2017'})
            self.assertIsInstance(record_id, int)

            #read the new record and compare the written value
            record = server.get_record(record_id)
            self.assertEqual(record.record_id, record_id)
            self.assertEqual(record.name, u'FileMaker サーバ')

            #delete record by the ID
            deleted = server.delete_record(record_id)
            self.assertTrue(deleted)

    def test_create_record_from_record_instance(self):
        u"""Create a record from a new record instance."""

        record = Record([u'name', u'drink'], [u'David', u'Coffee'])

        with self._fms as server:
            server.login()
            record_id = server.create(record)

        self.assertIsInstance(record_id, int)

    def test_info(self):
        u"""Test that foundset info property contains data as expected.

        The executed script computes the expected information independently and is used to
        make a comparision against the data computed by the FMDAPI"""
        with self._fms as server:
            server.login()
            foundset = server.find(query=[{u'id': 1}], scripts={u'after': [u'testScript_dataInfo', None]})
            expected_info = json.loads(server.last_script_result[u'after'][1])

        self.assertDictEqual(foundset.info, expected_info[u'general'])
        self.assertDictEqual(foundset[0].portal_notes.info, expected_info[u'portal_notes'])

    def test_get_records(self):
        # TODO
        pass

    def test_find(self):
        # TODO
        pass

    def test_edit_record(self):
        # TODO
        pass

    def test_perform_script_single(self):
        u"""Perform script via dedicated script route introduced in FMS18"""
        param = u'input'
        expected_script_result = u'Output with param ' + param
        expected_return = (0, expected_script_result)

        with self._fms as server:
            server.login()
            ps_res = server.perform_script(u'testScript', param)
            ps_last_result = server.last_script_result

        self.assertEqual(ps_res, expected_return)

        # also check that last_script_result was updated
        self.assertEqual(ps_last_result, {u'after': [0, expected_script_result]})

    def test_perform_script_single_with_error(self):
        u"""Perform script w/ error via dedicated script route introduced in FMS18"""
        expected_return = (3, None)

        with self._fms as server:
            server.login()
            ps_res = server.perform_script(u'testScriptWithError')
            ps_last_result = server.last_script_result

        self.assertEqual(ps_res, expected_return)

        # also check that last_script_result was updated
        self.assertEqual(ps_last_result, {u'after': [3, None]})

    def test_perform_scripts_with_find(self):
        u"""Perform scripts for find route and verify results."""
        expected_script_result = {
            u'prerequest': [0, u'Output prerequest with param for prerequest'],
            u'presort': [0, u'Output presort with param for presort'],
            u'after': [0, u'Output with param for after'],
        }
        with self._fms as server:
            server.login()
            server.find(
                query=[{u'id': u'1'}],
                scripts={
                    u'prerequest': [u'testScript_prerequest', u'for prerequest'],
                    u'presort': [u'testScript_presort', u'for presort'],
                    u'after': [u'testScript', u'for after'],
                })

            self.assertEqual(server.last_script_result, expected_script_result)

    def test_perform_script_find_with_error(self):
        u"""Perform a script via find route that contains an error and check if error is returned."""
        expected_script_result = {u'after': [3, None]} # unsupported script step

        with self._fms as server:
            server.login()
            server.find(
                query=[{u'id': u'1'}],
                scripts={u'after': [u'testScriptWithError', None]})

            self.assertEqual(server.last_script_result, expected_script_result)

    def test_delete_record_instance(self):
        with self._fms as server:
            server.login()

            # create dummy record
            record = Record([u'name'], [u'David'])
            new_record_id = server.create(record)

            # "hand-made" record not fetched from server should fail for deletion
            with self.assertRaises(RecordError):
                server.delete(record)

            # fetch record from server so that we have a valid record instance
            record = server.get_record(new_record_id)

            # test deletion
            deletion_result = server.delete(record)
            self.assertTrue(deletion_result)

    def test_duplicate_by_get_create(self):
        u"""Test that we can pass a record instance from get_record directly to create().

        Note that this might not be a practical application in real life, as duplicating
        a record like this will only work if you have no ID fields, calc fields, etc. in your
        record instance.
        """

        with self._fms as server:
            server.layout = u'Planets' # different test layout with no IDs / calcs
            server.login()
            record = server.get_record(5)

            # duplicate record by passing rec instance to create method
            duplicated_record_id = server.create(record)
            self.assertIsInstance(duplicated_record_id, int)

            # delete test record
            server.delete_record(duplicated_record_id)

    def test_set_globals_to_access_related_values(self):
        u"""Test that we can set a global value in the current session and then
        use it to access a related value
        """

        with self._fms as server:
            server.login()

            # give the global field the value of an existing note record
            globals_ = {u'Contacts::g_note_id_active': u'1'}
            set_globals = server.set_globals(globals_)
            self.assertTrue(set_globals)

            # now request a record and check that the relationship using this global
            # field can be established.
            record = server.get_record(497) # can be any, as we use a global relationship
            self.assertEqual(
                record[u'Notes_active::note'], u'This is a test note. Do not delete or change.'
            )

    def test_get_record(self):
        u"""Test that get_record returns the Record value we are expecting."""
        with self._fms as server:
            server.login()
            fake_record = Record([u'name', u'drink'], [u'Do not delete record 1', u'Coffee'])
            record = server.get_record(1)
            self.assertEqual(fake_record.name, record.name)
            self.assertEqual(fake_record.drink, record.drink)

    def test_upload_container(self):
        u"""Test that uploading container data works without errors."""
        with self._fms as server:
            server.login()

            response = server.upload_container(
                1, u'portrait', (u'sample.csv', u'col1,col2,col3,col4\nwhat,is,going,on\n')
            )

            self.assertTrue(response)

    def test_auto_relogin_off(self):
        u"""Call get_record with an invalid token and test if token refresh
        is not (!) performed when auto_relogin is off.
        """
        self._fms.login()
        self._fms.auto_relogin = False
        self._fms._token = u'invalid token'
        with self.assertRaises(FileMakerError):
            self._fms.get_record(1)
        self.assertEqual(self._fms.last_error,
                         FMSErrorCode.INVALID_DAPI_TOKEN.value)

        self._fms.auto_relogin = AUTO_RELOGIN  # reset

    def test_auto_relogin_on(self):
        u"""Call get_record with an invalid token and test if token refresh is
        performed.
        """
        fake_token = u'invalid token'
        self._fms.login()
        self._fms.auto_relogin = True
        self._fms._token = fake_token
        try:
            self._fms.get_record(1)
        except FileMakerError, exc:
            self.fail(f'FileMakerError despite relogin; {exc}')

        self.assertEqual(self._fms.last_error, FMSErrorCode.SUCCESS.value)
        self.assertNotEqual(self._fms._token, fake_token)

        self._fms.auto_relogin = AUTO_RELOGIN  # reset

    def test_auto_relogin_on_and_fail(self):
        u"""Call get_record with an invalid token and test if token refresh is
        attempted and if potential error in the login will bubble up
        correctly.
        """
        fake_token = u'invalid token'
        self._fms.login()
        self._fms.auto_relogin = True
        self._fms._token = fake_token
        self._fms.user = u'fake'  # make the relogin fail
        with self.assertRaises(FileMakerError):
            self._fms.get_record(1)

        self.assertEqual(self._fms.last_error,
                         FMSErrorCode.INVALID_USER_PASSWORD.value)

        self._fms.auto_relogin = AUTO_RELOGIN  # reset

    def test_auto_relogin_on_and_fail_in_original(self):
        u"""Call get_record with an invalid token and test if token refresh is
        attempted and if potential error in repeated original call bubbles
        up correctly.
        """
        fake_token = u'invalid token'
        self._fms.login()
        self._fms.auto_relogin = True
        self._fms._token = fake_token
        with self.assertRaises(FileMakerError):
            self._fms.get_record(10000)

        self.assertEqual(self._fms.last_error,
                         FMSErrorCode.RECORD_MISSING.value)

        self._fms.auto_relogin = AUTO_RELOGIN  # reset
