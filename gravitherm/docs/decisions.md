# Jurnal de decizii

Format: 3-5 rânduri per sesiune/MVP — ce am decis, de ce, ce a rămas deschis. Scopul e ca oricine preia un modul (backup, sau chiar proprietarul după o pauză) să nu piardă timp reconstituind de ce lucrurile arată așa cum arată. Se completează de persoana care a luat decizia, în același PR sau imediat după.

## Șablon (copiați blocul de mai jos pentru fiecare decizie nouă)

```
## [MVP X] Titlu scurt al deciziei — 20YY-MM-DD, Nume

- Decizie:
- Motiv:
- Alternative luate în calcul:
- Ce rămâne deschis / de revizitat:
```

## [MVP0] Valoarea Q pentru scenariul REAL (extrapolare raport) — Alexandra

- Decizie: `config.PIPE_FLOW_REAL_BUILDING_L_S = 0.05` (nu 0.5, cum apărea literal în textul propunerii).
- Motiv: formula `P = η·ρ·g·Q·H` cu Q=0.5 L/s, H=60m, η=0.72 dă ~212W, nu ~21W cum scrie propunerea. Q=0.05 L/s e singura valoare care reproduce ~21W. În plus, 21W se încadrează în intervalul „5-50W/turbină" declarat separat în propunere, iar 212W nu; și 21W × 7-19h/zi dă exact intervalul „150-400 Wh/zi" declarat, pe când 212W ar cere sub 2h/zi de funcționare, ceea ce nu se potrivește cu ideea de recuperare continuă. Trei indicii independente, toate spre 0.05.
- Alternative luate în calcul: am luat în calcul și varianta ca „~21W" din text să fie typo pentru „~212W" (adică Q=0.5 e corect) — respinsă, pentru că ar necesita corectarea altor două cifre din propunere (intervalul 5-50W și producția 150-400 Wh/zi), în timp ce varianta aleasă corectează un singur număr.
- Ce rămâne deschis: dacă vreți certitudine completă, întrebați persoana care a calculat inițial exemplul din slide-uri ce a vrut să scrie. Până atunci, 0.05 L/s e valoarea folosită în cod (`pper_model.py`, `config.py`) și cea recomandată pentru corectarea slide-ului/raportului final.

## [MVP0→Faza II] H și Q pentru scenariul de LABORATOR — deschis, Alexandra

- Decizie: **nu s-a luat încă** — `config.PIPE_HEAD_LAB_M` și `config.PIPE_FLOW_LAB_L_S` rămân `None` intenționat.
- Motiv: valorile scenariului real (60-80m, 0.05 L/s) descriu o clădire de 20 etaje, NU macheta de laborator (rezervor + tub silicon 6mm + pompă mini DC). Cele două scenarii au roluri diferite — real = extrapolare pentru raport, laborator = ce se măsoară fizic — și nu trebuie amestecate (vezi `pper_model.py` pentru detalii).
- Alternative luate în calcul: am luat în calcul să punem o valoare „plauzibilă" acum, ca placeholder — respinsă, pentru că orice cifră inventată aici ar da o falsă senzație de precizie înainte să existe măsurătoarea reală.
- Ce rămâne deschis: măsurarea fizică a înălțimii rezervor→ieșire și calibrarea `pper_model.pressure_to_flow_estimate_l_s()` cu citiri reale de la BMP280, în Faza II (Săpt. 4-6), odată ce macheta fizică ajunge. Puterea rezultată la scară de laborator va fi probabil de ordinul miliwaților — normal, e o limitare deja recunoscută explicit în propunere.


## [MVP1] Agent RL — Adapter mediu, reward parametrizat și export ONNX — 2026-09-05, Alina

- Decizie: Crearea clasei `GraviThermAgentEnv` în `src/gravitherm/agent/env_adapter.py` ca wrapper Gymnasium în locul modificării fișierelor comune `interfaces.py` sau `simulation/env.py`. Parametrizarea funcției de recompensă prin `RewardWeights`.
- Motiv: Păstrează contractul strict între module (regula de bază a echipei). `GraviThermAgentEnv` convertește observațiile în `np.ndarray(shape=(6,), dtype=float32)` necesare pentru SB3 PPO și efectuează calculul recompensei multi-obiectiv.
- Alternative luate în calcul: Modificarea `Observation` în `interfaces.py` pentru adăugarea metodelor `to_array()` — respinsă pentru a evita atingerea fișierelor comune ale echipei fără o discuție prealabilă.
- Ce rămâne deschis: Tunarea fină a ponderilor de recompensă în Faza III pe baza datelor reale din instrumentarea IoT.


## [MVP2] Agent RL — Evaluare Baseline, algoritm SAC și comparare Faza I — 2026-09-05, Alina

- Decizie: Implementarea clasei `BaselineOnOffPolicy` în `agent/evaluation.py` și adăugarea suportului `continuous_actions=True` în `GraviThermAgentEnv` pentru antrenarea `train_sac.py`.
- Motiv: Faza I din propunere cere o comparație cantitativă între o politică clasică de termostat și agentul RL. Adăugarea acțiunilor continue permite antrenarea ambilor algoritmi (PPO și SAC) fără a afecta interfața `interfaces.py`.
- Alternative luate în calcul: Crearea unui nou mediu complet separat pentru SAC — respinsă pentru a evita duplicarea codului.
- Ce rămâne deschis: Calibrarea mai fină a agentului pe un orizont de antrenare mai lung (50.000+ pași) în Faza III.
## IoT Setup - Andreea
- Am verificat stack-ul Docker Compose si simulatorul de senzori.
