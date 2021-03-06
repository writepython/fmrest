u"""Record class for FileMaker record responses"""

from __future__ import absolute_import
from .utils import convert_string_type
from .const import PORTAL_PREFIX
from itertools import izip

class Record(object):
    u"""A FileMaker record representation.

    (with ideas from: https://github.com/kennethreitz/records)
    """
    __slots__ = (u'_keys', u'_values', u'_in_portal', u'_modifications')

    def __init__(self, keys, values,
                 in_portal = False, type_conversion = False):
        u"""Initialize the Record class.

        Parameters
        ----------
        keys : list
            List of keys (fields) for this Record as returned by FileMaker Server
        values : list
            Values corresponding to keys
        in_portal : bool
            If true, this record instance describes a related record from a portal. This is a
            special case as portal records are treated differently by the Data API and don't get
            all standard keys (modId is missing).
        type_conversion : bool, optional
            If True, attempt to convert string values into their potential original types.
            FileMaker Data API always returns strings and there is no way of knowing the correct
            type of a requested field value. Be cautious with this parameter!
            Values will be converted into int, float, datetime, timedelta, string.
        """

        self._keys = keys

        if type_conversion:
            self._values = []
            for value in values:
                parsed = convert_string_type(value) if isinstance(value, unicode) else value
                self._values.append(parsed)
        else:
            self._values = values

        self._in_portal = in_portal
        self._modifications = {}

        if len(self._keys) != len(self._values):
            raise ValueError(u"Length of keys does not match length of values.")

    def __repr__(self):
        return u'<Record id={} modification_id={} is_dirty={}>'.format(
            self.record_id,
            self.modification_id,
            self.is_dirty
        )

    def __getitem__(self, key):
        u"""Returns value for given key. For dict lookups, like my_id = record['id']."""
        keys = self.keys()

        try:
            index = keys.index(key)
            return self.values()[index]
        except ValueError:
            raise KeyError((u"No field named {}. Note that the Data API only returns fields "
                            u"placed on your FileMaker layout.").format(key))

    def __getattr__(self, key):
        u"""Returns value for given key. For attribute lookups, like my_id = record.id.

        Calls __getitem__ for key access.
        """
        try:
            return self[key]
        except KeyError, ex:
            raise AttributeError(ex)

    def __setitem__(self, key, value):
        u"""Allows changing values of fields available in _keys.

        Modified keys land in _modifications and are later used to write values back to
        FileMaker.
        """
        if key not in self.__slots__:
            # objects in __slots__ are the only allowed attributes.
            # all others are handled here
            if key not in self.keys():
                raise KeyError(unicode(key) + u" is not a valid field name.")
            elif key.startswith(PORTAL_PREFIX):
                raise KeyError(
                    (u"Portal data cannot be set through the record instance. "
                     u"To edit portal data, build a dict and pass it to edit_records().")
                )
            elif value != self[key]:
                # store modified key and value for later re-use
                self._modifications[key] = value

                # also update the value in _values, so that values() returns expected data
                index = self.keys().index(key)
                self._values[index] = value
        else:
            # allow setting of attributes in __slots__
            super(Record, self).__setattr__(key, value)

    def __setattr__(self, key, value):
        u"""See __setitem__. Returns AttributeError if trying to set a value for a field/attribute
        not existing in the record instance.
        """
        try:
            return self.__setitem__(key, value)
        except KeyError, ex:
            raise AttributeError(ex)

    def modifications(self):
        u"""Returns a dict of changed keys in the form of {key : new_value}.

        Used for writing back record changes via Server.edit(record).
        """
        return self._modifications

    @property
    def is_dirty(self):
        u"""Returns True if key values have been modified."""
        return len(self._modifications) > 0

    @property
    def record_id(self):
        u"""Returns the internal record id.

        This is exposed as a method to reliably return the record id, even if the API might change
        the field name in the future.
        """
        return int(self.recordId)

    @property
    def modification_id(self):
        u"""Returns the internal modification id.

        This is exposed as a method to reliably return the modification id, even if the API might
        change the field name in the future.
        """
        return None if self._in_portal else int(self.modId)

    def keys(self):
        u"""Returns all keys of this record."""
        return self._keys

    def values(self):
        u"""Returns all values of this record."""
        return self._values

    def to_dict(self, ignore_portals = False, ignore_internal_ids = False):
        u"""Returns record values as dictionary of key: val."""
        zipped = izip(self.keys(), self.values())

        if ignore_portals:
            out = dict((k, v) for k, v in zipped if not k.startswith(PORTAL_PREFIX))
        else:
            out = dict(zipped)

        if ignore_internal_ids:
            out.pop(u'recordId', None)
            out.pop(u'modId', None)
        return out

    def pop(self, key, default = None):
        u"""Pops the record's key. Returns key's value or default."""
        keys = self.keys()

        try:
            value = self[key]
            index = keys.index(key)
            self._keys.pop(index)
            self._values.pop(index)
            return value
        except (KeyError, ValueError):
            return default
