# AGENTS.md — context pentru orice AI assistant (Claude, Cursor, ChatGPT, Copilot etc.)

Acest fișier e citit automat de majoritatea coding assistant-elor (Claude Code, Cursor, Windsurf...) când lucrează în acest repo. Dacă folosești alt tool, copiază conținutul lui ca prompt de sistem / context la începutul conversației.

## Regula #0 — pune întrebări înainte să răspunzi

**Înainte să scrii cod, să propui o arhitectură sau să dai un răspuns tehnic ferm, verifică dacă cerința utilizatorului este complet clară.** Dacă lipsește oricare din următoarele, întreabă înainte de a continua, în loc să presupui:

- Unitățile de măsură ale unei mărimi fizice (ex: `H` e în metri sau în bar? `Q` e în L/s sau m³/h?).
- Formatul exact al unui mesaj/interfață care traversează granița dintre module (vezi `interfaces.py`) — nu schimba acest contract fără să spui explicit ce se schimbă și de ce.
- Dacă o cerință se referă la varianta **simulată** (fără hardware) sau la varianta **reală** (cu Raspberry Pi conectat) — comportamentul diferă.
- Dacă lipsesc valori numerice/parametri necesari pentru un calcul (ex. randamentul turbinei, adâncimea buclei) — nu inventa valori "plauzibile" fără să le marchezi clar ca presupunere și fără să întrebi dacă sunt corecte.
- Scopul exact al unei sarcini ambigue ("îmbunătățește dashboard-ul" — ce anume: performanță, aspect vizual, metrici noi?).

E de preferat să pui 1-2 întrebări scurte și țintite decât să implementezi ceva greșit care trebuie refăcut. Dacă cerința e clară și lipsesc doar detalii minore, poți face o presupunere rezonabilă — dar spune-o explicit ("presupun că X, spune-mi dacă nu").

## Ce este GraviTherm (context de proiect)

Proiect academic pentru TechChallenge by Honeywell 2026 (echipă de 3, Facultatea de Automatică și Calculatoare, UPB). Propunerea completă e în `docs/plan.md` și în docurile proiectului; pe scurt, sistemul propus (la scară reală, într-o clădire de birouri) are 3 subsisteme:

- **PPER (Pipe Pressure Energy Recovery)** — micro-turbine pe conductele de apă potabilă, recuperează energie din presiunea coloanei de apă: `P = η · ρ · g · Q · H`.
- **UTL (Underground Thermal Loop)** — buclă de apă gri îngropată la 5-8m, folosește temperatura constantă a solului (12-14°C) pentru răcire pasivă, modelată cu ecuația liniei-sursă infinite (ILS).
- **RLAEA (RL Agent Energy-Aware)** — agent de reinforcement learning (PPO → SAC) care controlează HVAC-ul cu o funcție de recompensă cu 5 termeni: confort + energie recaptată + tarif minim − penalizare rețea − penalizare disconfort.

**Ce construim noi acum e un prototip de laborator** care validează aceste idei la scară mică ("simulate-then-scale"): modele fizice în Python + un agent RL antrenat în simulare + hardware real (Raspberry Pi 4, senzori DS18B20/BMP280, pompă DC, LED RGB) + un pipeline de date (MQTT → InfluxDB → Grafana). Detalii complete: `docs/plan.md`.

## Arhitectură de cod (3 module + 1 contract comun)

```
src/gravitherm/
├── interfaces.py     # CONTRACTUL comun — nu se schimbă fără acordul echipei
├── config.py         # constante fizice, setpoint-uri
├── simulation/        # modele fizice (UTL, PPER, HVAC) + mediu Gymnasium
├── agent/              # funcție de recompensă, antrenare RL, export/inferență ONNX
├── iot/                # senzori, actuatoare, MQTT, InfluxDB, bucla RPi
└── dashboard/          # vizualizare Plotly/Dash
```

Fiecare modul are propriul `AGENTS.md` cu context specific — citește-l pe cel din folderul în care lucrezi, pe lângă acesta.

## Convenții de cod

- Python 3.11+, type hints peste tot unde e practic.
- Formatare cu `black`, linting cu `ruff` — rulează-le local înainte de commit (`black . && ruff check .`).
- Nu modifica fișiere din folderul altcuiva (`simulation/`, `agent/`, `iot/`) fără să anunți — vezi `CONTRIBUTING.md`.
- Orice funcție care implementează o ecuație din propunere trebuie să aibă în docstring formula și sursa (numărul ecuației din `docs/plan.md` sau din documentul de propunere).
- Testele merg în `tests/test_<modul>/`, oglindind structura din `src/gravitherm/`.

## Fișiere de citit înainte de a începe

1. `docs/plan.md` — planul tehnic complet (stack, MVP-uri, split de lucru, testare).
2. `CONTRIBUTING.md` — workflow de git (branch-uri, PR-uri, cum evităm conflictele).
3. `AGENTS.md` din modulul tău specific.
