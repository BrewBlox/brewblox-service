"""
Default service middlewares. This includes error handling and automatic CORS headers.
"""


from aiohttp import hdrs, web, web_exceptions
from aiohttp.typedefs import Handler

from brewblox_service import brewblox_logger, strex

LOGGER = brewblox_logger(__name__)


def cors_response(request: web.Request, response: web.Response) -> web.Response:
    response.headers['Access-Control-Allow-Origin'] =\
        request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Methods'] =\
        request.headers.get('Access-Control-Request-Method', ','.join(hdrs.METH_ALL))
    response.headers['Access-Control-Allow-Headers'] =\
        request.headers.get('Access-Control-Request-Headers', '*')
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


@web.middleware
async def cors_middleware(request: web.Request, handler: Handler) -> web.Response:
    # preflight requests
    if request.method == 'OPTIONS':
        return cors_response(request, web.Response())

    try:
        response = await handler(request)
        return cors_response(request, response)
    except web_exceptions.HTTPError as ex:  # error_middleware converts other exceptions to HTTPError
        cors_response(request, ex)
        raise ex


@web.middleware
async def error_middleware(request: web.Request, handler: Handler) -> web.Response:
    try:
        return await handler(request)
    except web_exceptions.HTTPError:
        raise
    except Exception as ex:
        raise web_exceptions.HTTPInternalServerError(reason=strex(ex))
