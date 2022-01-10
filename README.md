# Scaffolding for Brewblox service applications

In order to reduce code duplication between services, generic functionality is implemented here.

For an example on how to implement your own service based on `brewblox-service`, see <https://github.com/brewblox/brewblox-boilerplate>.

`brewblox-service` can technically be launched as a standalone application, but will not be very useful.

## [brewblox_service](./brewblox_service/__init__.py)

Small generic tools are defined here.

`brewblox_logger` can be used for creating module-specific loggers. It is not required, but will play a bit nicer with default formatting of the log.

Example:

```python
from brewblox_service import brewblox_logger

LOGGER = brewblox_logger(__name__)
LOGGER.info('hello')
```

## [service.py](./brewblox_service/service.py)

Parses commandline arguments, creates an `aiohttp` app, and runs it.

The shortest implementation is:

```python
app = service.create_app(default_name='my_service')
service.furnish(app)
service.run(app)
```

This will get you a working web application, but it will not have any endpoints.

Applications can configure their own features, and add new commandline arguments.

Example:

```python
# Separately creating the parser allows adding arguments to the default set
parser = service.create_parser(default_name='my_service')
parser.add_argument('--my-arg')

# Now create the app
app = service.create_app(parser=create_parser())

# Add features for this service
device.setup(app)
api.setup(app)

# Furnish and run
service.furnish(app)
service.run(app)
```

## [features.py](./brewblox_service/features.py)

Many service features are application-scoped. Their lifecycle should span multiple requests, either because they are not request-driven, or because they manage asynchronous I/O operations (such as listening to AMQP messages).

The `ServiceFeature` class offers an abstract base class for this behavior. Implementing classes should define `startup(app)` and `shutdown(app)` functions, and those will be automatically called when the application starts up and shuts down.

Both `startup()` and `shutdown()` are called in an async context, making them the async counterparts of `__init__()` and `__del__()` functions.

Features must be constructed after the app is created, but before it starts running. (`service.create_app()` and `service.run(app)`)

The `add()` and `get()` functions make it easy to centrally declare a feature, and then use it in any function that has a reference to the aiohttp app.

## [mqtt.py](./brewblox_service/mqtt.py)

The replacement for the AMQP-based `events` module.

The major advantages over AMQP is that the protocol is simpler, and supports websocket transport.
This allows for it to be used outside a Brewblox network.

Messages have a /-separated *topic* and a JSON-serialized body.

To publish data, all you need is the `publish(topic, message)` function.

To listen to incoming messages, you can combine `subscribe(topic)` with one or more calls to `listen(topic, callback)`.
The subscribe/listen functions allow for + and # wildcards to be used.

For a detailed explanation of how to use MQTT topics, see http://www.steves-internet-guide.com/understanding-mqtt-topics/.

For the Brewblox spec on how and where to publish data, see https://brewblox.netlify.app/dev/reference/event_logging.html.

Includes top-level convenience functions for `publish(topic, message)`, `listen(topic, callback)` and `subscribe(topic)`.
