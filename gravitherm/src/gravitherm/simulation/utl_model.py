"""Modelul UTL — schimb termic sol-apa, ecuatia liniei-sursa infinite (ILS).

T_sol(r, t) = T_undisturbed + (q_L / (4*pi*lambda_sol)) * E1(r^2 / (4*a_sol*t))

Vezi docs/plan.md sectiunea 1 si documentul de propunere, Ecuatia 4.
"""

from scipy.special import exp1

from gravitherm.config import SOIL_THERMAL_CONDUCTIVITY, SOIL_UNDISTURBED_TEMP_C


def soil_temperature_c(
    linear_heat_flux_w_m: float,
    radius_m: float,
    time_s: float,
    soil_diffusivity_m2_s: float,
    undisturbed_temp_c: float = SOIL_UNDISTURBED_TEMP_C,
    soil_conductivity: float = SOIL_THERMAL_CONDUCTIVITY,
) -> float:
    """Temperatura solului la distanta `radius_m` de bucla, dupa `time_s` secunde.

    Args:
        linear_heat_flux_w_m: q_L, fluxul termic liniar, W/m.
        radius_m: distanta radiala de la bucla, m.
        time_s: timpul scurs de la inceperea extractiei, s.
        soil_diffusivity_m2_s: difuzivitatea termica a solului, m^2/s.
        undisturbed_temp_c: temperatura neperturbata a solului (12-14C in RO).
        soil_conductivity: conductivitatea termica a solului, W/(m*K).

    Returns:
        Temperatura solului in grade Celsius.

    Nota fizica importanta (verificati impreuna, echipa): modelul ILS
    converge la T_undisturbed la t -> 0 (inceputul extractiei, solul inca
    neperturbat la raza r), NU la t -> infinit. Sub extractie constanta de
    caldura, temperatura solului se DEPARTEAZA logaritmic de T_undisturbed
    pe termen lung ("deriva termica") - fenomen real si documentat pentru
    bucle geotermale, relevant pentru dimensionarea UTL pe termen lung
    (a nu se folosi acest model naiv pentru a "dovedi" stabilitate pe
    perioade multi-anuale fara a discuta explicit deriva termica).
    """
    x = (radius_m ** 2) / (4 * soil_diffusivity_m2_s * time_s)
    return undisturbed_temp_c + (linear_heat_flux_w_m / (4 * 3.141592653589793 * soil_conductivity)) * exp1(x)
