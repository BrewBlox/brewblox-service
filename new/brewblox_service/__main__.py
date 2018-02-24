"""
Entry point for standalone brewblox_service.

This will create the app, and run a simulator.
"""

from brewblox_service import events, service, simulator


def main():
    app = service.create()

    # Add implementation-specific functionality
    # In this case: simulator
    simulator.setup(app)

    # Event handling is optional
    # It should be enabled explicitly by service implementations
    events.setup(app)

    # Add all default endpoints, and announce service to gateway
    service.furnish(app)

    # service.run() will start serving clients async
    service.run(app)


if __name__ == '__main__':
    main()
