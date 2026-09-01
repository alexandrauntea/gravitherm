"""Profilul de consum HVAC al cladirii simulate.

Implementeaza o curba de consum HVAC zilnica (varf termic dupa-amiatza la ora 14:00).
Suporta atat modul determinist (noise_std=0.0, ideal pentru teste reproductibile si demo live),
cat si modul stocastic (noise_std > 0, util pentru antrenare RL robusta).
"""

import numpy as np


def hvac_load_w(
    hour_of_day: float,
    base_load_w: float = 2000.0,
    noise_std: float = 0.0,
    rng: np.random.Generator | None = None,
) -> float:
    """Consum HVAC estimat la o ora data, cu un varf simplu la orele calde.

    Formula de baza:
        P_HVAC = P_base * max(1.0 + 0.5 * sin((ora - 8)/24 * 2*pi), 0.2) + N(0, noise_std)

    Args:
        hour_of_day: Ora din zi (0.0 - 23.99).
        base_load_w: Consumul de baza in W (implicit 2000W).
        noise_std: Deviatia standard a zwomotului gaussian adaugat (implicit 0.0 = determinist).
        rng: Generator NumPy optional pentru reproductibilitate stocastica.

    Returns:
        Consumul HVAC instantaneu estimat in Watt.
    """
    peak_factor = 1.0 + 0.5 * np.sin((hour_of_day - 8.0) / 24.0 * 2.0 * np.pi)
    load = base_load_w * max(peak_factor, 0.2)
    if noise_std > 0:
        if rng is not None:
            noise = float(rng.normal(0, noise_std))
        else:
            noise = float(np.random.normal(0, noise_std))
        load += noise
    return float(max(load, 0.0))
