"""
Testing utility functions
"""

import re
from contextlib import contextmanager
from subprocess import DEVNULL, run

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


def find_free_port():
    """
    Returns the next free port that is available on the OS
    This is a bit of a hack, it does this by creating a new socket, and calling
    bind with the 0 port. The operating system will assign a brand new port,
    which we can find out using getsockname(). Once we have the new port
    information we close the socket thereby returning it to the free pool.
    This means it is technically possible for this function to return the same
    port twice (for example if run in very quick succession), however operating
    systems return a random port number in the default range (1024 - 65535),
    and it is highly unlikely for two processes to get the same port number.
    In other words, it is possible to flake, but incredibly unlikely.
    """
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 0))
    portnum = s.getsockname()[1]
    s.close()

    return portnum


@contextmanager
def mqtt_broker(name='mqtt-test-broker', image='ghcr.io/brewblox/mosquitto:develop'):
    """
    Spawns and closes an MQTT broker image.
    To prevent conflict, it listens on random free ports.
    The context manager yields a dict containing the randomly selected port numbers.
    """
    mqtt_port = find_free_port()
    ws_port = find_free_port()
    run(['docker', 'stop', name], stdout=DEVNULL)
    run(
        [
            'docker',
            'run',
            '--rm',
            '--detach',
            f'--name={name}',
            f'--publish={mqtt_port}:1883',
            f'--publish={ws_port}:15675',
            image,
        ],
        check=True)
    try:
        yield {'mqtt': mqtt_port, 'ws': ws_port}
    except Exception:
        run(['docker', 'ps'])
        raise
    finally:
        run(['docker', 'logs', '--timestamps', name])
        run(['docker', 'stop', name], stdout=DEVNULL)
