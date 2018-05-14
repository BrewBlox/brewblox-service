"""
Tests brewblox_service.__main__.py
"""

from brewblox_service import __main__ as main


TESTED = main.__name__


def test_main(loop, mocker):
    create_mock = mocker.patch(TESTED + '.service.create_app')
    furnish_mock = mocker.patch(TESTED + '.service.furnish')
    run_mock = mocker.patch(TESTED + '.service.run')
    events_mock = mocker.patch(TESTED + '.events.setup')
    app_mock = create_mock.return_value

    main.main()

    create_mock.assert_called_once_with(default_name='_service')
    furnish_mock.assert_called_once_with(app_mock)
    run_mock.assert_called_once_with(app_mock)
    events_mock.assert_called_once_with(app_mock)
