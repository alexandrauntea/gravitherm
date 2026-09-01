"""Client MQTT - publica citiri de senzori, subscrie la comenzi de actuatoare.

Contractul de topic-uri si payload e definit in interfaces.py.
"""

import json
from datetime import UTC, datetime

import paho.mqtt.client as mqtt

from gravitherm.config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC_PREFIX


def make_client(client_id: str) -> mqtt.Client:
    client = mqtt.Client(client_id=client_id)
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    return client


def publish_reading(client: mqtt.Client, topic_suffix: str, value: float, unit: str) -> None:
    topic = f"{MQTT_TOPIC_PREFIX}/sensors/{topic_suffix}"
    payload = json.dumps(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "value": value,
            "unit": unit,
        }
    )
    client.publish(topic, payload)
