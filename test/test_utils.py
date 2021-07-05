"""
Tests brewblox_service.__init__ utils
"""

from brewblox_service import strex


def test_strex():
    try:
        raise RuntimeError('Boo!')
    except RuntimeError as ex:
        msg = strex(ex)
        assert msg == 'RuntimeError(Boo!)'

        msg = strex(ex, tb=True)
        assert msg.startswith('RuntimeError(Boo!)\n\n')
        assert 'Traceback (most recent call last):' in msg
