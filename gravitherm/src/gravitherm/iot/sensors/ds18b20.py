"""Citire temperatura de la senzorii DS18B20 (1-Wire).

Suporta atat libraria w1thermsensor cat si citirea directa din
/sys/bus/w1/devices/<sensor_id>/w1_slave, cu mecanism de retry si tratare robusta a erorilor.
"""

import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_W1_PATH = Path("/sys/bus/w1/devices")
DS18B20_FAMILY_CODE = "28"
MAX_RETRIES = 3
RETRY_DELAY_S = 0.5

# Prevenim incarcarea kernel modules de catre w1thermsensor pe sisteme non-RPi / WSL
os.environ.setdefault("W1THERMSENSOR_NO_KERNEL_MODULE", "1")

# Incercam importul librariei w1thermsensor daca este disponibila
try:
    from w1thermsensor import Sensor, W1ThermSensor
    from w1thermsensor.errors import (
        KernelModuleLoadError,
        NoSensorFoundError,
        ResetValueError,
        SensorNotReadyError,
        W1ThermSensorError,
    )

    HAS_W1THERMSENSOR = True
except ImportError:
    HAS_W1THERMSENSOR = False
    W1ThermSensor = None  # type: ignore[assignment]
    Sensor = None  # type: ignore[assignment]
    W1ThermSensorError = Exception  # type: ignore[misc,assignment]
    SensorNotReadyError = Exception  # type: ignore[misc,assignment]
    ResetValueError = Exception  # type: ignore[misc,assignment]
    NoSensorFoundError = Exception  # type: ignore[misc,assignment]
    KernelModuleLoadError = Exception  # type: ignore[misc,assignment]


class DS18B20Error(Exception):
    """Exceptie de baza pentru erorile senzorului DS18B20."""


class SensorNotFoundError(DS18B20Error):
    """Aruncata cand senzorul specificat nu este gasit pe magistrala 1-Wire."""


class SensorReadError(DS18B20Error):
    """Aruncata cand citirea esueaza (CRC invalid, deconectare, valoare eronata)."""


@dataclass
class TemperatureReading:
    """Citire de temperatura de la un senzor DS18B20."""

    sensor_id: str
    temperature_c: float

    def to_sensor_message(self) -> dict[str, Any]:
        """Formateaza citirea conform contractului MQTT definit in interfaces.py.

        Returns:
            dict cu campurile:
                - timestamp (ISO8601 UTC)
                - value (float rotunjit la 3 zecimale, in grade Celsius)
                - unit ("celsius")
        """
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "value": round(self.temperature_c, 3),
            "unit": "celsius",
        }


