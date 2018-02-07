"""
Test functions for brewblox_service.__main__
"""

from brewblox_service import __main__ as main


def test_get_args():
    args = main.get_args([
        '-o', 'file_name',
        '-c', 'config_name'])

    assert args.output == 'file_name'
    assert args.config == 'config_name'
    assert args.name == 'brewblox_service'

    args = main.get_args([
        '-n', 'service_name'
    ])

    assert args.name == 'service_name'
    assert not args.output


def test_init_logging(mocker):
    log_mock = mocker.patch('brewblox_service.__main__.logging')
    handler = log_mock.handlers.TimedRotatingFileHandler.return_value

    args = main.get_args([])
    main.init_logging(args)

    assert log_mock.basicConfig.call_count == 1
    assert log_mock.getLogger().addHandler.call_count == 0

    args = main.get_args(['-o', 'outfile'])
    main.init_logging(args)

    assert log_mock.basicConfig.call_count == 2
    log_mock.getLogger().addHandler.assert_called_once_with(handler)


def test_main(mocker):
    log_mock = mocker.patch('brewblox_service.__main__.init_logging')
    app_mock = mocker.patch('brewblox_service.__main__.rest.create_app').return_value

    main.main([])

    assert log_mock.call_count == 1
    assert app_mock
