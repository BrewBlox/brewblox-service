"""
Entry point for standalone brewblox_service.

This will create the app, and run a simulator.
"""

from brewblox_service import service
import asyncio


def main():
    async def async_task():
        app = await service.create()

        # Add implementation-specific functionality
        # In this case: simulator

        await service.furnish(app)
        await service.run(app)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_task)


if __name__ == '__main__':
    main()
