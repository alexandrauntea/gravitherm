"""Citire presiune apei prin I2C de la senzorul BMP280.

Suporta atat libraria adafruit-circuitpython-bmp280 cat si smbus2,
cu mecanism de retry la erori de comunicatie I2C (OSError), conversie
din hPa/Pa in bar, validare a limitelor fizice plauzibile si formatare MQTT.
"""

import logging
import struct
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Constante de configurare I2C
DEFAULT_I2C_ADDRESS = 0x76  # SDO conectat la GND (implicit pentru BMP280)
SECONDARY_I2C_ADDRESS = 0x77  # SDO conectat la VDD
DEFAULT_I2C_BUS = 1

# Parametri de retry si limite fizice de presiune a apei
MAX_RETRIES = 3
RETRY_DELAY_S = 0.5
MIN_PRESSURE_BAR = 0.0
MAX_PRESSURE_BAR = 10.0

# Factori de conversie: 1 bar = 100 000 Pa = 1 000 hPa
PA_TO_BAR = 1.0 / 100_000.0
HPA_TO_BAR = 1.0 / 1_000.0

# Registre hardware BMP280 (pentru backend-ul smbus2)
BMP280_REG_CALIB = 0x88
BMP280_REG_CHIP_ID = 0xD0
BMP280_REG_RESET = 0xE0
BMP280_REG_STATUS = 0xF3
BMP280_REG_CTRL_MEAS = 0xF4
BMP280_REG_CONFIG = 0xF5
BMP280_REG_DATA = 0xF7

BMP280_VALID_CHIP_IDS = (0x58, 0x56, 0x57, 0x60)

# Incercare import adafruit-circuitpython-bmp280 si dependinte hardware
try:
    import adafruit_bmp280
    import board
    import busio

    HAS_ADAFRUIT_BMP280 = True
except ImportError:
    HAS_ADAFRUIT_BMP280 = False
    adafruit_bmp280 = None  # type: ignore[assignment]
    board = None  # type: ignore[assignment]
    busio = None  # type: ignore[assignment]

# Incercare import smbus2 ca alternativa usoara pe Linux/RPi
try:
    import smbus2

    HAS_SMBUS2 = True
except ImportError:
    HAS_SMBUS2 = False
    smbus2 = None  # type: ignore[assignment]


class BMP280Error(Exception):
    """Exceptie de baza pentru erorile senzorului BMP280."""


class BMP280NotFoundError(BMP280Error):
    """Aruncata cand senzorul nu este detectat pe magistrala I2C."""


class BMP280ReadError(BMP280Error):
    """Aruncata cand citirea esueaza sau valoarea e in afara limitelor fizice."""


@dataclass
class PressureReading:
    """Citire de presiune si temperatura optionala de la senzorul BMP280."""

    pressure_bar: float
    temperature_c: float | None = None

    def to_sensor_message(self) -> dict[str, Any]:
        """Formateaza citirea conform contractului MQTT standard definit in interfaces.py.

        Returns:
            dict cu campurile:
                - timestamp (ISO8601 UTC)
                - value (float rotunjit la 3 zecimale, in bar)
                - unit ("bar")
        """
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "value": round(self.pressure_bar, 3),
            "unit": "bar",
        }


