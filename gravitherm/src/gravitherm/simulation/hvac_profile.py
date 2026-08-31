"""Profilul de consum HVAC al cladirii simulate.

TODO(Alexandra): definiti impreuna cu Alina daca profilul e determinist
(curba fixa, buna pentru teste reproductibile) sau cu zgomot stocastic
(mai realist pentru antrenare RL robusta). Cele doua moduri pot coexista
printr-un parametru `seed`/`noise_std`.
"""

import numpy as np


def hvac_load_w(hour_of_day: float, base_load_w: float = 2000.0, noise_std: float = 0.0) -> float:
    """Consum HVAC estimat la o ora data, cu un varf simplu la orele calde.

    Placeholder simplu (sinusoida) - de rafinat cu date reale/EnergyPlus
    in etapele ulterioare (vezi docs/plan.md, imbunatatiri viitoare).
    """
    peak_factor = 1.0 + 0.5 * np.sin((hour_of_day - 14) / 24 * 2 * np.pi)
    load = base_load_w * max(peak_factor, 0.2)
    if noise_std > 0:
        load += np.random.normal(0, noise_std)
    return float(load)
