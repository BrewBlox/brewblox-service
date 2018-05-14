"""
Entry point for standalone brewblox_service.

This will create the app, and enable events.
"""

from brewblox_service import events, service


def main():
    app = service.create_app(default_name='_service')

    # Event handling is optional
    # It should be enabled explicitly by service implementations
    events.setup(app)

    # Add all default endpoints
    service.furnish(app)

    # service.run() will start serving clients async
    service.run(app)


if __name__ == '__main__':
    main()
