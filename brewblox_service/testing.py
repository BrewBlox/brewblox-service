"""
Testing utility functions
"""

from aiohttp.client_exceptions import ContentTypeError


async def response(request, status=200):
    retv = await request
    if retv.status != status:
        print(retv)
        assert retv == status
    try:
        return await retv.json()
    except ContentTypeError:
        return await retv.text()
