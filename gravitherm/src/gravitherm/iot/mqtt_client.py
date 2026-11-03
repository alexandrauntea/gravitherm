"""Client MQTT - publică citiri de senzori și starea actuatoarelor, subscrie la comenzi.

Contractul de topic-uri și payload este definit în interfaces.py.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import paho.mqtt.client as mqtt  # type: ignore[import-untyped]

from gravitherm.config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC_PREFIX

logger = logging.getLogger(__name__)


class GraviThermMQTTClient:
    """Client MQTT wrapper cu suport pentru reconectare automată și formatare conform interfaces.py."""

    def __init__(
        self,
        client_id: str = "gravitherm_iot_client",
        host: str = MQTT_BROKER_HOST,
        port: int = MQTT_BROKER_PORT,
    ) -> None:
        """Inițializează conexiunea clientului MQTT.

        Parameters
        ----------
        client_id : str
            Identificatorul unic al clientului pe broker.
        host : str
            Adresa IP sau hostname-ul broker-ului Mosquitto (implicit localhost).
        port : int
            Portul broker-ului MQTT (implicit 1883).
        """
        self.client_id = client_id
        self.host = host
        self.port = port
        self.is_connected = False

        # Compatibilitate Paho-MQTT v1 & v2 API
        try:
            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
            )
        except AttributeError:
            self._client = mqtt.Client(client_id=client_id)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._message_callback: Callable[[str, dict[str, Any]], None] | None = None

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: Any,
        properties: Any = None,
    ) -> None:
        """Callback lansat la conectarea la broker."""
        if (isinstance(rc, int) and rc == 0) or getattr(rc, "is_failure", False) is False:
            self.is_connected = True
            logger.info("Conectat cu succes la broker-ul MQTT %s:%d", self.host, self.port)
            self._client.subscribe(f"{MQTT_TOPIC_PREFIX}/actuators/#")
        else:
            self.is_connected = False
            logger.warning("Conectare la broker-ul MQTT eșuată cu codul %s", str(rc))

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: Any = None,
        reason_code: Any = None,
        properties: Any = None,
    ) -> None:
        """Callback lansat la deconectarea accidentală de la broker."""
        self.is_connected = False
        logger.warning("Deconectat de la broker-ul MQTT. Se va încerca reconectarea...")

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Callback recepționare mesaj de pe un topic subscris."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            logger.debug("Mesaj primit pe topic %s: %s", msg.topic, payload)
            if self._message_callback is not None:
                self._message_callback(msg.topic, payload)
        except (json.JSONDecodeError, ValueError, TypeError) as err:
            logger.error("Eroare la procesarea mesajului de pe topic %s: %s", msg.topic, err)

    def connect(self) -> None:
        """Conectează clientul la broker și pornește bucla asincronă de rețea."""
        try:
            self._client.connect(self.host, self.port, keepalive=60)
            self._client.loop_start()
        except (OSError, RuntimeError, ValueError) as err:
            logger.warning("Nu s-a putut efectua conexiunea inițială la broker-ul MQTT: %s", err)

    def disconnect(self) -> None:
        """Oprește bucla de rețea și deconectează clientul."""
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except (OSError, RuntimeError):
            logger.debug("Deconectare curățată fără erori de rețea.")
        self.is_connected = False

    def publish_sensor_reading(
        self,
        topic_suffix: str,
        value: float,
        unit: str,
    ) -> None:
        """Publică o măsurătoare de senzor pe topicul gravitherm/sensors/{topic_suffix}.

        Parameters
        ----------
        topic_suffix : str
            Numele senzorului (ex: "temp1", "pressure").
        value : float
            Valoarea numerică măsurată.
        unit : str
            Unitatea de măsură ("C", "bar", "W").
        """
        topic = f"{MQTT_TOPIC_PREFIX}/sensors/{topic_suffix}"
        payload = json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "value": float(value),
                "unit": str(unit),
            }
        )
        try:
            self._client.publish(topic, payload, qos=0)
        except (OSError, RuntimeError, ValueError) as err:
            logger.error("Eroare la publicarea pe topic %s: %s", topic, err)

    def publish_actuator_state(
        self,
        actuator_name: str,
        payload_dict: dict[str, Any],
    ) -> None:
        """Publică starea unui actuator pe topicul gravitherm/actuators/{actuator_name}.

        Parameters
        ----------
        actuator_name : str
            Numele actuatorului (ex: "pump", "led").
        payload_dict : dict[str, Any]
            Dicționarul cu datele de telemetrie ale actuatorului.
        """
        topic = f"{MQTT_TOPIC_PREFIX}/actuators/{actuator_name}"
        if "timestamp" not in payload_dict:
            payload_dict["timestamp"] = datetime.now(UTC).isoformat()
        payload = json.dumps(payload_dict)
        try:
            self._client.publish(topic, payload, qos=0)
        except (OSError, RuntimeError, ValueError) as err:
            logger.error("Eroare la publicarea pe topic %s: %s", topic, err)

    def set_on_message_callback(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Setează funcția callback apeleată la primirea comenzilor pentru actuatoare."""
        self._message_callback = callback


# --- Funcții helper pentru compatibilitate cu codul existent ---


def make_client(client_id: str = "gravitherm_legacy_client") -> mqtt.Client:
    """Creează și conectează un client Paho MQTT simplu."""
    client = mqtt.Client(client_id=client_id)
    try:
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    except (OSError, RuntimeError) as err:
        logger.warning("Conectare directă paho eșuată: %s", err)
    return client


def publish_reading(client: mqtt.Client, topic_suffix: str, value: float, unit: str) -> None:
    """Publică o citire de senzor folosind o instanță Paho MQTT."""
    topic = f"{MQTT_TOPIC_PREFIX}/sensors/{topic_suffix}"
    payload = json.dumps(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "value": float(value),
            "unit": str(unit),
        }
    )
    client.publish(topic, payload)
