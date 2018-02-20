"""
Test functions for brewblox_service.__main__
"""

from brewblox_service import __main__ as main


TESTED = 'brewblox_service.__main__'


def test_get_args():
    # test defaults
    args = main.get_args([])
    assert args.port == 5000
    assert args.service == 'brewblox_service'
    assert not args.debug
    assert not args.output

    # test output file name
    args = main.get_args(['-o', 'file_name'])
    assert args.output == 'file_name'

    # test service name
    args = main.get_args(['-s', 'service_name'])
    assert args.service == 'service_name'

    # test port
    args = main.get_args(['-p', '1234'])
    assert args.port == 1234

    # test debug mode
    args = main.get_args(['--debug'])
    assert args.debug

    # test
    args = main.get_args(['--plugindir', 'pluggy'])
    assert args.plugindir == 'pluggy'


def test_init_logging(mocker):
    log_mock = mocker.patch(TESTED + '.logging')
    handler = mocker.patch(TESTED + '.TimedRotatingFileHandler').return_value

    args = main.get_args([])
    main.init_logging(args)

    assert log_mock.basicConfig.call_count == 1
    assert log_mock.getLogger().addHandler.call_count == 0

    args = main.get_args(['-o', 'outfile'])
    main.init_logging(args)

    assert log_mock.basicConfig.call_count == 2
    log_mock.getLogger().addHandler.assert_called_once_with(handler)


def test_furnish_app(app):
    main.furnish_app(app)


def test_main(mocker):
    log_mock = mocker.patch(TESTED + '.init_logging')
    app_mock = mocker.patch(TESTED + '.rest.create_app').return_value
    furnish_mock = mocker.patch(TESTED + '.furnish_app')
    announce_mock = mocker.patch(TESTED + '.announcer.announce')

    main.main([])

    assert log_mock.call_count == 1
    assert furnish_mock.call_count == 1
    assert announce_mock.call_count == 1
    assert app_mock