class DS18B20Sensor:
    """Driver pentru citirea unui senzor individual DS18B20."""

    def __init__(self, sensor_id: str, w1_path: Path | str = DEFAULT_W1_PATH) -> None:
        """Initializeaza driverul DS18B20.

        Args:
            sensor_id: ID-ul senzorului (ex: '28-00000abc123' sau doar adresa '00000abc123').
            w1_path: Calea catre directorul dispozitivelor 1-Wire.
        """
        self.w1_path = Path(w1_path)
        self.sensor_id = (
            sensor_id
            if sensor_id.startswith(f"{DS18B20_FAMILY_CODE}-")
            else f"{DS18B20_FAMILY_CODE}-{sensor_id}"
        )
        self._raw_id = self.sensor_id.split("-", 1)[1] if "-" in self.sensor_id else self.sensor_id

    @property
    def device_file(self) -> Path:
        """Calea catre fisierul w1_slave din sysfs."""
        return self.w1_path / self.sensor_id / "w1_slave"

    def exists(self) -> bool:
        """Verifica daca senzorul este prezent pe magistrala."""
        return self.device_file.exists()

    def _read_sysfs(self) -> float:
        """Citeste si parseaza temperatura direct din fisierul w1_slave."""
        if not self.device_file.exists():
            raise SensorNotFoundError(f"Fisierul senzorului {self.sensor_id} nu exista: {self.device_file}")

        try:
            content = self.device_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SensorReadError(f"Eroare I/O la citirea {self.device_file}: {exc}") from exc

        lines = content.splitlines()
        if len(lines) < 2:
            raise SensorReadError(f"Date incomplete primite de la {self.sensor_id}: {content}")

        # Linia 1: verificare CRC (trebuie sa se termine cu 'YES')
        if not lines[0].strip().endswith("YES"):
            raise SensorReadError(f"Eroare CRC la senzorul {self.sensor_id}: {lines[0]}")

        # Linia 2: parsare valoare temperatura 't=XXXXX'
        match = re.search(r"t=(-?\d+)", lines[1])
        if not match:
            raise SensorReadError(f"Format temperatura invalid pe linia 2 ({self.sensor_id}): {lines[1]}")

        temp_c = int(match.group(1)) / 1000.0

        # DS18B20 returneaza 85.0 C la pornire/reset inainte ca conversia sa fie gata
        # si -127.0 C in cazul lipsei conexiunii de date/pull-up
        if temp_c == 85.0:
            raise SensorReadError(
                f"Senzorul {self.sensor_id} a returnat valoarea de power-on reset (85.0 C)."
            )
        if temp_c <= -127.0:
            raise SensorReadError(
                f"Senzorul {self.sensor_id} a returnat valoare invalida de deconectare ({temp_c} C)."
            )
        if temp_c < -55.0 or temp_c > 125.0:
            raise SensorReadError(
                f"Senzorul {self.sensor_id} a returnat temperatura in afara limitelor hardware ({temp_c} C)."
            )

        return temp_c

    def _read_w1thermsensor(self) -> float:
        """Citeste temperatura folosind libraria w1thermsensor."""
        if not HAS_W1THERMSENSOR or W1ThermSensor is None:
            raise RuntimeError("w1thermsensor nu este disponibila.")
        try:
            sensor = W1ThermSensor(sensor_id=self._raw_id)
            temp = float(sensor.get_temperature())
            if temp == 85.0 or temp <= -127.0 or temp < -55.0 or temp > 125.0:
                raise SensorReadError(
                    f"Valoare invalida citita de w1thermsensor pentru {self.sensor_id}: {temp} C"
                )
            return temp
        except NoSensorFoundError as exc:
            raise SensorNotFoundError(
                f"Senzorul {self.sensor_id} nu a fost gasit de w1thermsensor: {exc}"
            ) from exc
        except (W1ThermSensorError, SensorNotReadyError, ResetValueError) as exc:
            raise SensorReadError(f"Eroare w1thermsensor pentru {self.sensor_id}: {exc}") from exc
        except Exception as exc:
            raise SensorReadError(f"Eroare neasteptata w1thermsensor: {exc}") from exc

    def read_temperature(
        self,
        max_retries: int = MAX_RETRIES,
        retry_delay_s: float = RETRY_DELAY_S,
    ) -> float:
        """Citeste temperatura in grade Celsius cu mecanism de retry si fallback.

        Args:
            max_retries: Numarul maxim de incercari inainte de aruncarea erorii.
            retry_delay_s: Intervalul de asteptare intre reincercari (in secunde).

        Returns:
            Temperatura in grade Celsius ca float.

        Raises:
            SensorNotFoundError: Daca senzorul nu este prezent.
            SensorReadError: Daca citirea esueaza dupa toate reincercarile.
        """
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                if HAS_W1THERMSENSOR and self.w1_path == DEFAULT_W1_PATH:
                    try:
                        return self._read_w1thermsensor()
                    except (SensorReadError, RuntimeError) as exc:
                        logger.debug("Fallback de la w1thermsensor la citire sysfs: %s", exc)

                return self._read_sysfs()
            except SensorNotFoundError:
                raise
            except SensorReadError as exc:
                last_error = exc
                logger.warning(
                    "Incercarea %d/%d de citire a senzorului %s a esuat: %s",
                    attempt,
                    max_retries,
                    self.sensor_id,
                    exc,
                )
                if attempt < max_retries and retry_delay_s > 0:
                    time.sleep(retry_delay_s)

        raise SensorReadError(
            f"Nu s-a putut citi temperatura de la senzorul {self.sensor_id} "
            f"dupa {max_retries} incercari. Ultima eroare: {last_error}"
        ) from last_error


