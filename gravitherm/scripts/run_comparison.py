"""Ruleaza un scenariu scurt baseline (ON/OFF) vs. agent RL si compara metrici.

Folosit in Faza III pentru validarea cantitativa (tinta: 10-18% reducere
consum fata de baseline). Poate rula fie complet simulat, fie cu hardware
real conectat (schimband sursa de Observation).
"""

import argparse


def run_baseline(duration_s: int) -> dict:
    """TODO(echipa): implementati controller ON/OFF simplu peste acelasi mediu."""
    raise NotImplementedError


def run_rl_agent(duration_s: int) -> dict:
    """TODO(echipa): implementati rulare cu agent/inference.py peste acelasi mediu."""
    raise NotImplementedError


def main():
    parser = argparse.ArgumentParser(description="Compara baseline ON/OFF vs. agent RL.")
    parser.add_argument("--duration", type=int, default=1800, help="Durata sesiunii, in secunde")
    args = parser.parse_args()

    baseline_metrics = run_baseline(args.duration)
    rl_metrics = run_rl_agent(args.duration)

    print("Baseline:", baseline_metrics)
    print("RL agent:", rl_metrics)


if __name__ == "__main__":
    main()
