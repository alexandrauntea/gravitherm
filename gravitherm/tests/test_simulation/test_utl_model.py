from gravitherm.simulation.utl_model import soil_temperature_c


def test_soil_temperature_starts_at_undisturbed():
    """La t foarte mic (inceputul extractiei), solul la raza r nu a fost inca
    perturbat -> temperatura trebuie sa fie foarte aproape de T_undisturbed.
    (Modelul ILS NU converge la T_undisturbed la t mare - vezi nota din
    utl_model.py despre deriva termica pe termen lung.)"""
    temp = soil_temperature_c(
        linear_heat_flux_w_m=10.0,
        radius_m=0.5,
        time_s=1e-3,
        soil_diffusivity_m2_s=1e-6,
        undisturbed_temp_c=13.0,
    )
    assert abs(temp - 13.0) < 0.1


def test_soil_temperature_drifts_over_long_term():
    """Sub extractie constanta, temperatura se departeaza de T_undisturbed
    pe termen lung - de documentat explicit in raport, nu de ignorat."""
    temp_long_term = soil_temperature_c(
        linear_heat_flux_w_m=10.0,
        radius_m=0.5,
        time_s=1e9,
        soil_diffusivity_m2_s=1e-6,
        undisturbed_temp_c=13.0,
    )
    assert temp_long_term > 13.0
