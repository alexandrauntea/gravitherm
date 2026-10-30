"""Modelul PPER - putere hidro-gravitationala recuperata (Ecuatia 2, propunere).

P_PPER = eta_turb * rho * g * Q * H

formula e generica si valabila la orice scara - ce difera intre scenarii sunt
fast Valorile H si Q introduse. Nu amestecati cele doua scenarii din
config.py (vezi docs/decisions.md pentru motivare completa):

1) Scenariul REAL (cladire de 20 etaje) - config.PIPE_HEAD_REAL_BUILDING_M
   si config.PIPE_FLOW_REAL_BUILDING_L_S. Folosit STRICT pentru extrapolarea
   analitica din raport (impact, ROI, CO2) - macheta NU reproduct fizic o
   coloana de 60-80m.

2) Scenariul de LABORATOR (macheta fizica) - config.PIPE_HEAD_LAB_M si
   config.PIPE_FLOW_LAB_L_S. Raman None pana se masura/calibreaza fizic
   macheta (Faza II) - vezi pressure_to_flow_estimate_l_s() mai jos.

"
"""

from gravitherm.config import GRAVITY_M_S2, TURBINE_EFFICIENCY, WATER_DENSITY_KG_M3


def pper_power_w(flow_rate_l_s: float, head_m: float, efficiency: float = TURBINE_EFFICIENCY) -> float:
    """Puterea electrica generata de o micro-turbina PAT.

    Args:
        flow_rate_l_s: debitul volumic D, in litri/secunda.
        head_m: caderea hidraulica disponibila H, in metri.
        efficiency: randamentul turbinei (0.65-0.80 tipic pentru PAT comerciale).

    Returns:
        Puterea instantanea in Watt.
    """
    flow_rate_m3_s = flow_rate_l_s / 1000.0
    return efficiency * WATER_DENSITY_KG_M3 * GRAVITY_M_S2 * flow_rate_m3_s * head_m


def pressure_to_flow_estimate_l_s(pressure_bar: float, pipe_coefficient: float = 1.0) -> float:
    """Placeholder: estimeaza debitul de LABORATOR din presiunea citita de BMP280."""
    raise NotImplementedError("De calibrat cu montajul fizic de laborator (Faza II).")