class BMP280Sensor:
    """Driver I2C pentru citirea presiunii de la senzorul BMP280."""

    def __init__(
        self,
        i2c_address: int = DEFAULT_I2C_ADDRESS,
        bus_id: int = DEFAULT_I2C_BUS,
        min_pressure_bar: float = MIN_PRESSURE_BAR,
        max_pressure_bar: float = MAX_PRESSURE_BAR,
        device: Any | None = None,
        backend: str | None = None,
    ) -> None:
        """Initializeaza driverul BMP280.

        Args:
            i2c_address: Adresa I2C a senzorului (implicit 0x76 sau 0x77).
            bus_id: Numarul magistralei I2C (implicit 1 pentru /dev/i2c-1).
            min_pressure_bar: Limita fizica minima admisa (implicit 0.0 bar).
            max_pressure_bar: Limita fizica maxima admisa (implicit 10.0 bar).
            device: Dispozitiv I2C optional injectat direct (util pentru teste/mock).
            backend: Backend specific ('adafruit' sau 'smbus2'). Daca este None, se detecteaza automat.
        """
        self.i2c_address = i2c_address
        self.bus_id = bus_id
        self.min_pressure_bar = min_pressure_bar
        self.max_pressure_bar = max_pressure_bar
        self._device = device
        self._backend = backend

        # Auto-detectie backend daca device a fost injectat fara backend specificat
        if self._device is not None and self._backend is None:
            if hasattr(type(self._device), "read_i2c_block_data") or "read_i2c_block_data" in getattr(
                self._device, "__dict__", {}
            ):
                self._backend = "smbus2"
            elif hasattr(type(self._device), "pressure") or "pressure" in getattr(
                self._device, "__dict__", {}
            ):
                self._backend = "adafruit"

        # Coeficienti de calibrare pentru backend-ul smbus2
        self._dig_T1: int | None = None
        self._dig_T2: int | None = None
        self._dig_T3: int | None = None
        self._dig_P1: int | None = None
        self._dig_P2: int | None = None
        self._dig_P3: int | None = None
        self._dig_P4: int | None = None
        self._dig_P5: int | None = None
        self._dig_P6: int | None = None
        self._dig_P7: int | None = None
        self._dig_P8: int | None = None
        self._dig_P9: int | None = None

    def _init_hardware(self) -> Any:
        """Initializeaza conexiunea hardware I2C folosind backend-ul disponibil."""
        if self._device is not None:
            return self._device

        # 1. Incercam mai intai adafruit-circuitpython-bmp280
        if HAS_ADAFRUIT_BMP280 and board is not None and adafruit_bmp280 is not None:
            try:
                i2c = board.I2C()
                self._device = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=self.i2c_address)
                self._backend = "adafruit"
                logger.info(
                    "Senzor BMP280 initializat cu adafruit_bmp280 la adresa 0x%02X.",
                    self.i2c_address,
                )
                return self._device
            except (NotImplementedError, ValueError, OSError) as exc:
                logger.debug("Initializarea adafruit_bmp280 a esuat, incercam smbus2: %s", exc)

        # 2. Incercam fallback la smbus2
        if HAS_SMBUS2 and smbus2 is not None:
            try:
                bus = smbus2.SMBus(self.bus_id)
                self._device = bus
                self._backend = "smbus2"
                self._init_smbus2_sensor(bus)
                logger.info(
                    "Senzor BMP280 initializat cu smbus2 pe bus-ul %d la adresa 0x%02X.",
                    self.bus_id,
                    self.i2c_address,
                )
                return self._device
            except OSError as exc:
                logger.debug("Initializarea smbus2 a esuat: %s", exc)
                raise

        raise BMP280ReadError(
            "Nicio librarie I2C nu este disponibila sau functionala "
            "(instalati adafruit-circuitpython-bmp280 sau smbus2 pe Raspberry Pi)."
        )

    def _init_smbus2_sensor(self, bus: Any) -> None:
        """Verifica prezenta chip-ului si citeste calibrarea prin smbus2."""
        try:
            chip_id = bus.read_byte_data(self.i2c_address, BMP280_REG_CHIP_ID)
        except OSError as exc:
            raise BMP280NotFoundError(
                f"Senzorul nu raspunde la adresa I2C 0x{self.i2c_address:02X} pe bus-ul {self.bus_id}: {exc}"
            ) from exc

        if chip_id not in BMP280_VALID_CHIP_IDS:
            raise BMP280NotFoundError(
                f"Dispozitivul de la adresa 0x{self.i2c_address:02X} are chip ID 0x{chip_id:02X} "
                f"(asteptat: una din {tuple(hex(x) for x in BMP280_VALID_CHIP_IDS)})."
            )

        # Citim calibrarea din 24 octeti incepand de la 0x88
        calib = bus.read_i2c_block_data(self.i2c_address, BMP280_REG_CALIB, 24)
        (
            self._dig_T1,
            self._dig_T2,
            self._dig_T3,
            self._dig_P1,
            self._dig_P2,
            self._dig_P3,
            self._dig_P4,
            self._dig_P5,
            self._dig_P6,
            self._dig_P7,
            self._dig_P8,
            self._dig_P9,
        ) = struct.unpack("<HhhHhhhhhhhh", bytes(calib))

        # osrs_t x1, osrs_p x1, mod normal (0x27)
        bus.write_byte_data(self.i2c_address, BMP280_REG_CTRL_MEAS, 0x27)
        # standby 62.5ms, filtru x4 (0x08)
        bus.write_byte_data(self.i2c_address, BMP280_REG_CONFIG, 0x08)

    def _read_via_smbus(self, bus: Any) -> tuple[float, float]:
        """Efectueaza citirea directa si compensarea conform formulelor Bosch BMP280."""
        if self._dig_T1 is None:
            self._init_smbus2_sensor(bus)

        # Citim datele brute (6 octeti: F7..FC)
        data = bus.read_i2c_block_data(self.i2c_address, BMP280_REG_DATA, 6)
        raw_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)

        # Compensare temperatura (Bosch 3.11.3)
        var1 = ((raw_t / 16384.0) - (self._dig_T1 / 1024.0)) * (self._dig_T2 or 0)
        var2 = (((raw_t / 131072.0) - (self._dig_T1 / 8192.0)) ** 2) * (self._dig_T3 or 0)
        t_fine = var1 + var2
        temp_c = t_fine / 5120.0

        # Compensare presiune (Bosch 3.11.3)
        p_var1 = (t_fine / 2.0) - 64000.0
        p_var2 = p_var1 * p_var1 * ((self._dig_P6 or 0) / 32768.0)
        p_var2 = p_var2 + (p_var1 * (self._dig_P5 or 0) * 2.0)
        p_var2 = (p_var2 / 4.0) + ((self._dig_P4 or 0) * 65536.0)
        p_var1 = (
            (((self._dig_P3 or 0) * p_var1 * p_var1) / 524288.0) + ((self._dig_P2 or 0) * p_var1)
        ) / 524288.0
        p_var1 = (1.0 + (p_var1 / 32768.0)) * (self._dig_P1 or 1)

        if p_var1 == 0.0:
            raise BMP280ReadError("Eroare la compensarea presiunii: impartire la zero.")

        p = 1048576.0 - float(raw_p)
        p = (p - (p_var2 / 4096.0)) * 6250.0 / p_var1
        p_var1 = ((self._dig_P9 or 0) * p * p) / 2147483648.0
        p_var2 = (p * (self._dig_P8 or 0)) / 32768.0
        pressure_pa = p + ((p_var1 + p_var2 + (self._dig_P7 or 0)) / 16.0)

        pressure_bar = pressure_pa * PA_TO_BAR
        return pressure_bar, temp_c

    def _read_raw(self) -> tuple[float, float | None]:
        """Citeste valorile brute de la hardware-ul configurat."""
        device = self._init_hardware()

        if self._backend == "adafruit":
            pressure_hpa = float(device.pressure)
            temp_c = float(getattr(device, "temperature", 0.0))
            return pressure_hpa * HPA_TO_BAR, temp_c

        if self._backend == "smbus2":
            return self._read_via_smbus(device)

        if hasattr(device, "read_pressure_bar"):
            p_bar = float(device.read_pressure_bar())
            t_c = float(getattr(device, "temperature_c", 0.0))
            return p_bar, t_c

        # Auto-detectie pe baza structurii
        if hasattr(type(device), "read_i2c_block_data") or "read_i2c_block_data" in getattr(
            device, "__dict__", {}
        ):
            self._backend = "smbus2"
            return self._read_via_smbus(device)

        if hasattr(type(device), "pressure") or "pressure" in getattr(device, "__dict__", {}):
            self._backend = "adafruit"
            pressure_hpa = float(device.pressure)
            temp_c = float(getattr(device, "temperature", 0.0))
            return pressure_hpa * HPA_TO_BAR, temp_c

        raise BMP280ReadError(f"Dispozitiv I2C nesuportat: {type(device)}")

    def read_pressure(
        self,
        max_retries: int = MAX_RETRIES,
        retry_delay_s: float = RETRY_DELAY_S,
    ) -> PressureReading:
        """Citeste presiunea si temperatura senzorului cu mecanism de retry.

        Args:
            max_retries: Numarul maxim de incercari in caz de eroare I2C (OSError).
            retry_delay_s: Intervalul de asteptare intre reincercari (secunde).

        Returns:
            Obiect PressureReading continand presiunea in bar si temperatura in grade Celsius.

        Raises:
            BMP280ReadError: Daca citirea esueaza dupa epuizarea incercarilor sau valoarea
                e in afara limitelor fizice plauzibile [min_pressure_bar, max_pressure_bar].
        """
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                pressure_bar, temp_c = self._read_raw()
                if not (self.min_pressure_bar <= pressure_bar <= self.max_pressure_bar):
                    raise BMP280ReadError(
                        f"Presiunea masurata ({pressure_bar:.4f} bar) este in afara "
                        f"limitelor fizice plauzibile [{self.min_pressure_bar}, {self.max_pressure_bar}] bar."
                    )
                return PressureReading(pressure_bar=pressure_bar, temperature_c=temp_c)
            except OSError as exc:
                last_error = exc
                logger.warning(
                    "Incercarea %d/%d de comunicare I2C (adresa 0x%02X, bus %d) a esuat: %s",
                    attempt,
                    max_retries,
                    self.i2c_address,
                    self.bus_id,
                    exc,
                )
                if attempt < max_retries and retry_delay_s > 0:
                    time.sleep(retry_delay_s)

        raise BMP280ReadError(
            f"Nu s-a putut citi presiunea de la senzorul BMP280 (0x{self.i2c_address:02X}) "
            f"dupa {max_retries} incercari. Ultima eroare: {last_error}"
        ) from last_error

    def read_pressure_bar(
        self,
        max_retries: int = MAX_RETRIES,
        retry_delay_s: float = RETRY_DELAY_S,
    ) -> float:
        """Citeste presiunea apei direct in bar cu mecanism de retry si validare.

        Args:
            max_retries: Numarul maxim de incercari permise.
            retry_delay_s: Intervalul de asteptare intre reincercari (secunde).

        Returns:
            Presiunea apei ca float exprimat in bar.

        Raises:
            BMP280ReadError: Daca citirea esueaza sau valoarea depaseste limitele.
        """
        reading = self.read_pressure(max_retries=max_retries, retry_delay_s=retry_delay_s)
        return reading.pressure_bar

    def to_sensor_message(self, pressure_bar: float | None = None) -> dict[str, Any]:
        """Formateaza citirea conform contractului MQTT standard definit in interfaces.py.

        Args:
            pressure_bar: Valoarea optionala a presiunii. Daca este None, se efectueaza o citire.

        Returns:
            dict cu campurile:
                - timestamp (ISO8601 UTC)
                - value (float rotunjit la 3 zecimale, in bar)
                - unit ("bar")
        """
        val = self.read_pressure_bar() if pressure_bar is None else pressure_bar
        if not (self.min_pressure_bar <= val <= self.max_pressure_bar):
            raise BMP280ReadError(
                f"Presiunea specificata ({val:.4f} bar) este in afara "
                f"limitelor fizice plauzibile [{self.min_pressure_bar}, {self.max_pressure_bar}] bar."
            )
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "value": round(val, 3),
            "unit": "bar",
        }


