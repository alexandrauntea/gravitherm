# AGENTS.md — modul `simulation/` (proprietar: Alexandra)

Citește mai întâi `AGENTS.md` de la rădăcina repo-ului (regula #0 despre întrebări de clarificare se aplică la fel aici).

## Scopul acestui modul

Modelele fizice digitale ale sistemului GraviTherm, plus mediul de simulare (Gymnasium) peste care se antrenează agentul RL din `agent/`. Acest modul NU conține cod de RL și NU conține cod de hardware/IoT — doar fizică și matematică, în Python pur (NumPy/SciPy).

## Fișiere și ce trebuie să facă fiecare

- `utl_model.py` — implementează ecuația liniei-sursă infinite (ILS) pentru temperatura solului/buclei: `T_sol(r,t) = T_undisturbed + (q_L / 4πλ_sol) · E1(r² / 4·a_sol·t)`. Parametri tipici România: `λ_sol` 1.5–2.5 W/(m·K), `T_undisturbed` 12–14°C.
- `pper_model.py` — implementează `P_PPER = η_turb · ρ · g · Q · H`. Test de referință: Q=0.5 L/s, H=60m, η=0.72 → P≈21W.
- `hvac_profile.py` — profilul de consum HVAC al clădirii simulate (curbă zilnică/sezonieră, folosită ca "load" pe care agentul trebuie să-l gestioneze).
- `env.py` — mediu Gymnasium (`reset()`, `step(action)`) care combină cele 3 fișiere de mai sus într-o singură buclă de simulare. **Acesta e fișierul-graniță** — `observation_space` și `reward` trebuie să respecte exact ce e definit în `../interfaces.py`.

## Interfața pe care trebuie să o respecți (nu o schimba unilateral)

`env.step()` trebuie să întoarcă o observație cu exact câmpurile din `interfaces.py::Observation` (temperatură UTL, presiune PPER, oră curentă, tarif energie) — dacă adaugi/elimini un câmp, agentul din `agent/` se rupe silențios. Anunță echipa înainte de orice schimbare aici.

## Ce să NU faci

- Nu scrie cod de antrenare RL aici (asta e în `agent/`).
- Nu adăuga dependențe de hardware (RPi.GPIO, paho-mqtt) — modulul trebuie să ruleze identic pe orice laptop, fără hardware.

## Întrebări de pus înainte de a implementa ceva aici

- Ce unități are `H` (coloana de apă) — metri sau bar echivalent?
- Adâncimea buclei UTL e parametru fix sau configurabil per scenariu de test?
- Profilul HVAC trebuie să fie determinist (pentru reproducibilitate în teste) sau cu zgomot stocastic?

## Testare

`tests/test_simulation/` — teste pur numerice, fără mock-uri, fără hardware. Verifică ecuațiile pe cazuri cunoscute (vezi exemplul PPER de mai sus) și comportamentul la limită (ex. `T_sol → T_undisturbed` când `t → ∞`).