def get_available_sensors(w1_path: Path | str = DEFAULT_W1_PATH) -> list[str]:
    """Returneaza ID-urile tuturor senzorilor DS18B20 detectati pe magistrala 1-Wire.

    Args:
        w1_path: Calea catre directorul dispozitivelor 1-Wire.

    Returns:
        Lista de ID-uri ale senzorilor (ex: ['28-00000abc123']).
    """
    path = Path(w1_path)
    if not path.exists():
        return []

    return sorted([p.name for p in path.glob(f"{DS18B20_FAMILY_CODE}-*") if p.is_dir()])


def read_all_sensors(
    w1_path: Path | str = DEFAULT_W1_PATH,
    max_retries: int = MAX_RETRIES,
    retry_delay_s: float = RETRY_DELAY_S,
) -> list[TemperatureReading]:
    """Citeste toti senzorii DS18B20 conectati pe magistrala 1-Wire.

    Args:
        w1_path: Calea catre dispozitivele 1-Wire.
        max_retries: Numarul maxim de incercari per senzor.
        retry_delay_s: Timpul de asteptare intre reincercari.

    Returns:
        Lista de obiecte TemperatureReading pentru fiecare senzor detectat.

    Raises:
        SensorNotFoundError: Daca nu este detectat niciun senzor DS18B20 pe magistrala.
        SensorReadError: Daca un senzor detectat nu poate fi citit cu succes.
    """
    sensor_ids = get_available_sensors(w1_path=w1_path)
    if not sensor_ids:
        raise SensorNotFoundError(f"Niciun senzor DS18B20 (familia {DS18B20_FAMILY_CODE}) gasit in {w1_path}")

    readings: list[TemperatureReading] = []
    for sid in sensor_ids:
        sensor = DS18B20Sensor(sid, w1_path=w1_path)
        temp_c = sensor.read_temperature(max_retries=max_retries, retry_delay_s=retry_delay_s)
        readings.append(TemperatureReading(sensor_id=sid, temperature_c=temp_c))

    return readings


def read_temperature(
    sensor_id: str | None = None,
    w1_path: Path | str = DEFAULT_W1_PATH,
    max_retries: int = MAX_RETRIES,
    retry_delay_s: float = RETRY_DELAY_S,
) -> float:
    """Citeste temperatura de la un senzor specific sau de la primul senzor disponibil.

    Args:
        sensor_id: ID-ul senzorului dorit. Daca este None, se alege primul senzor detectat.
        w1_path: Calea catre dispozitivele 1-Wire.
        max_retries: Numar maxim de incercari.
        retry_delay_s: Timp de asteptare intre incercari.

    Returns:
        Temperatura masurata in grade Celsius.

    Raises:
        SensorNotFoundError: Daca senzorul specificat sau niciun senzor nu este gasit.
        SensorReadError: Daca citirea esueaza dupa epuizarea incercarilor.
    """
    if sensor_id is None:
        available = get_available_sensors(w1_path=w1_path)
        if not available:
            raise SensorNotFoundError(f"Niciun senzor DS18B20 disponibil in {w1_path}")
        sensor_id = available[0]

    sensor = DS18B20Sensor(sensor_id=sensor_id, w1_path=w1_path)
    return sensor.read_temperature(max_retries=max_retries, retry_delay_s=retry_delay_s)
