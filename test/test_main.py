"""
Tests brewblox_service.__main__.py
"""

from brewblox_service import __main__ as main

TESTED = main.__name__


def test_main(mocker):
    m_create = mocker.patch(TESTED + '.service.create_app')
    m_furnish = mocker.patch(TESTED + '.service.furnish')
    m_run = mocker.patch(TESTED + '.service.run')
    m_mqtt = mocker.patch(TESTED + '.mqtt.setup')
    m_app = m_create.return_value

    main.main()

    m_create.assert_called_once_with(default_name='_service')
    m_furnish.assert_called_once_with(m_app)
    m_run.assert_called_once_with(m_app)
    m_mqtt.assert_called_once_with(m_app)
