"""Modelul PPER — putere hidro-gravitationala recuperata (Ecuatia 2, propunere).

P_PPER = eta_turb * rho * g * Q * H

Formula e generica si valabila la orice scara - ce difera intre scenarii sunt
DOAR valorile H si Q introduse. Nu amestecati cele doua scenarii din
config.py (vezi docs/decisions.md pentru motivare completa):

1) Scenariul REAL (cladire de 20 etaje) - config.PIPE_HEAD_REAL_BUILDING_M
   si config.PIPE_FLOW_REAL_BUILDING_L_S. Folosit STRICT pentru extrapolarea
   analitica din raport (impact, ROI, CO2) - macheta NU reproduce fizic o
   coloana de 60-80m.

   Discrepanta gasita in documentul de propunere: exemplul numeric citat
   (Q=0.5 L/s, H=60m, eta=0.72 -> "~21W") NU corespunde formulei de mai sus -
   calculand exact, 0.72*1000*9.81*0.0005*60 = ~212W (de 10x mai mare).
   Valoarea de ~21W rezulta corect doar daca Q=0.05 L/s. Am ales Q=0.05 L/s
   ca valoare corecta (config.PIPE_FLOW_REAL_BUILDING_L_S) - motivare completa
   in docs/decisions.md (se potriveste cu intervalul "5-50W/turbina" si cu
   "150-400 Wh/zi" declarate in alta parte a propunerii; 212W nu s-ar
   incadra in niciunul din cele doua).

2) Scenariul de LABORATOR (macheta fizica) - config.PIPE_HEAD_LAB_M si
   config.PIPE_FLOW_LAB_L_S. Raman None pana se masoara/calibreaza fizic
   macheta (Faza II) - vezi pressure_to_flow_estimate_l_s() mai jos.

Vezi tests/test_simulation/test_pper_model.py.
"""

from gravitherm.config import GRAVITY_M_S2, WATER_DENSITY_KG_M3, TURBINE_EFFICIENCY


def pper_power_w(flow_rate_l_s: float, head_m: float, efficiency: float = TURBINE_EFFICIENCY) -> float:
    """Puterea electrica generata de o micro-turbina PAT.

    Args:
        flow_rate_l_s: debitul volumic Q, in litri/secunda.
        head_m: caderea hidraulica disponibila H, in metri.
        efficiency: randamentul turbinei (0.65-0.80 tipic pentru PAT comerciale).

    Returns:
        Puterea instantanee in Watt.
    """
    flow_rate_m3_s = flow_rate_l_s / 1000.0
    return efficiency * WATER_DENSITY_KG_M3 * GRAVITY_M_S2 * flow_rate_m3_s * head_m


def pressure_to_flow_estimate_l_s(pressure_bar: float, pipe_coefficient: float = 1.0) -> float:
    """Placeholder: estimeaza debitul de LABORATOR din presiunea citita de BMP280.

    TODO(Alexandra, Faza II): calibrati relatia presiune->debit cu masuratori
    reale din montajul de laborator (depinde de geometria tubului de 6mm si
    de inaltimea rezervor->iesire). Rezultatul calibrarii se salveaza in
    config.PIPE_FLOW_LAB_L_S / config.PIPE_HEAD_LAB_M - NU folositi valorile
    de la scenariul real (config.PIPE_*_REAL_BUILDING_*) ca aproximare aici,
    sunt scenarii complet diferite ca ordin de marime.
    """
    raise NotImplementedError("De calibrat cu montajul fizic de laborator (Faza II).")
