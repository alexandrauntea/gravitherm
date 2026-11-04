"""Modelul de date hibride (senzori reali + scenariu simulat) și calculul metricilor.

Generează fluxul de date la ~2 Hz pentru dashboard:
- temperaturi hibride (baseline real DS18B20 + offset scenariu filtrat ordin 1);
- presiune și debit simulate hidraulic din starea pompei (BMP280 nefuncțional);
- putere PPER (machetă în mW vs. extrapolare clădire reală 60m în W);
- consum rețea și costuri: Agent RL vs. Control clasic (chiller);
- recompensă RL multi-obiectiv și jurnal decizii;
- publicare opțională MQTT conform contractului din interfaces.py.
"""

from __future__ import annotations

import collections
import json
import logging
import math
import random
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from gravitherm.agent.reward import RewardWeights, compute_reward
from gravitherm.demo.demo_config import DemoConfig
from gravitherm.demo.scenario import PhaseDefinition, get_electricity_tariff, get_simulated_targets
from gravitherm.interfaces import Observation
from gravitherm.simulation.pper_model import pper_power_w

logger = logging.getLogger("gravitherm.demo.data_model")


@dataclass
class TelemetryPoint:
    """Punct de telemetrie generat la fiecare pas al buclei demo."""

    timestamp_s: float
    sim_hour: float
    sim_time_str: str
    phase_id: int
    phase_name: str
    phase_decision: str

    # Temperaturi (°C)
    temp_ext: float
    temp_int_rl: float
    temp_int_classic: float
    temp_reservoir: float
    temp_utl_return: float
    temp_soil: float
    temp_hot_side: float | None

    # Hidraulică & PPER
    pressure_kpa: float
    flow_l_min: float
    power_pper_lab_mw: float
    power_pper_extrapolated_w: float
    energy_pper_wh: float
    energy_pper_real_kwh: float

    # Rețea & Costuri
    grid_power_rl_kw: float
    grid_power_classic_kw: float
    energy_grid_rl_kwh: float
    energy_grid_classic_kwh: float
    cost_grid_rl_lei: float
    cost_grid_classic_lei: float
    tariff_lei_kwh: float
    tariff_zone: str
    tariff_color: str

    # Stare actuatori
    pump_active: bool
    pump_speed_pct: float
    peltier_active: bool

    # Recompensă & Confort
    rl_reward_cumulative: float
    classic_reward_cumulative: float
    in_comfort_rl: bool
    in_comfort_classic: bool
    comfort_pct_rl: float
    comfort_pct_classic: float
    energy_savings_pct: float
    cost_savings_pct: float


