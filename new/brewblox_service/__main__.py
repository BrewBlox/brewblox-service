"""
Entry point for standalone brewblox_service.

This will create the app, and run a simulator.
"""

from brewblox_service import service, simulator, events
import logging


def main():
    app = service.create()

    # Add implementation-specific functionality
    # In this case: simulator
    simulator.init_app(app)

    events.setup(app)
    # events.subscribe(app, 'brewblox', 'bb_queue')
    # events.subscribe(app, 'brewblox', 'controller')

    async def on_message(message):
        logging.info(f'Message received: {message}')

    async def on_json(queue, message: dict):
        logging.info(f'JSON message: {message}')

    listener = events.get_listener(app)
    listener.subscribe(app, 'brewblox', 'controller1', on_json=on_json)
    listener.subscribe(app, 'brewblox', 'controller2', on_json=on_json)

    # Add all default endpoints, and announce service to gateway
    service.furnish(app)

    # service.run() will start serving clients async
    service.run(app)


if __name__ == '__main__':
    main()
