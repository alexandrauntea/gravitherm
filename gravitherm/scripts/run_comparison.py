import os
from pathlib import Path
from stable_baselines3 import PPO


from gravitherm.agent.env_adapter import obs_to_array
from gravitherm.config import COMFORT_TEMP_MAX_C, COMFORT_TEMP_MIN_C

from gravitherm.simulation.env import GraviThermEnv
from scripts.baseline_onoff import run_baseline_episode


def evaluate_ppo_episode(
    env: GraviThermEnv, model: PPO, num_steps: int = 1440
) -> list[dict]:
    obs_raw, _ = env.reset(seed=42)
    records = []


    for step_idx in range(num_steps):
        obs_arr = obs_to_array(obs_raw)
        action, _ = model.predict(obs_arr, deterministic=True)
        action = int(action)


        record = {
            "step": step_idx,
            "hour_of_day": obs_raw["hour_of_day"],
            "utl_temperature_c": obs_raw["utl_temperature_c"],
            "pper_pressure_bar": obs_raw["pper_pressure_bar"],
            "pper_power_w": obs_raw["pper_power_w"],
            "energy_price": obs_raw["energy_price"],
            "hvac_load_w": obs_raw["hvac_load_w"],
            "action": action,
        }
        records.append(record)


        obs_raw, _, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            break


    return records




def compute_metrics(records: list[dict]) -> dict:
    total_pper_wh = sum(r["pper_power_w"] for r in records) / 60.0
    avg_temp = sum(r["utl_temperature_c"] for r in records) / len(records)
    pump_on_pct = (
        sum(1 for r in records if r["action"] == 1) / len(records)
    ) * 100.0


    comfort_count = sum(
        1
        for r in records
        if COMFORT_TEMP_MIN_C <= r["utl_temperature_c"] <= COMFORT_TEMP_MAX_C
    )
    comfort_pct = (comfort_count / len(records)) * 100.0


    grid_cost = sum(
        max(0.0, r["hvac_load_w"] - r["pper_power_w"])
        * r["energy_price"]
        * (1.0 / 60.0)
        for r in records
    )


    return {
        "total_pper_wh": total_pper_wh,
        "avg_temp": avg_temp,
        "pump_on_pct": pump_on_pct,
        "comfort_pct": comfort_pct,
        "grid_cost": grid_cost,
    }



def main():
    model_path = Path("models/ppo_gravitherm.zip")
    if not model_path.exists():
        model_path = Path("models/ppo_gravitherm")


    env = GraviThermEnv()
    baseline_records = run_baseline_episode(env=env, num_steps=1440)
    baseline_metrics = compute_metrics(baseline_records)


    print("=== REZULTATE COMPARATIE BASELINE ON/OFF vs. RL PPO (24h) ===")


    if model_path.exists():
        model = PPO.load(model_path)
        env_rl = GraviThermEnv()
        rl_records = evaluate_ppo_episode(env=env_rl, model=model, num_steps=1440)
        rl_metrics = compute_metrics(rl_records)


        print("\n[RL Model incarcat cu succes din: %s]\n" % model_path)
        print("Metrica                      | Baseline ON/OFF  | RL PPO Agent")
        print("------------------------------+----------------+-------------")
        print(
            "Energie PPER generata (Wh)    | %15.2f | %12.2f"
            % (baseline_metrics["total_pper_wh"], rl_metrics["total_pper_wh"])
        )
        print(
            "Temperatura medie UTL` (C)    | %15.2f | %12.2f"
            % (baseline_metrics["avg_temp"], rl_metrics["avg_temp"])
        )
        print(
            "Comfort termic (21-24C) (%%)   | %15.1f | %12.1f"
            % (baseline_metrics["comfort_pct"], rl_metrics["comfort_pct"])
        )
        print(
            "Timp functionare pompa (%%)    | %15.1f | %12.1f"
            % (baseline_metrics["pump_on_pct"], rl_metrics["pump_on_pct"])
        )
        print(
            "Cost energie retea (norm)     | %15.2f | %12.2f"
            % (baseline_metrics["grid_cost"], rl_metrics["grid_cost"])
        )
    else:
        print("\n[Nota: Modelul RL nu a fost gasit la %s.]" % model_path)



if __name__ == "__main__":
    main()
