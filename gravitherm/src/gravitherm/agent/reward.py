"""Functia de recompensa multi-obiectiv (Ecuatia 1, propunere).

R = +r_confort + r_recaptat + r_tarif - r_retea - r_dep

Vezi src/gravitherm/agent/AGENTS.md pentru semnificatia fiecarui termen.
"""

from gravitherm.config import COMFORT_TEMP_MAX_C, COMFORT_TEMP_MIN_C
from gravitherm.interfaces import Observation, RewardBreakdown


def compute_reward(obs: Observation, grid_import_w: float) -> RewardBreakdown:
    """Calculeaza recompensa pentru o observatie data.

    TODO(Alina): confirmati ponderile relative ale termenilor (constante
    hardcodate mai jos) - probabil devin hiperparametri de tunat in Faza I.
    """
    if COMFORT_TEMP_MIN_C <= obs.utl_temperature_c <= COMFORT_TEMP_MAX_C:
        comfort = 1.0
        discomfort_penalty = 0.0
    else:
        comfort = 0.0
        deviation = min(abs(obs.utl_temperature_c - COMFORT_TEMP_MIN_C), abs(obs.utl_temperature_c - COMFORT_TEMP_MAX_C))
        discomfort_penalty = deviation * 0.1

    recaptured_energy_bonus = 0.05 * obs.pper_power_w
    price_bonus = (1.0 - obs.energy_price) * 0.2
    grid_penalty = 0.01 * max(grid_import_w, 0.0)

    return RewardBreakdown(
        comfort=comfort,
        recaptured_energy_bonus=recaptured_energy_bonus,
        price_bonus=price_bonus,
        grid_penalty=grid_penalty,
        discomfort_penalty=discomfort_penalty,
    )
