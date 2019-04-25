"""
Cross Origin Resource Sharing (CORS) headers must be present when using multiple backends.
This middleware automatically returns OPTIONS requests, and appends other requests with the correct headers.
"""

from asyncio import CancelledError

from aiohttp import hdrs, web, web_exceptions

from brewblox_service import brewblox_logger, strex

LOGGER = brewblox_logger(__name__)


def enable_cors(app: web.Application):
    app.middlewares.append(cors_middleware)


def set_cors_headers(request, response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] =\
        request.headers.get('Access-Control-Request-Method', ','.join(hdrs.METH_ALL))
    response.headers['Access-Control-Allow-Headers'] =\
        request.headers.get('Access-Control-Request-Headers', '*')
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


@web.middleware
async def cors_middleware(request: web.Request, handler: web.RequestHandler) -> web.Response:
    # preflight requests
    if request.method == 'OPTIONS':
        return set_cors_headers(request, web.Response())
    else:
        try:
            response = await handler(request)
        except CancelledError:
            raise  # Client abandoned request - we're not returning a response anymore
        except web_exceptions.HTTPError as ex:
            response = ex
        except Exception as ex:
            response = web_exceptions.HTTPInternalServerError(reason=strex(ex))

        return set_cors_headers(request, response)
