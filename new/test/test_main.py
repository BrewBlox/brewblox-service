"""
Test functions for brewblox_service.__main__
"""

from brewblox_service import __main__ as main


def test_create_app():
    assert main.create_app({})
