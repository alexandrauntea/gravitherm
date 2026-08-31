"""Teste care nu necesita hardware fizic - verifica doar contractul de date.

TODO(Andreea): adaugati teste cu un mock/broker MQTT local (ex. pornit in
Docker in CI) care verifica formatul mesajelor publicate de mqtt_client.py,
conform interfaces.py.
"""

from gravitherm.interfaces import Action, Observation


def test_observation_has_expected_fields():
    obs = Observation(
        utl_temperature_c=13.0,
        pper_pressure_bar=1.0,
        pper_power_w=20.0,
        hour_of_day=10.0,
        energy_price=0.3,
        hvac_load_w=1500.0,
    )
    assert obs.utl_temperature_c == 13.0


def test_action_defaults_are_sane():
    action = Action(pump_on=True, pump_speed_pct=100.0)
    assert 0.0 <= action.pump_speed_pct <= 100.0
