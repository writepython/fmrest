from __future__ import absolute_import
from typing import Optional, Any
import requests

class FMRestException(Exception):
    u"""The base fmrest Exception."""

class RequestException(FMRestException):
    u"""Exception for http request errors

    Re-raised after requests module exception
    """

    def __init__(self, original_exception, request_args, request_kwargs):
        u"""Parameters
        ----------
        original_exception
            The original exception raised by requests module
        request_args
            Args to the request function
        request_kwargs
            Keyword args to the request function
        """

        self._original_exception = original_exception
        self._request_args = request_args
        self._request_kwargs = request_kwargs
        super(RequestException, self).__init__(u'Request error: {}'.format(original_exception))

class ResponseException(FMRestException):
    u"""Exception for http response errors

    Re-raised after requests module exception
    """

    def __init__(self, original_exception, response):
        u"""Parameters
        ----------
        original_exception
            The original exception raised by requests module
        response:
            Response object of requests module
        """
        self._response = response
        super(ResponseException, self).__init__(
            u'{}, {} http response, content-type: {}'.format(
                original_exception,
                self._response.status_code,
                self._response.headers.get(u'content-type', None))
        )

class BadJSON(ResponseException):
    u"""Invalid json response"""

class FileMakerError(FMRestException):
    u"""Error raised by FileMaker Data API"""

    def __init__(self, error_code, error_message):
        super(FileMakerError, self).__init__(u'FileMaker Server returned error {}, {}'.format(error_code, error_message))

class RecordError(FMRestException):
    u"""Error with the local Record instance."""
