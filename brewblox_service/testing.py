"""
Testing utility functions
"""

import re

from aiohttp.client_exceptions import ContentTypeError


async def response(request, status=200):
    retv = await request
    payload = await retv.text()

    if retv.status != status:
        print(retv)
        print(payload)
        raise AssertionError(f'Unexpected response code. (Expected {status}, got {retv.status})')

    try:
        return await retv.json()
    except ContentTypeError:
        return payload


class matching:
    """Assert that a given string meets some expectations."""

    def __init__(self, pattern, flags=0):
        self._regex = re.compile(pattern, flags)

    def __eq__(self, actual):
        return bool(self._regex.match(actual))

    def __repr__(self):
        return self._regex.pattern
