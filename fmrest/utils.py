u"""Utility functions for fmrest"""
from __future__ import absolute_import
from typing import List, Dict, Any, Iterator
import requests
from .exceptions import RequestException
from .const import TIMEOUT
from itertools import imap


def request(*args, **kwargs):
    u"""Wrapper around requests library request call"""
    try:
        return requests.request(*args, timeout=TIMEOUT, **kwargs)
    except Exception, ex:
        raise RequestException(ex, args, kwargs)

def build_portal_params(portals, names_as_string = False):
    u"""Takes a list of dicts and returns a dict in a format as FMServer expects it.

    FMS expects portals and their options to be specified in the following format:
        portal=["Portal1", "Portal2"]&_offset.Portal1=1&_limit.Portal1=10

    This function will return a dict of params suitable for the requests module.

    Parameters
    -----------
    portals : list
        List of dicts with keys name, offset, limit
        Example:
            [
                {
                    'name': 'addressPortal', # FM object name of portal
                    'offset': 1,
                    'limit': 50
                },
                {
                    'name': 'notesPortal',
                    'offset': 1,
                    'limit': 50
                }
            ]
    names_as_string : bool
        For GET params the list of portal names might need to be turned into
        a string. Use this to get something like '["Portal1", "Portal2"]'.
        If False, portals key will have a value of type list, like ["Portal1", "Portal2"]
    """

    params: Dict[unicode, Any]

    portal_selector = [portal[u'name'] for portal in portals]
    if names_as_string:
        portal_param = u"[" + u', '.join(imap(lambda x: u'"' + x + u'"', portal_selector)) + u"]"
        params = {u'portal': portal_param}
        param_prefix = u'_' # for GET we need an underscore as prefix
    else:
        params = {u'portal': portal_selector}
        param_prefix = u''

    for portal in portals:
        params[param_prefix + u'offset.' + portal[u'name']] = portal.get(u'offset', 1)
        params[param_prefix + u'limit.' + portal[u'name']] = portal.get(u'limit', 50)

    return params

def build_script_params(scripts):
    u"""Takes simplified scripts object and returns scripts objects as FMSDAPI expects it.

    Example simplified scripts object:

        scripts = {
            'prerequest': ['script_name', 'script_parameter'],
            'presort': ['script_name', 'script_parameter'],
            'after': ['script_name', 'script_parameter']
        }
    """

    # read user-defined script configuration
    # if no values were passed, initilize list with None as script and param
    presort = scripts.get(u'presort', [None]*2)
    prerequest = scripts.get(u'prerequest', [None]*2)
    after = scripts.get(u'after', [None]*2)

    # format for FMSDAPI
    verbose_scripts = {
        u'script.prerequest': prerequest[0],
        u'script.prerequest.param': prerequest[1],
        u'script.presort': presort[0],
        u'script.presort.param': presort[1],
        u'script': after[0],
        u'script.param': after[1],
    }

    # return only keys that have a real value
    return dict((k, v) for k, v in verbose_scripts.items() if v is not None)

def cache_generator(iterator, cache):
    u"""Takes iterator and cache list, caches values before yielding them.
    Eventually flagging cache as complete.

    Parameters
    ----------
    iterator : generator
        Generator to consume
    cache : list
        List holding list of cached values and state of caching.
        If cache[1] is True, all values have been cached.
    """

    for val in iterator:
        cache[0].append(val)
        yield val

    cache[1] = True # all values have been cached

def filename_from_url(url):
    u"""Returns filename from given remote container url."""

    # remove query string
    url = url.split(u'?')[0]

    # get last part of url. FileMaker Data API does not always include the file extension
    # (e.g. for non audio/image/video) so we cannot rely on matching for a filename with extension
    filename = url.split(u'/')[-1]

    return filename

def convert_string_type(value):
    u"""Quick and dirty way to convert strings into their (guessed) original type.

    FileMaker Data API only returns strings. Hopefully, we can throw this function away as
    soon as the Data API is out of beta :-)

    Not used when running fmrest with default parameters as returned values can
    be unexpected.
    """

    # int and float
    for type_ in int, float:
        try:
            return type_(value)
        except ValueError:
            pass

    # datetime / timedelta
    try:
        from dateutil.parser import parse
        from datetime import timedelta
        parsed = parse(value)
        if u'/' not in value:
            #assume time, as FM always returns / for date and ts, and parse didn't raise ValueError
            parsed = timedelta(hours=parsed.hour, minutes=parsed.minute, seconds=parsed.second)
        return parsed
    except ValueError:
        pass

    # timedelta (above try will fail for >24h)
    time_split = value.split(u':')
    if len(time_split) == 3:
        try:
            hours = int(time_split[0])
            minutes = int(time_split[1])
            seconds = int(time_split[2])
            return timedelta(hours=hours, minutes=minutes, seconds=seconds)
        except ValueError:
            pass

    # fall back to string
    return value