def read_pressure(
    i2c_address: int = DEFAULT_I2C_ADDRESS,
    bus_id: int = DEFAULT_I2C_BUS,
    max_retries: int = MAX_RETRIES,
    retry_delay_s: float = RETRY_DELAY_S,
) -> PressureReading:
    """Functie utilitara de nivel inalt pentru citirea presiunii si temperaturii.

    Args:
        i2c_address: Adresa I2C (implicit 0x76).
        bus_id: Numarul magistralei I2C (implicit 1).
        max_retries: Numarul maxim de incercari in caz de eroare.
        retry_delay_s: Intervalul intre reincercari.

    Returns:
        Obiect PressureReading.
    """
    sensor = BMP280Sensor(i2c_address=i2c_address, bus_id=bus_id)
    return sensor.read_pressure(max_retries=max_retries, retry_delay_s=retry_delay_s)


def read_pressure_bar(
    i2c_address: int = DEFAULT_I2C_ADDRESS,
    bus_id: int = DEFAULT_I2C_BUS,
    max_retries: int = MAX_RETRIES,
    retry_delay_s: float = RETRY_DELAY_S,
) -> float:
    """Functie utilitara de nivel inalt pentru citirea presiunii in bar.

    Args:
        i2c_address: Adresa I2C (implicit 0x76).
        bus_id: Numarul magistralei I2C (implicit 1).
        max_retries: Numarul maxim de incercari in caz de eroare.
        retry_delay_s: Intervalul intre reincercari.

    Returns:
        Presiunea apei ca float exprimat in bar.
    """
    sensor = BMP280Sensor(i2c_address=i2c_address, bus_id=bus_id)
    return sensor.read_pressure_bar(max_retries=max_retries, retry_delay_s=retry_delay_s)
