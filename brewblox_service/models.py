from typing import Literal, Optional

from pydantic import BaseModel

MqttProtocol = Literal['mqtt', 'mqtts', 'ws', 'wss']


class ServiceConfig(BaseModel):
    host: str
    port: int
    name: str
    debug: bool
    mqtt_protocol: MqttProtocol
    mqtt_host: str
    mqtt_port: Optional[int]
    mqtt_path: str
    history_topic: str
    state_topic: str
