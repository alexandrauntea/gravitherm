"""Script de test pentru verificarea stabilitarii pe termen lung a mediului GraviThermEnv.

Simuleaza 100.000 de pasi (echivalentul a ~70 de zile de operare continua)
cu zgomot stocastic ridicat (hvac_noise_std=100.0) si actiuni aleatorii / ON-OFF.
Verifica absenta erorilor numerice (NaN, Inf) si incadrarea in limite fizice.
"""

import time

import numpy as np

from gravitherm.simulation.env import GraviThermEnv
from scripts.baseline_onoff import on_off_controller


def test_simulation_stability(total_steps: int = 100_000, hvac_noise_std: float = 100.0):
    print("=== START TEST DE STABILITATE PE TERMEN LUNG (GraviThermEnv) ===")
    print(f"Total pasi de simulat: {total_steps}")
    print(f"Zgomot HVAC (std)    : {hvac_noise_std} W\n")

    env = GraviThermEnv(hvac_noise_std=hvac_noise_std)
    obs_dict, _ = env.reset(seed=42)

    pump_is_on = False
    temps = []
    powers = []
    nan_count = 0
    inf_count = 0

    start_time = time.time()

    for step_idx in range(1, total_steps + 1):
        temp_c = obs_dict["utl_temperature_c"]
        temps.append(temp_c)

        if step_idx % 2 == 0:
            action = int(env.action_space.sample())
        else:
            action = on_off_controller(current_temp_c=temp_c, pump_is_on=pump_is_on)

        pump_is_on = bool(action == 1)

        obs_dict, _reward, terminated, truncated, _info = env.step(action)
        powers.append(obs_dict["pper_power_w"])

        for key, val in obs_dict.items():
            if np.isnan(val):
                nan_count += 1
                print(f"[EROARE] NaN detectat la pasul {step_idx} pentru {key}")
            if np.isinf(val):
                inf_count += 1
                print(f"[EROARE] Inf detectat la pasul {step_idx} pentru {key}")

        if terminated or truncated:
            obs_dict, _ = env.reset()
            pump_is_on = False

    elapsed_sec = time.time() - start_time
    steps_per_sec = total_steps / elapsed_sec if elapsed_sec > 0 else 0

    min_temp = min(temps)
    max_temp = max(temps)
    avg_temp = sum(temps) / len(temps)
    max_power = max(powers)
    avg_power = sum(powers) / len(powers)

    print("=== REZULTATE TEST STABILITATE ===")
    print(f"Timp executie         : {elapsed_sec:.2f} secunde")
    print(f"Viteza simulare       : {steps_per_sec:.0f} pasi/secunda")
    print(f"Valori NaN detectate  : {nan_count}")
    print(f"Valori Inf detectate  : {inf_count}")
    print(f"Temperatura UTL min   : {min_temp:.2f} °C")
    print(f"Temperatura UTL max   : {max_temp:.2f} °C")
    print(f"Temperatura UTL medie : {avg_temp:.2f} °C")
    print(f"Putere PPER max       : {max_power:.2f} W")
    print(f"Putere PPER medie     : {avg_power:.2f} W")

    assert nan_count == 0, "Test eseat; s-au detectat valori NaN!"
    assert inf_count == 0, "Test eseat: s-au detectat valori Ind!"
    assert (
        5.0 <= min_temp <= max_temp <= 45.0
    ), f"Test eseat: temperatura a iesit din intervalul fizic safe [5°C, 45ÃJ]! ({min_temp:.2f} °C - {max_temp:.2f} °C)"

    print("\nTEST PASAT CU SUCCES! Mediul este 100% stabil pentru antrenare RL.")


if __name__ == "__main__":
    test_simulation_stability()
