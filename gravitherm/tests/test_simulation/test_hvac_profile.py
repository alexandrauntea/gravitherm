import numpy as np

from gravitherm.simulation.hvac_profile import hvac_load_w


def test_hvac_load_deterministic_by_default():
    """Verifica daca profilul HVAC este 100% determinist cand noise_std=0.0."""
    load1 = hvac_load_w(hour_of_day=14.0)
    load2 = hvac_load_w(hour_of_day=14.0)
    assert load1 == load2, "Consumul trebuie sa fie identic pentru aceasi ora"
    assert load1 > 2000.0, "Varful termic la ora 14:00 trebuie sa corespunda unui consum ridicat"


def test_hvac_load_stochastic_with_noise():
    """Verifica adaugarea de zgomot stocastic cand noise_std > 0."""
    rng1 = np.random.default_rng(seed=42)
    rng2 = np.random.default_rng(seed=42)

    load_stochastic1 = hvac_load_w(hour_of_day=14.0, noise_std=100.0, rng=rng1)
    load_stochastic2 = hvac_load_w(hour_of_day=14.0, noise_std=100.0, rng=rng2)

    assert load_stochastic1 == load_stochastic2, "Seed-ul identic trebuie sa genereze acelasi zgomot"
    assert load_stochastic1 != hvac_load_w(
        hour_of_day=14.0, noise_std=0.0
    ), "Zkomotul trebuie sa modifice valoarea"


def test_hvac_load_is_non_negative():
    """Verifica factul ca sarcina HVAC nu este niciodata negativa."""
    load = hvac_load_w(hour_of_day=2.0, base_load_w=10.0, noise_std=1000.0)
    assert load >= 0.0
