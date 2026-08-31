from gravitherm.simulation.pper_model import pper_power_w


def test_pper_power_formula_is_correct():
    """Verifica formula P = eta*rho*g*Q*H direct (fara sa presupuna cifra din
    propunere, care pare sa aiba o eroare de zecimala - vezi docstring-ul
    din pper_model.py)."""
    power = pper_power_w(flow_rate_l_s=0.5, head_m=60.0, efficiency=0.72)
    expected = 0.72 * 1000 * 9.81 * 0.0005 * 60.0
    assert abs(power - expected) < 0.01


def test_pper_power_at_q_0_05_matches_proposal_example():
    """Daca Q=0.05 L/s (nu 0.5 L/s ca in text), rezultatul e ~21W, exact cifra
    citata in propunere - de confirmat cu echipa care e valoarea corecta."""
    power = pper_power_w(flow_rate_l_s=0.05, head_m=60.0, efficiency=0.72)
    assert 20.0 <= power <= 22.0
