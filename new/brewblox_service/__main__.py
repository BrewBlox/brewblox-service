"""
Entry point for standalone brewblox_service.

This will create the app, and run a simulator.
"""

from brewblox_service import service, simulator


def main():
    app = service.create()

    # Add implementation-specific functionality
    # In this case: simulator
    simulator.init_app(app)

    # Add all default endpoints, and announce service to gateway
    service.furnish(app)

    # service.run() will start serving clients async
    service.run(app)


if __name__ == '__main__':
    main()
