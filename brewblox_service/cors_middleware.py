"""
Cross Origin Resource Sharing (CORS) headers must be present when using multiple backends.
This middleware automatically returns OPTIONS requests, and appends other requests with the correct headers.
"""

from aiohttp import web


def enable_cors(app: web.Application):
    app.middlewares.append(cors_middleware)


ALLOWED_HEADERS = ','.join((
    'content-type',
    'accept',
    'origin',
    'authorization',
    'x-requested-with',
    'x-csrftoken',
))


def set_cors_headers(request, response):
    response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Methods'] = request.method
    response.headers['Access-Control-Allow-Headers'] = ALLOWED_HEADERS
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


@web.middleware
async def cors_middleware(request: web.Request, handler: web.RequestHandler) -> web.Response:
    # preflight requests
    if request.method == 'OPTIONS':
        return set_cors_headers(request, web.Response())
    else:
        response = await handler(request)
        return set_cors_headers(request, response)
