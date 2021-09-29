u"""Server class for API connections"""
from __future__ import absolute_import
import json
import warnings
from typing import (List, Dict, Optional, Any, IO, Tuple, Union, Iterator,
                    Callable)
from functools import wraps
import requests
from .utils import request, build_portal_params, build_script_params, filename_from_url
from .const import API_PATH, PORTAL_PREFIX, FMSErrorCode
from .exceptions import BadJSON, FileMakerError, RecordError
from .record import Record
from .foundset import Foundset

class Server(object):
    u"""The server class provides easy access to the FileMaker Data API

    Get an instance of this class, login, get a record, logout:

        import fmrest
        fms = fmrest.Server('https://server-address.com',
                    user='db user name',
                    password='db password',
                    database='db name',
                    layout='db layout'
                   )
        fms.login()
        fms.get_record(1)
        fms.logout()

    Or use as with statement, logging out automatically:

        with fms as my_server:
            my_server.login()
            # do stuff
    """

    def __init__(self, url, user,
                 password, database, layout,
                 data_sources = None,
                 verify_ssl = True,
                 type_conversion = False,
                 auto_relogin = False,
                 proxies = None):
        u"""Initialize the Server class.

        Parameters
        ----------
        url : str
            Address of the FileMaker Server, e.g. https://my-server.com or https://127.0.0.1
            Note: Data API must use https.
        user : str
            Username to log into your database
            Note: make sure it belongs to a privilege set that has fmrest extended privileges.
        password : str
            Password to log into your database
        database : str
            Name of database without extension, e.g. Contacts
        layout : str
            Layout to work with. Can be changed between calls by setting the layout attribute again,
            e.g.: fmrest_instance.layout = 'new_layout'.
        data_sources : list, optional
            List of dicts in formatj
                [{'database': 'db_file', 'username': 'admin', 'password': 'admin'}]
            Use this if for your actions you need to be authenticated to multiple DB files.
        verify_ssl : bool or str, optional
            Switch to set if certificate should be verified.
            Use False to disable verification. Default True.
            Use string path to a root cert pem file, if you work with a custom CA.
        type_conversion : bool, optional
            If True, attempt to convert string values into their potential original types.
            In previous versions of the FileMaker Data API only strings were returned and there was
            no way of knowing the correct type of a requested field value.

            Be cautious with this parameter, as results may be different from what you expect!

            Values will be converted into int, float, datetime, timedelta, string. This happens
            on a record level, not on a foundset level.
        auto_relogin : bool, optional
            If True, tries to automatically get a new token (re-login) when a
            request comes back with a 952 (invalid token) error. Defaults to
            False.
        proxies : dict, optional
            Pass requests through a proxy, configure like so:
            { 'https': 'http://127.0.0.1:8080' }
        """

        self.url = url
        self.user = user
        self.password = password
        self.database = database
        self.layout = layout
        self.data_sources = [] if data_sources is None else data_sources
        self.verify_ssl = verify_ssl
        self.auto_relogin = auto_relogin
        self.proxies = proxies

        self.type_conversion = type_conversion

        if url[:5] != u'https':
            raise ValueError(u'Please make sure to use https, otherwise calls to the Data '
                             u'API will not work.')

        self._token = None
        self._last_fm_error = None
        self._last_script_result = None
        self._headers = {}
        self._set_content_type()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_traceback):
        self.logout()

    def __repr__(self):
        return u'<Server logged_in={} database={} layout={}>'.format(
            bool(self._token), self.database, self.layout
        )

    def _with_auto_relogin(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            if not self.auto_relogin:
                return f(self, *args, **kwargs)

            try:
                return f(self, *args, **kwargs)
            except FileMakerError:
                if self.last_error == FMSErrorCode.INVALID_DAPI_TOKEN.value:
                    # got invalid token error; try to get a new token
                    self._token = None
                    self.login()
                    # ... now perform original request again
                    return f(self, *args, **kwargs)
                raise  # if another error occurred, re-raise the exception
        return wrapper

    def login(self):
        u"""Logs into FMServer and returns access token.

        Authentication happens via HTTP Basic Auth. Subsequent calls to the API will then use
        the return session token.

        Note that OAuth is currently not supported.
        """

        path = API_PATH[u'auth'].format(database=self.database, token=u'')
        data = {u'fmDataSource': self.data_sources}

        response = self._call_filemaker(u'POST', path, data, auth=(self.user, self.password))
        self._token = response.get(u'token', None)

        return self._token

    def logout(self):
        u"""Logs out of current session. Returns True if successful.

        Note: this method is also called by __exit__
        """

	# token is expected in endpoint for logout
        path = API_PATH[u'auth'].format(database=self.database, token=self._token)

	# remove token, so that the Authorization header is not sent for logout
	# (_call_filemaker() will update the headers)
        self._token = u''
        self._call_filemaker(u'DELETE', path)

        return self.last_error == FMSErrorCode.SUCCESS.value

    def create(self, record):
        u"""Shortcut to create_record method. Takes record instance and calls create_record."""
        # TODO: support for handling foundset instances inside record instance
        return self.create_record(record.to_dict(ignore_portals=True, ignore_internal_ids=True))

    @_with_auto_relogin
    def create_record(self, field_data,
                      portals = None,
                      scripts = None):
        u"""Creates a new record with given field data and returns new internal record id.

        Parameters
        -----------
        field_data : dict
            Dict of field names as defined in FileMaker: E.g.: {'name': 'David', 'drink': 'Coffee'}
        scripts : dict, optional
            Specify which scripts should run when with which parameters
            Example: {'prerequest': ['my_script', 'my_param']}
            Allowed types: 'prerequest', 'presort', 'after'
            List should have length of 2 (both script name and parameter are required.)
        portals : dict
            Specify the records that should be created via a portal (must allow creation of records)
            Example: {'my_portal': [
                {'TO::field': 'hello', 'TO::field2': 'world'},
                {'TO::field': 'another record'}
            ]
        """
        path = API_PATH[u'record'].format(
            database=self.database,
            layout=self.layout,
        )

        request_data = {u'fieldData': field_data}
        if portals:
            request_data[u'portalData'] = portals

        # build script param object in FMSDAPI style
        script_params = build_script_params(scripts) if scripts else None
        if script_params:
            request_data.update(script_params)

        response = self._call_filemaker(u'POST', path, request_data)
        record_id = response.get(u'recordId')

        return int(record_id) if record_id else None

    def edit(self, record, validate_mod_id = False):
        u"""Shortcut to edit_record method. Takes (modified) record instance and calls edit_record"""
        mod_id = record.modification_id if validate_mod_id else None
        return self.edit_record(record.record_id, record.modifications(), mod_id)

    @_with_auto_relogin
    def edit_record(self, record_id, field_data,
                    mod_id = None, portals = None,
                    scripts = None):
        u"""Edits the record with the given record_id and field_data. Return True on success.

        Parameters
        -----------
        record_id : int
            FileMaker's internal record id.
        field_data: dict
            Dict of field names as defined in FileMaker: E.g.: {'name': 'David', 'drink': 'Coffee'}

            To delete related records, use {'deleteRelated': 'Orders.2'}, where 2 is the record id
            of the related record.
        mod_id: int, optional
            Pass a modification id to only edit the record when mod_id matches the current mod_id of
            the server. This is only supported for records in the current table, not related
            records.
        portals : dict
            Specify the records that should be edited via a portal.
            If recordId is not specified, a new record will be created.
            Example: {'my_portal': [
                {'TO::field': 'hello', 'recordId': '42'}
            ]
        scripts : dict, optional
            Specify which scripts should run when with which parameters
            Example: {'prerequest': ['my_script', 'my_param']}
            Allowed types: 'prerequest', 'presort', 'after'
            List should have length of 2 (both script name and parameter are required.)
        """
        path = API_PATH[u'record_action'].format(
            database=self.database,
            layout=self.layout,
            record_id=record_id
        )

        request_data = {u'fieldData': field_data}
        if mod_id:
            request_data[u'modId'] = unicode(mod_id)

        if portals:
            request_data[u'portalData'] = portals

        # build script param object in FMSDAPI style
        script_params = build_script_params(scripts) if scripts else None
        if script_params:
            request_data.update(script_params)

        self._call_filemaker(u'PATCH', path, request_data)

        return self.last_error == FMSErrorCode.SUCCESS.value

    def delete(self, record):
        u"""Shortcut to delete_record method. Takes record instance and calls delete_record."""
        try:
            record_id = record.record_id
        except AttributeError:
            raise RecordError(u'Not a valid record instance. record_id is missing.')

        return self.delete_record(record_id)

    @_with_auto_relogin
    def delete_record(self, record_id, scripts = None):
        u"""Deletes a record for the given record_id. Returns True on success.

        Parameters
        -----------
        record_id : int
            FileMaker's internal record id.
        scripts : dict, optional
            Specify which scripts should run when with which parameters
            Example: {'prerequest': ['my_script', 'my_param']}
            Allowed types: 'prerequest', 'presort', 'after'
            List should have length of 2 (both script name and parameter are required.)
        """
        path = API_PATH[u'record_action'].format(
            database=self.database,
            layout=self.layout,
            record_id=record_id
        )

        params = build_script_params(scripts) if scripts else None

        self._call_filemaker(u'DELETE', path, params=params)

        return self.last_error == FMSErrorCode.SUCCESS.value

    @_with_auto_relogin
    def get_record(self, record_id, portals = None,
                   scripts = None,
                   layout = None):
        u"""Fetches record with given ID and returns Record instance

        Parameters
        -----------
        record_id : int
            The FileMaker record id. Be aware that record ids CAN change (e.g. in cloned databases)
        portals : list
            A list of dicts in format [{'name':'objectName', 'offset':1, 'limit':50}]

            Use this if you want to limit the amout of data returned. Offset and limit are optional
            with default values of 1 and 50, respectively.
            All portals will be returned when portals==None. Default None.
        scripts : dict, optional
            Specify which scripts should run when with which parameters
            Example: {'prerequest': ['my_script', 'my_param']}
            Allowed types: 'prerequest', 'presort', 'after'
            List should have length of 2 (both script name and parameter are required.)
        layout : str, optional
            Passing a layout name allows you to set the response (!) layout.
            This is helpful, for example, if you want to limit the number of fields/portals being
            returned and have a dedicated response layout.
        """
        path = API_PATH[u'record_action'].format(
            database=self.database,
            layout=self.layout,
            record_id=record_id
        )

        params = build_portal_params(portals, True) if portals else {}
        params[u'layout.response'] = layout

        # build script param object in FMSDAPI style
        script_params = build_script_params(scripts) if scripts else None
        if script_params:
            params.update(script_params)

        response = self._call_filemaker(u'GET', path, params=params)

        # pass response to foundset generator function. As we are only requesting one record though,
        # we only re-use the code and immediately consume the first (and only) record via next().
        return self._process_foundset_response(response).next()

    @_with_auto_relogin
    def perform_script(self, name,
                       param = None):
        u"""Performs a script with the given name and parameter.

        Returns tuple containing script error and result.

        Parameters:
        --------
        name : str
            The script name as defined in FileMaker Pro
        param: str
            Optional script parameter
        """
        path = API_PATH[u'script'].format(
            database=self.database,
            layout=self.layout,
            script_name=name
        )

        response = self._call_filemaker(u'GET', path, params={u'script.param': param})

        script_error = response.get(u'scriptError', None)
        script_error = int(script_error) if script_error else None
        script_result = response.get(u'scriptResult', None)

        return script_error, script_result

    @_with_auto_relogin
    def upload_container(self, record_id, field_name, file_):
        u"""Uploads the given binary data for the given record id and returns True on success.
        Parameters
        -----------
        record_id : int
            The FileMaker record id
        field_name : str
            Name of the container field on the current layout without TO name. E.g.: my_container
        file_ : fileobj
            File object as returned by open() in binary mode.
        """
        path = API_PATH[u'record_action'].format(
            database=self.database,
            layout=self.layout,
            record_id=record_id
        ) + u'/containers/' + field_name + u'/1'

        # requests library handles content type for multipart/form-data incl. boundary
        self._set_content_type(False)
        self._call_filemaker(u'POST', path, files={u'upload': file_})

        return self.last_error == FMSErrorCode.SUCCESS.value

    @_with_auto_relogin
    def get_records(self, offset = 1, limit = 100,
                    sort = None,
                    portals = None,
                    scripts = None,
                    layout = None):
        u"""Requests all records with given offset and limit and returns result as
        (sorted) Foundset instance.

        Parameters
        -----------
        offset : int, optional
            Offset for the query, starting at 1, default 1
        limit : int, optional
            Limit the amount of returned records. Defaults to 100
        sort : list of dicts, optional
            A list of sort criteria. Example:
                [{'fieldName': 'name', 'sortOrder': 'descend'}]
        portals : list of dicts, optional
            Define which portals you want to include in the result.
            Example: [{'name':'objectName', 'offset':1, 'limit':50}]
            Defaults to None, which then returns all portals with default offset and limit.
        scripts : dict, optional
            Specify which scripts should run when with which parameters
            Example: {'prerequest': ['my_script', 'my_param']}
            Allowed types: 'prerequest', 'presort', 'after'
            List should have length of 2 (both script name and parameter are required.)
        layout : str, optional
            Passing a layout name allows you to set the response (!) layout.
            This is helpful, for example, if you want to limit the number of fields/portals being
            returned and have a dedicated response layout.
        """
        path = API_PATH[u'record'].format(
            database=self.database,
            layout=self.layout
        )

        params = build_portal_params(portals, True) if portals else {}
        params[u'_offset'] = offset
        params[u'_limit'] = limit
        params[u'layout.response'] = layout

        if sort:
            params[u'_sort'] = json.dumps(sort)

        # build script param object in FMSDAPI style
        script_params = build_script_params(scripts) if scripts else None
        if script_params:
            params.update(script_params)

        response = self._call_filemaker(u'GET', path, params=params)
        info = response.get(u'dataInfo', {})

        return Foundset(self._process_foundset_response(response), info)

    @_with_auto_relogin
    def find(self, query,
             sort = None,
             offset = 1, limit = 100,
             portals = None,
             scripts = None,
             layout = None):
        u"""Finds all records matching query and returns result as a Foundset instance.

        Parameters
        -----------
        query : list of dicts
            A list of find queries, specified as 'field_name': 'field_value'
            Example:
                [{'drink': 'Coffee'}, {'drink': 'Dr. Pepper'}] will find matches for either Coffee
                or Dr. Pepper.

                You can also negate find requests by adding a key "omit" with value "true".

                Generally, all FileMaker Pro operators are supported. So, wildcard finds with "*" or
                exact matches with "==" should all work like in Pro.
        sort : list of dicts, optional
            A list of sort criteria. Example:
                [{'fieldName': 'name', 'sortOrder': 'descend'}]
        offset : int, optional
            Offset for the query, starting at 1, default 1
        limit : int, optional
            Limit the amount of returned records. Defaults to 100
        portals : list of dicts, optional
            Define which portals you want to include in the result.
            Example: [{'name':'objectName', 'offset':1, 'limit':50}]
            Defaults to None, which then returns all portals with default offset and limit.
        scripts : dict, optional
            Specify which scripts should run when with which parameters
            Example: {'prerequest': ['my_script', 'my_param']}
            Allowed types: 'prerequest', 'presort', 'after'
            List should have length of 2 (both script name and parameter are required.)
        layout : str, optional
            Passing a layout name allows you to set the response (!) layout.
            Your find will still be performed based on the Server.layout attribute.
            This is helpful, for example, if you want to limit the number of fields/portals being
            returned and have a dedicated response layout.
        """
        path = API_PATH[u'find'].format(
            database=self.database,
            layout=self.layout
        )

        data = {
            u'query': query,
            u'sort': sort,
            u'limit': unicode(limit),
            u'offset': unicode(offset),
            u'layout.response': layout
        }

        # build script param object in FMSDAPI style
        script_params = build_script_params(scripts) if scripts else None
        if script_params:
            data.update(script_params)

        # build portal param object in FMSDAPI style
        portal_params = build_portal_params(portals) if portals else None
        if portal_params:
            data.update(portal_params)

        # FM Data API from v17 cannot handle null values, so we remove all Nones from data
        data = dict((k, v) for k, v in data.items() if v is not None)

        response = self._call_filemaker(u'POST', path, data=data)
        info = response.get(u'dataInfo', {})

        return Foundset(self._process_foundset_response(response), info)

    def fetch_file(self, file_url,
                   stream = False):
        u"""Fetches the file from the given url.

        Returns a tuple of filename (unique identifier), content type (e.g. image/png), length,
        and a requests response object. You can access contents by response.content.

        Example:
            url = record.container_field
            name, type_, length, content = fms.fetch_file(url)

        Parameters
        -----------
        file_url : str
            URL to file as returned by FMS.
            Example:
            https://address/Streaming_SSL/MainDB/unique-identifier.png?RCType=EmbeddedRCFileProcessor
        stream : bool, optional
            Set this to True if you don't want the file to immediately be loaded into memory.
            This let's you decide how you want to handle large files before downloading them.
            Access to headers is given before downloading.
            If you are not consuming all data, make sure to close the connection after use by
            calling response.close().
        """
        name = filename_from_url(file_url)
        response = request(method=u'get',
                           url=file_url,
                           verify=self.verify_ssl,
                           stream=stream
                          )

        return (name,
                response.headers.get(u'Content-Type'),
                response.headers.get(u'Content-Length'),
                response)

    @_with_auto_relogin
    def set_globals(self, globals_):
        u"""Set global fields for the currently active session. Returns True on success.

        Global fields do not need to be placed on the layout and can be used for establishing
        relationships of which the global is a match field.

        Parameters
        -----------
        globals_ : dict
            Dict of { field name : value }
            Note that field names must be fully qualified, i.e. contain the TO name
            Example:
                { 'Table::myField': 'whatever' }
        """
        path = API_PATH[u'global'].format(database=self.database)

        data = {u'globalFields': globals_}

        self._call_filemaker(u'PATCH', path, data=data)
        return self.last_error == FMSErrorCode.SUCCESS.value

    @property
    def last_error(self):
        u"""Returns last error number returned by FileMaker Server as int.

        Error is set by _call_filemaker method. If error == -1, the previous request failed
        and no FM error code is available. If no request was made yet, last_error will be None.
        """
        if self._last_fm_error:
            error = int(self._last_fm_error)
        else:
            error = None
        return error

    @property
    def last_script_result(self):
        u"""Returns last script results as returned by FMS as dict in format {type: [error, result]}

        Only returns keys that have a value from the last call. I.e. 'presort' will
        only be present if the last call performed a presort script.
        The returned error (0th element in list) will always be converted to int.
        """
        if self._last_script_result:
            result = dict((
                k, [int(v[0]), v[1]]) for k, v in self._last_script_result.items() if v[0] is not None)
        return result

    def _call_filemaker(self, method, path,
                        data = None,
                        params = None,
                        **kwargs):
        u"""Calls a FileMaker Server Data API path and returns the parsed fms response data

        Parameters
        -----------
        method : str
            The http request method, e.g. POST
        path : str
            The API path, /fmi/data/v1/databases/:database/...
        data : dict of str : str, optional
            Dict of parameter data for http request
            Can be None if API expects no data, e.g. for logout
        params : dict of str : str, optional
            Dict of get parameters for http request
            Can be None if API expects no params
        auth : tuple of str, str, optional
            Tuple containing user and password for HTTP basic
            auth
        """

        url = self.url + path
        request_data = json.dumps(data) if data else None

        # if we have a token, make sure it's included in the header
        # if not, the Authorization header gets removed (necessary for example
        # for logout)
        self._update_token_header()

        response = request(method=method,
                           headers=self._headers,
                           url=url,
                           data=request_data,
                           verify=self.verify_ssl,
                           params=params,
                           proxies=self.proxies,
                           **kwargs)

        try:
            response_data = response.json()
        except json.decoder.JSONDecodeError, ex:
            raise BadJSON(ex, response)

        fms_messages = response_data.get(u'messages')
        fms_response = response_data.get(u'response')

        self._update_script_result(fms_response)
        self._last_fm_error = fms_messages[0].get(u'code', -1)
        if self.last_error != FMSErrorCode.SUCCESS.value:
            raise FileMakerError(self._last_fm_error,
                                 fms_messages[0].get(u'message', u'Unkown error'))

        self._set_content_type() # reset content type

        return fms_response

    def _update_script_result(self, response):
        u"""Extracts script result data from fms response and updates script result attribute"""
        self._last_script_result = {
            u'prerequest': [
                response.get(u'scriptError.prerequest', None),
                response.get(u'scriptResult.prerequest', None)
            ],
            u'presort': [
                response.get(u'scriptError.presort', None),
                response.get(u'scriptResult.presort', None)
            ],
            u'after': [
                response.get(u'scriptError', None),
                response.get(u'scriptResult', None)
            ]
        }

        return self._last_script_result

    def _update_token_header(self):
        u"""Update header to include access token (if available) for subsequent calls."""
        if self._token:
            self._headers[u'Authorization'] = u'Bearer ' + self._token
        else:
            self._headers.pop(u'Authorization', None)
        return self._headers

    def _set_content_type(self, type_ = u'application/json'):
        u"""Set the Content-Type header and returns the updated _headers dict.

        Parameters
        -----------
        type_ : str, boolean
            String definining the content type for the HTTP header or False to remove the
            Content-Type key from _headers (i.e. let the requests lib handle the Content-Type.)
        path : str
        """
        if isinstance(type_, unicode):
            self._headers[u'Content-Type'] = type_
        elif not type_:
            self._headers.pop(u'Content-Type')
        else:
            raise ValueError
        return self._headers

    def _process_foundset_response(self, response):
        u"""Generator function that takes a response object, brings it into a Foundset/Record
        structure and yields processed Records.

        Lazily processing and yielding the results is slightly faster than building a list upfront
        when you deal with big foundsets containing records that each have many portal records.
        It won't save us much memory as we still hold the response, but initial processing time goes
        down, and we only need to build the records when we actually use them.
        (may think of another approach if it proves to be more pain than gain though)

        Parameters
        -----------
        response : dict
            FMS response from a _call_filemaker request
        """
        data = response[u'data']

        for record in data:
            field_data = record[u'fieldData']

            # Add meta fields to record.
            # TODO: this can clash with fields that have the same name. Find a better
            # way (maybe prefix?).
            # Note that portal foundsets have the recordId field included by default
            # (without the related table prefix).
            field_data[u'recordId'] = record.get(u'recordId')
            field_data[u'modId'] = record.get(u'modId')

            keys = list(field_data)
            values = list(field_data.values())

            portal_info = {}
            for entry in record.get(u'portalDataInfo', []):
                # a portal is identified by its object name, or, if not available, its TO name
                portal_identifier = entry.get(u'portalObjectName', entry[u'table'])
                portal_info[portal_identifier] = entry

            for portal_name, rows in record[u'portalData'].items():
                keys.append(PORTAL_PREFIX + portal_name)

                # further delay creation of portal record instances
                related_records = (
                    Record(list(row), list(row.values()),
                           in_portal=True, type_conversion=self.type_conversion
                          ) for row in rows
                )
                # add portal foundset to record
                values.append(Foundset(related_records, portal_info.get(portal_name, {})))

            yield Record(keys, values, type_conversion=self.type_conversion)
