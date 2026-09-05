"""Functia de recompensa multi-obiectiv (Ecuatia 1, propunere).

R = +r_confort + r_recaptat + r_tarif - r_retea - r_dep

Vezi src/gravitherm/agent/AGENTS.md pentru semnificatia fiecarui termen.
"""

from dataclasses import dataclass

from gravitherm.config import COMFORT_TEMP_MAX_C, COMFORT_TEMP_MIN_C
from gravitherm.interfaces import Observation, RewardBreakdown


@dataclass
class RewardWeights:
    """Ponderile termenilor din funcția de recompensă multi-obiectiv."""

    w_comfort: float = 1.0
    w_recaptured: float = 0.05
    w_price: float = 0.2
    w_grid: float = 0.01
    w_discomfort: float = 0.1


def compute_reward(
    obs: Observation,
    grid_import_w: float,
    weights: RewardWeights | None = None,
) -> RewardBreakdown:
    """Calculeaza recompensa pentru o observatie data."""
    if weights is None:
        weights = RewardWeights()

    if COMFORT_TEMP_MIN_C <= obs.utl_temperature_c <= COMFORT_TEMP_MAX_C:
        comfort = weights.w_comfort * 1.0
        discomfort_penalty = 0.0
    else:
        comfort = 0.0
        deviation = min(
            abs(obs.utl_temperature_c - COMFORT_TEMP_MIN_C),
            abs(obs.utl_temperature_c - COMFORT_TEMP_MAX_C),
        )
        discomfort_penalty = weights.w_discomfort * deviation

    recaptured_energy_bonus = weights.w_recaptured * obs.pper_power_w
    price_bonus = weights.w_price * (1.0 - obs.energy_price)
    grid_penalty = weights.w_grid * max(grid_import_w, 0.0)

    return RewardBreakdown(
        comfort=comfort,
        recaptured_energy_bonus=recaptured_energy_bonus,
        price_bonus=price_bonus,
        grid_penalty=grid_penalty,
        discomfort_penalty=discomfort_penalty,
    )
