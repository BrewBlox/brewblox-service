import asyncio
import aio_pika
import logging
from aio_pika.exchange import ExchangeType
import sys
import json


async def read_main(loop):
    connection = await aio_pika.connect_robust(loop=loop)

    # queue_name = "test_queue"

    # Creating channel
    channel = await connection.channel()    # type: aio_pika.Channel

    # Declaring queue
    exchange = await channel.declare_exchange('brewblox',
                                              type=ExchangeType.FANOUT,
                                              auto_delete=True)
    queue = await channel.declare_queue(auto_delete=True)   # type: aio_pika.Queue

    await queue.bind(exchange, queue)

    async for message in queue:
        with message.process():
            logging.info(message.body)


async def send_main(loop, routing_key, count):
    connection = await aio_pika.connect_robust(loop=loop)

    channel = await connection.channel()    # type: aio_pika.Channel
    exchange = await channel.declare_exchange('brewblox', type=ExchangeType.TOPIC, auto_delete=True)
    message = json.dumps(dict(key=routing_key))
    logging.info(f'sending {message}')

    for i in range(0, count):
        await exchange.publish(
            aio_pika.Message(
                body=message.encode()
            ),
            routing_key=routing_key
        )

    await connection.close()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)-8s %(name)-30s  %(message)s',
        datefmt='%Y/%m/%d %H:%M:%S'
    )
    logging.getLogger('pika').setLevel(logging.WARNING)
    logging.getLogger('aio_pika').setLevel(logging.WARNING)

    key = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) >= 3 else 1
    loop.run_until_complete(send_main(loop, key, count))

    loop.close()