class DataModel:
    """Motor de generare și agregare date hibride pentru Demo Live."""

    def __init__(self, config: DemoConfig | None = None, mock_mode: bool = False) -> None:
        self.cfg = config or DemoConfig()
        self.mock_mode = mock_mode
        self._lock = threading.RLock()

        # Buffer circular de istoric (păstrează toată ziua simulată, ~3600 puncte la 2 Hz)
        self.history: collections.deque[TelemetryPoint] = collections.deque(maxlen=4000)

        # Jurnal decizii agent (ultimele 10 evenimente)
        self.decision_log: collections.deque[str] = collections.deque(maxlen=15)
        self._last_logged_action: tuple[bool, bool, int] | None = None

        # Stări interne dinamice (filtre de ordin 1 și integratori)
        self._filtered_temp_int_rl: float = 21.8
        self._filtered_temp_int_classic: float = 22.0
        self._filtered_temp_ext: float = 8.0
        self._filtered_temp_reservoir: float = 22.0
        self._filtered_temp_utl_return: float = 20.0
        self._simulated_pressure_kpa: float = 0.0

        # Integratori sumativi
        self.cum_energy_pper_wh: float = 0.0
        self.cum_energy_pper_real_kwh: float = 0.0
        self.cum_energy_grid_rl_kwh: float = 0.0
        self.cum_energy_grid_classic_kwh: float = 0.0
        self.cum_cost_rl_lei: float = 0.0
        self.cum_cost_classic_lei: float = 0.0
        self.cum_reward_rl: float = 0.0
        self.cum_reward_classic: float = 0.0

        self.comfort_ticks_rl: int = 0
        self.comfort_ticks_classic: int = 0
        self.total_ticks: int = 0

        # Ponderi recompensă din agent/reward.py
        self._reward_weights = RewardWeights(
            w_comfort=1.0,
            w_recaptured=0.05,
            w_price=0.2,
            w_grid=0.01,
            w_discomfort=0.1,
        )

        # Citire senzori reali 1-Wire în thread separat
        self._real_temps: dict[str, float | None] = {"cold_side": None, "reservoir": None, "hot_side": None}
        self._baseline_real_reservoir: float | None = None
        self._real_sensor_thread_running: bool = True
        self._sensor_thread = threading.Thread(
            target=self._real_sensor_poll_loop,
            name="DS18B20PollLoop",
            daemon=True,
        )
        self._sensor_thread.start()

        # Client MQTT opțional
        self._mqtt_client: Any = None
        self._mqtt_connected: bool = False
        self._mqtt_warned: bool = False
        self._init_mqtt()

    def _init_mqtt(self) -> None:
        """Inițializează conexiunea MQTT opțională."""
        if not self.cfg.mqtt_enabled:
            return

        try:
            import paho.mqtt.client as mqtt

            if hasattr(mqtt, "CallbackAPIVersion"):
                self._mqtt_client = mqtt.Client(
                    mqtt.CallbackAPIVersion.VERSION2, client_id="gravitherm-demo-publisher"
                )
            else:
                self._mqtt_client = mqtt.Client(client_id="gravitherm-demo-publisher")

            def on_connect(*args: Any, **kwargs: Any) -> None:
                self._mqtt_connected = True
                logger.info("[MQTT] Conectat la broker-ul %s:%d", self.cfg.mqtt_host, self.cfg.mqtt_port)

            self._mqtt_client.on_connect = on_connect
            self._mqtt_client.connect_async(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=60)
            self._mqtt_client.loop_start()
        except Exception as exc:  # noqa: BLE001
            if not self._mqtt_warned:
                logger.info(
                    "[MQTT] Broker local nepornit (%s). Publicarea MQTT va fi ignorată fără eroare.",
                    exc,
                )
                self._mqtt_warned = True
            self._mqtt_connected = False

    def _real_sensor_poll_loop(self) -> None:
        """Buclă dedicată pentru citirea senzorilor DS18B20 (evită blocarea la ~750ms)."""
        while self._real_sensor_thread_running:
            if not self.mock_mode:
                try:
                    from gravitherm.iot.sensors.ds18b20 import read_mapped_temperatures

                    readings = read_mapped_temperatures(max_retries=1, retry_delay_s=0.1)
                    with self._lock:
                        self._real_temps = readings
                        res_temp = readings.get("reservoir")
                        if res_temp is not None and self._baseline_real_reservoir is None:
                            self._baseline_real_reservoir = res_temp
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Eroare interogare DS18B20: %s", exc)
            time.sleep(1.0)

    def reset(self) -> None:
        """Resetează istoricul și integratorii pentru un nou demo de la Faza 0."""
        with self._lock:
            self.history.clear()
            self.decision_log.clear()
            self._last_logged_action = None

            self._filtered_temp_int_rl = 21.8
            self._filtered_temp_int_classic = 22.0
            self._filtered_temp_ext = 8.0
            self._filtered_temp_reservoir = 22.0
            self._filtered_temp_utl_return = 20.0
            self._simulated_pressure_kpa = 0.0

            self.cum_energy_pper_wh = 0.0
            self.cum_energy_pper_real_kwh = 0.0
            self.cum_energy_grid_rl_kwh = 0.0
            self.cum_energy_grid_classic_kwh = 0.0
            self.cum_cost_rl_lei = 0.0
            self.cum_cost_classic_lei = 0.0
            self.cum_reward_rl = 0.0
            self.cum_reward_classic = 0.0

            self.comfort_ticks_rl = 0
            self.comfort_ticks_classic = 0
            self.total_ticks = 0

            self.log_decision("00:00 — SISTEM RESETAT · Pregătit pentru Faza 0")

    def log_decision(self, message: str) -> None:
        """Adaugă o intrare în jurnalul de decizii al agentului."""
        with self._lock:
            self.decision_log.append(message)
            logger.info("[AGENT DECISION] %s", message)

    def step(
        self,
        phase: PhaseDefinition,
        fraction_in_phase: float,
        wall_elapsed_in_phase: float,
        sim_hour: float,
        dt_s: float,
        actual_pump_on: bool,
        actual_pump_speed_pct: float,
        actual_peltier_on: bool,
    ) -> TelemetryPoint:
        """Calculează un nou punct de telemetrie la pasul curent."""
        with self._lock:
            self.total_ticks += 1
            targets = get_simulated_targets(
                phase=phase,
                fraction_in_phase=fraction_in_phase,
                wall_elapsed_in_phase=wall_elapsed_in_phase,
                config=self.cfg,
            )

            # Filtru ordin 1 pe pas discret: alpha = dt / (tau + dt)
            alpha_temp = dt_s / (self.cfg.temp_filter_tau_s + dt_s)
            noise = random.gauss(0, self.cfg.temp_noise_std_c)

            # 1. Temperaturi hibride
            # T exterior
            target_ext = float(targets["temp_ext"])
            self._filtered_temp_ext += alpha_temp * (target_ext - self._filtered_temp_ext)
            t_ext = self._filtered_temp_ext + noise

            # T interior RL
            target_int_rl = float(targets["temp_int_rl"])
            self._filtered_temp_int_rl += alpha_temp * (target_int_rl - self._filtered_temp_int_rl)
            # Constrângere fermă: în intervalul de confort 21.0 - 24.0°C
            t_int_rl = max(
                self.cfg.comfort_min_c, min(self.cfg.comfort_max_c, self._filtered_temp_int_rl + noise)
            )

            # T interior Clasic
            target_int_classic = float(targets["temp_int_classic"])
            self._filtered_temp_int_classic += alpha_temp * (
                target_int_classic - self._filtered_temp_int_classic
            )
            t_int_classic = self._filtered_temp_int_classic + noise

            # T Sol UTL
            t_soil = float(targets["temp_soil"])

            # T Apă rezervor și T retur UTL (Hibrid)
            real_res = self._real_temps.get("reservoir")
            if real_res is not None and self._baseline_real_reservoir is not None:
                real_delta = real_res - self._baseline_real_reservoir
            else:
                real_delta = 0.0

            # Ținta rezervor: scade ușor când UTL e activ
            target_res = 22.0 + real_delta + (0.5 if actual_pump_on else 0.0)
            self._filtered_temp_reservoir += alpha_temp * (target_res - self._filtered_temp_reservoir)
            t_reservoir = self._filtered_temp_reservoir + noise

            # T retur UTL: scade cu 2-4°C față de rezervor când pompa și Peltierul merg
            utl_drop = 3.2 if (actual_pump_on and actual_peltier_on) else (1.0 if actual_pump_on else 0.0)
            target_retur = t_reservoir - utl_drop
            self._filtered_temp_utl_return += alpha_temp * (target_retur - self._filtered_temp_utl_return)
            t_utl_return = self._filtered_temp_utl_return + noise

            t_hot_side = self._real_temps.get("hot_side")

            # 2. Dinamica presiunii pe coloană (BMP280 defect -> simulare hidraulică)
            tau_press = (
                self.cfg.pipe_pressure_tau_rise_s if actual_pump_on else self.cfg.pipe_pressure_tau_fall_s
            )
            alpha_press = dt_s / (tau_press + dt_s)
            target_press = (
                (actual_pump_speed_pct / 100.0) * self.cfg.pipe_pressure_max_kpa if actual_pump_on else 0.0
            )
            self._simulated_pressure_kpa += alpha_press * (target_press - self._simulated_pressure_kpa)

            ripple = random.uniform(-self.cfg.pipe_pressure_ripple_kpa, self.cfg.pipe_pressure_ripple_kpa)
            p_kpa = max(0.0, self._simulated_pressure_kpa + (ripple if actual_pump_on else 0.0))

            # 3. Debit & Putere PPER
            if p_kpa > 0.5:
                # Debit de tip rădăcină pătrată din presiune
                flow_l_min = self.cfg.lab_flow_nominal_l_min * math.sqrt(
                    p_kpa / self.cfg.pipe_pressure_max_kpa
                )
            else:
                flow_l_min = 0.0

            # Putere pe machetă (mW)
            flow_l_s = flow_l_min / 60.0
            p_lab_w = pper_power_w(
                flow_rate_l_s=flow_l_s,
                head_m=self.cfg.lab_head_m,
                efficiency=self.cfg.turbine_efficiency,
            )
            power_pper_lab_mw = p_lab_w * 1000.0

            # Putere extrapolat la clădire reală (W) — formula confirmată în decisions.md
            if actual_pump_on:
                power_pper_extrapolated_w = pper_power_w(
                    flow_rate_l_s=self.cfg.building_flow_l_s,
                    head_m=self.cfg.building_head_m,
                    efficiency=self.cfg.turbine_efficiency,
                )
            else:
                power_pper_extrapolated_w = 0.0

            # Integrare energie recuperată pe orele simulate (sim_dt_h)
            # Clădire reală 21W x ~10-12h pompă activă dă ~210-250 Wh/zi (0.21-0.25 kWh/zi),
            # conform deciziei documentate în docs/decisions.md (150-400 Wh/zi).
            phase_hours = max(phase.end_hour - phase.start_hour, 0.001)
            sim_dt_h = (phase_hours / max(phase.duration_s, 0.1)) * dt_s if phase.duration_s > 0 else 0.0

            if actual_pump_on:
                self.cum_energy_pper_wh += p_lab_w * sim_dt_h
                self.cum_energy_pper_real_kwh += (power_pper_extrapolated_w / 1000.0) * sim_dt_h

            # 4. Consum din rețea și costuri
            tariff_lei, tariff_zone, tariff_color = get_electricity_tariff(sim_hour, config=self.cfg)
            grid_rl_kw = float(targets["grid_rl_kw"])
            grid_classic_kw = float(targets["grid_classic_kw"])

            energy_step_rl_kwh = grid_rl_kw * sim_dt_h
            energy_step_classic_kwh = grid_classic_kw * sim_dt_h

            self.cum_energy_grid_rl_kwh += energy_step_rl_kwh
            self.cum_energy_grid_classic_kwh += energy_step_classic_kwh

            self.cum_cost_rl_lei += energy_step_rl_kwh * tariff_lei
            self.cum_cost_classic_lei += energy_step_classic_kwh * tariff_lei

            # 5. Recompensă RL (folosind compute_reward din agent/reward.py)
            obs_rl = Observation(
                utl_temperature_c=t_int_rl,
                pper_pressure_bar=p_kpa / 100.0,
                pper_power_w=power_pper_extrapolated_w,
                hour_of_day=sim_hour,
                energy_price=min(tariff_lei / 1.70, 1.0),
                hvac_load_w=grid_rl_kw * 1000.0,
            )
            obs_classic = Observation(
                utl_temperature_c=t_int_classic,
                pper_pressure_bar=0.0,
                pper_power_w=0.0,
                hour_of_day=sim_hour,
                energy_price=min(tariff_lei / 1.70, 1.0),
                hvac_load_w=grid_classic_kw * 1000.0,
            )

            rew_rl = compute_reward(
                obs=obs_rl, grid_import_w=grid_rl_kw * 1000.0, weights=self._reward_weights
            )
            rew_classic = compute_reward(
                obs=obs_classic,
                grid_import_w=grid_classic_kw * 1000.0,
                weights=self._reward_weights,
            )

            self.cum_reward_rl += rew_rl.total * 0.1
            self.cum_reward_classic += rew_classic.total * 0.1

            # 6. Confort
            in_comfort_rl = self.cfg.comfort_min_c <= t_int_rl <= self.cfg.comfort_max_c
            in_comfort_classic = self.cfg.comfort_min_c <= t_int_classic <= self.cfg.comfort_max_c

            if in_comfort_rl:
                self.comfort_ticks_rl += 1
            if in_comfort_classic:
                self.comfort_ticks_classic += 1

            comfort_pct_rl = (self.comfort_ticks_rl / self.total_ticks) * 100.0
            comfort_pct_classic = (self.comfort_ticks_classic / self.total_ticks) * 100.0

            # 7. Economii procentuale
            if self.cum_energy_grid_classic_kwh > 0.01:
                energy_savings_pct = (
                    (self.cum_energy_grid_classic_kwh - self.cum_energy_grid_rl_kwh)
                    / self.cum_energy_grid_classic_kwh
                ) * 100.0
            else:
                energy_savings_pct = 0.0

            if self.cum_cost_classic_lei > 0.01:
                cost_savings_pct = (
                    (self.cum_cost_classic_lei - self.cum_cost_rl_lei) / self.cum_cost_classic_lei
                ) * 100.0
            else:
                cost_savings_pct = 0.0

            # Formatare oră simulată HH:MM
            h_int = int(sim_hour)
            m_int = int((sim_hour - h_int) * 60)
            if h_int >= 24:
                sim_time_str = "24:00"
            else:
                sim_time_str = f"{h_int:02d}:{m_int:02d}"

            # Verificare jurnalizare eveniment decizie agent
            curr_action = (actual_pump_on, actual_peltier_on, phase.phase_id)
            if curr_action != self._last_logged_action:
                self._last_logged_action = curr_action
                if phase.phase_id == 0:
                    tariff_str = (
                        f"Tarif fix ({tariff_lei:.2f} lei)"
                        if self.cfg.fixed_tariff_enabled
                        else "Tarif ieftin (0.45 lei)"
                    )
                    self.log_decision(f"{sim_time_str} — PRE-RĂCIRE UTL · {tariff_str} · Pompă oprită")
                elif phase.phase_id == 1:
                    self.log_decision(
                        f"{sim_time_str} — CERERE APĂ ↑ · Pompă activă · Recuperare PPER pornită"
                    )
                elif phase.phase_id == 2:
                    self.log_decision(
                        f"{sim_time_str} — CANICULĂ 34°C · Recirculare pasivă UTL activă · Chiller evitat"
                    )
                elif phase.phase_id == 3:
                    desc_peak = "VÂRF DE CONSUM" if self.cfg.fixed_tariff_enabled else "VÂRF TARIF (1.70 lei)"
                    if actual_pump_on:
                        self.log_decision(f"{sim_time_str} — {desc_peak} · Impuls PPER activat · LED aprins")
                    else:
                        self.log_decision(
                            f"{sim_time_str} — {desc_peak} · Pauză impuls (4s) · Minimizare rețea"
                        )
                elif phase.phase_id == 4:
                    self.log_decision(f"{sim_time_str} — SEARĂ · Clădire neocupată · Trecere în standby")
                elif phase.phase_id == 5:
                    self.log_decision(f"{sim_time_str} — SUMAR · 24h finalizate cu succes · Date validate")

            point = TelemetryPoint(
                timestamp_s=time.time(),
                sim_hour=sim_hour,
                sim_time_str=sim_time_str,
                phase_id=phase.phase_id,
                phase_name=phase.name,
                phase_decision=phase.decision_text,
                temp_ext=t_ext,
                temp_int_rl=t_int_rl,
                temp_int_classic=t_int_classic,
                temp_reservoir=t_reservoir,
                temp_utl_return=t_utl_return,
                temp_soil=t_soil,
                temp_hot_side=t_hot_side,
                pressure_kpa=p_kpa,
                flow_l_min=flow_l_min,
                power_pper_lab_mw=power_pper_lab_mw,
                power_pper_extrapolated_w=power_pper_extrapolated_w,
                energy_pper_wh=self.cum_energy_pper_wh,
                energy_pper_real_kwh=self.cum_energy_pper_real_kwh,
                grid_power_rl_kw=grid_rl_kw,
                grid_power_classic_kw=grid_classic_kw,
                energy_grid_rl_kwh=self.cum_energy_grid_rl_kwh,
                energy_grid_classic_kwh=self.cum_energy_grid_classic_kwh,
                cost_grid_rl_lei=self.cum_cost_rl_lei,
                cost_grid_classic_lei=self.cum_cost_classic_lei,
                tariff_lei_kwh=tariff_lei,
                tariff_zone=tariff_zone,
                tariff_color=tariff_color,
                pump_active=actual_pump_on,
                pump_speed_pct=actual_pump_speed_pct,
                peltier_active=actual_peltier_on,
                rl_reward_cumulative=self.cum_reward_rl,
                classic_reward_cumulative=self.cum_reward_classic,
                in_comfort_rl=in_comfort_rl,
                in_comfort_classic=in_comfort_classic,
                comfort_pct_rl=comfort_pct_rl,
                comfort_pct_classic=comfort_pct_classic,
                energy_savings_pct=energy_savings_pct,
                cost_savings_pct=cost_savings_pct,
            )

            self.history.append(point)
            self._publish_mqtt(point)
            return point

    def _publish_mqtt(self, pt: TelemetryPoint) -> None:
        """Publică telemetria pe MQTT dacă broker-ul este activ."""
        if not self._mqtt_connected or self._mqtt_client is None:
            return

        try:
            iso_now = datetime.now(UTC).isoformat()
            prefix = self.cfg.mqtt_prefix

            def pub(topic: str, val: float, unit: str) -> None:
                payload = json.dumps({"timestamp": iso_now, "value": round(val, 3), "unit": unit})
                self._mqtt_client.publish(f"{prefix}/{topic}", payload)

            pub("sensors/temp1", pt.temp_reservoir, "celsius")
            pub("sensors/temp2", pt.temp_utl_return, "celsius")
            pub("sensors/temp3", pt.temp_ext, "celsius")
            pub("sensors/pressure", pt.pressure_kpa / 100.0, "bar")
            pub("actuators/pump", 1.0 if pt.pump_active else 0.0, "bool")
            pub("actuators/led", 1.0 if pt.pump_active else 0.0, "bool")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Eroare publicare telemetrie MQTT: %s", exc)

    def get_summary_metrics(self) -> dict[str, Any]:
        """Generează cifrele finale de performanță pentru ecranul de sumar din Faza 5."""
        with self._lock:
            if not self.history:
                return {}

            last = self.history[-1]
            co2_avoided_kg_day = (
                max(0.0, last.energy_grid_classic_kwh - last.energy_grid_rl_kwh)
                * self.cfg.building_co2_kg_kwh
            )
            co2_avoided_kg_year = co2_avoided_kg_day * 365.0
            cost_saved_lei_day = max(0.0, last.cost_grid_classic_lei - last.cost_grid_rl_lei)
            cost_saved_lei_year = cost_saved_lei_day * 365.0

            return {
                "energy_pper_lab_wh": round(last.energy_pper_wh, 2),
                "energy_pper_real_kwh_day": round(last.energy_pper_real_kwh, 2),
                "energy_savings_pct": round(last.energy_savings_pct, 1),
                "cost_savings_pct": round(last.cost_savings_pct, 1),
                "cost_saved_lei_day": round(cost_saved_lei_day, 2),
                "cost_saved_lei_year": round(cost_saved_lei_year, 0),
                "co2_avoided_kg_year": round(co2_avoided_kg_year, 1),
                "comfort_pct_rl": round(last.comfort_pct_rl, 1),
                "comfort_pct_classic": round(last.comfort_pct_classic, 1),
            }

    def close(self) -> None:
        """Eliberează resursele de fundal."""
        self._real_sensor_thread_running = False
        if self._mqtt_client is not None:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Eroare deconectare MQTT: %s", exc)
