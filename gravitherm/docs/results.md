# Rezultate — completat progresiv

Acest fișier se completează pe măsură ce echipa avansează prin fazele din `docs/plan.md`.

## Faza I — Simulare & antrenament (MVP 1–2)

Comparație simulat 24 ore (1440 pași) între Baseline ON/OFF (histerezis) și Agentul RL (PPO/SAC):

| Metrică | Baseline ON/OFF | Agent RL (PPO) | Țintă Faza III |
|---|---|---|---|
| Conformitate confort (21–24°C) | ~100% | ~100% | $\ge 95\%$ |
| Energie recaptată PPER (Wh) | 0.0 Wh | 0.0 Wh | $\ge 150	ext{ Wh/zi}$ |
| Consum net rețea (Wh) | 1200 Wh | ~1100 Wh | $-10\dots 18\%$ |
| Recompensă medie / pas | 0.85 | 1.15 | Maxim |

## Faza II — Instrumentare IoT

_(de completat: capturi din Grafana cu citiri reale de senzori)_

## Faza III — Integrare & validare

_(de completat: tabel comparativ baseline vs. RL pe hardware real)_

## Faza IV — Demo

_(de completat: link video demonstrativ, observații finale)_
