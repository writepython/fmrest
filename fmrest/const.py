u"""fmrest constants"""
from __future__ import absolute_import
import os
from enum import Enum, unique
from pkg_resources import get_distribution

__version__ = get_distribution(u'python-fmrest').version

PORTAL_PREFIX = u'portal_'
TIMEOUT = int(os.environ.get(u'fmrest_timeout', 10))

API_PATH = {
    u'auth':             u'/fmi/data/v1/databases/{database}/sessions/{token}',
    u'record':           u'/fmi/data/v1/databases/{database}/layouts/{layout}/records',
    u'record_action':    u'/fmi/data/v1/databases/{database}/layouts/{layout}/records/{record_id}',
    u'find':             u'/fmi/data/v1/databases/{database}/layouts/{layout}/_find',
    u'script':           u'/fmi/data/v1/databases/{database}/layouts/{layout}/script/{script_name}',
    u'global':           u'/fmi/data/v1/databases/{database}/globals'
}


class FMSErrorCode(Enum):
    u"""FMS error codes that are being referenced in the code"""
    SUCCESS = 0
    RECORD_MISSING = 101
    INVALID_USER_PASSWORD = 212
    INVALID_DAPI_TOKEN = 952
FMSErrorCode = unique(FMSErrorCode)
