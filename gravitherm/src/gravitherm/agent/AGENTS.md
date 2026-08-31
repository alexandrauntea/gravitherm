# AGENTS.md — modul `agent/` (proprietar: Alina)

Citește mai întâi `AGENTS.md` de la rădăcina repo-ului (regula #0 despre întrebări de clarificare se aplică la fel aici).

## Scopul acestui modul

Funcția de recompensă multi-obiectiv, antrenarea agentului RL (PPO inițial, SAC ca îmbunătățire ulterioară), și exportul/inferența modelului antrenat (ONNX) — cel care va rula pe Raspberry Pi în `iot/`.

## Fișiere și ce trebuie să facă fiecare

- `reward.py` — implementează cei 5 termeni: `R = +r_confort + r_recaptat + r_tarif − r_retea − r_dep`.
  - `r_confort`: maxim în intervalul 21–24°C, penalizare în afara lui.
  - `r_recaptat`: bonus pentru prioritizarea energiei din bufferul PPER local față de rețea.
  - `r_tarif`: bonus pentru pre-răcire când tariful orar e minim.
  - `r_retea`: penalizare pentru consum net din rețea.
  - `r_dep`: penalizare pentru deviație de la setpoint (disconfort).
- `train_ppo.py` — antrenează cu Stable-Baselines3 PPO peste mediul din `simulation/env.py`.
- `train_sac.py` — variantă SAC (etapă ulterioară, orizont lung/dinamică continuă), NU e blocantă pentru MVP-urile inițiale.
- `export_onnx.py` — exportă policy-ul antrenat ca model ONNX (~2MB țintă).
- `inference.py` — wrapper subțire peste `onnxruntime` care încarcă modelul și primește o observație, întoarce o acțiune. Acesta e singurul fișier din acest modul care rulează efectiv pe Raspberry Pi — trebuie să aibă dependențe minime (fără Stable-Baselines3, fără PyTorch complet, doar `onnxruntime`).

## Interfața pe care trebuie să o respecți

Inputul lui `reward()` și al `inference.py` trebuie să fie exact `Observation` din `../interfaces.py` — dacă `simulation/env.py` schimbă acest format, sincronizează-te cu Alexandra înainte de a actualiza aici.

## Ce să NU faci

- Nu modifica `simulation/` direct — dacă mediul nu-ți oferă o informație de care ai nevoie pentru reward, cere adăugarea ei în `interfaces.py` printr-o discuție cu Alexandra, nu o hack-ui local.
- Nu pune dependențe grele (torch, stable-baselines3) în `inference.py` — acel fișier trebuie să ruleze pe un Raspberry Pi 4 cu resurse limitate.

## Întrebări de pus înainte de a implementa ceva aici

- Ce interval de timp acoperă un episod de antrenare (o zi simulată? o săptămână)?
- Ponderile relative ale celor 5 termeni de recompensă sunt fixe sau hiperparametri de tunat?
- Modelul ONNX trebuie să suporte batch de 1 observație (inferență în timp real) — confirmă că nu se antrenează/exportă pentru batch mai mare.

## Testare

`tests/test_agent/` — teste pentru forma funcției de recompensă (valori la limite cunoscute) + un test scurt de "sanity" de antrenare (câteva sute de pași) care verifică doar că nu crapă, nu că a convers complet.
