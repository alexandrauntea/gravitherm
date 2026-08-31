# GraviTherm — Plan tehnic de implementare (prototip TechChallenge Honeywell 2026)

Echipă: **Alexandra** (Untea Alexandra-Nicoleta), **Alina** (Râncă Alina-Maria), **Andreea** (Ionescu Andreea).
Document de referință pentru tot ce ține de cod: ce construim, cu ce stack, cum împărțim munca pe fișiere separate ca să nu ne batem pe merge-uri, cum testăm și cum arată repo-ul.

---

## 1. Ce trebuie să facă sistemul (recapitulare din propunere)

Prototipul de laborator simulează, la scară redusă, cele 3 subsisteme din propunere:

1. **PPER (Pipe Pressure Energy Recovery)** — model al puterii generate de o micro-turbină PAT pe baza presiunii apei: `P = η · ρ · g · Q · H`. În laborator nu avem turbină reală — modelăm matematic puterea pe baza presiunii citite de senzorul BMP280.
2. **UTL (Underground Thermal Loop)** — model termic al schimbului de căldură sol–apă, bazat pe ecuația liniei-sursă infinite (ILS). Calibrat cu citirile celor 3 senzori DS18B20.
3. **RLAEA (RL Agent Energy-Aware)** — un agent de reinforcement learning (PPO inițial, SAC ca îmbunătățire ulterioară) care decide când pornește/oprește pompa DC, pe baza unei funcții de recompensă cu 5 termeni: confort termic + energie recaptată prioritizată + preț orar minim − penalizare rețea − penalizare disconfort.

Trei bucăți de cod separate, cu o interfață comună (mediul de simulare / semnalele de senzori), plus un pipeline IoT (senzori → MQTT → InfluxDB → Grafana) și un dashboard care arată agentul RL vs. un baseline ON/OFF.

**Concluzie practică:** codul se împarte natural în 3 pachete Python independente + un dashboard comun + o infrastructură de date comună. Asta ne dă exact separarea pe fișiere de care avem nevoie ca să lucrăm în paralel fără conflicte.

---

## 2. Cine scrie ce (split pe module, nu pe zile)

Ideea centrală: **fiecare persoană deține un folder**, nu un set de zile din calendar. Așa, doi oameni nu editează niciodată același fișier în același timp. Codul comun (interfețele) se scrie o singură dată, împreună, în prima săptămână, și apoi se schimbă rar.

| Persoană | Modul deținut | Folder | Ce conține |
|---|---|---|---|
| **Alexandra** | Simulare fizică | `src/gravitherm/simulation/` | Modelul UTL (ecuația ILS), modelul PPER (putere hidro-gravitațională), profilul de consum HVAC, mediul Gymnasium care le pune cap la cap |
| **Alina** | Agent RL | `src/gravitherm/agent/` | Funcția de recompensă (5 termeni), antrenare PPO → SAC, export ONNX, wrapper de inferență pentru Raspberry Pi |
| **Andreea** | IoT & date | `src/gravitherm/iot/` | Driverele senzorilor (DS18B20, BMP280), driverele actuatoarelor (pompă L298N, LED RGB), clientul MQTT, scrierea în InfluxDB, bucla principală de pe Raspberry Pi |
| **Toată echipa** | Dashboard + integrare | `src/gravitherm/dashboard/`, `scripts/` | Dashboard Plotly/Dash (baseline vs. RL), scriptul de comparație finală — se ating rar, se coordonează dinainte |

Interfața comună care trebuie stabilită **în prima zi**, împreună (o discuție de 30 min, nu cod scris pe apucate):

- Ce returnează mediul de simulare la fiecare pas: `observation` (temperatură UTL, presiune PPER, oră, tarif) și `reward`.
- Formatul mesajelor MQTT (topic-uri: `gravitherm/sensors/temp1`, `gravitherm/sensors/pressure`, `gravitherm/actuators/pump`, payload JSON cu `timestamp`, `value`, `unit`).
- Formatul modelului exportat (ONNX, input/output shape) pe care Andreea îl consumă în `iot/rpi_main.py` fără să știe cum a fost antrenat.

Acest contract se scrie o dată în `src/gravitherm/interfaces.py` (dataclass-uri simple) și devine "granița" peste care nimeni nu calcă fără să anunțe pe ceilalți.

---

## 3. Stack tehnic

**Limbaj:** Python 3.11+ peste tot (simulare, agent, IoT) — un singur limbaj, o singură toolchain, ușor de rulat și pe laptop și pe Raspberry Pi.

| Zonă | Unelte | De ce |
|---|---|---|
| Modele fizice | NumPy, SciPy | ecuații ILS și hidro-gravitaționale, integrare numerică |
| Mediu RL | Gymnasium | interfață standard `reset()`/`step()`, compatibilă cu Stable-Baselines3 |
| Antrenare agent | Stable-Baselines3 (PPO, apoi SAC) | implementări testate, ușor de folosit, exact ce e menționat în propunere |
| Export/inferență model | ONNX + onnxruntime | model ~2MB, rulează rapid pe Raspberry Pi fără dependențe grele |
| Dashboard | Plotly Dash | grafice interactive live, ușor de rulat local |
| Senzori RPi | `w1thermsensor` (DS18B20, 1-Wire), `adafruit-circuitpython-bmp280` sau `smbus2` (I²C) | librării standard, bine documentate pentru RPi |
| Actuatoare | `gpiozero` sau `RPi.GPIO` | control pompă (prin L298N) și LED RGB |
| Mesagerie | Mosquitto (broker MQTT) + `paho-mqtt` (client Python) | exact stack-ul din propunere, ușor de rulat în Docker |
| Bază de date time-series | InfluxDB OSS | nativ pentru date de senzori, se integrează direct cu Grafana |
| Vizualizare live | Grafana OSS | dashboard-ul "de producție", separat de dashboard-ul Dash de analiză RL |
| Infrastructură locală | Docker Compose (Mosquitto + InfluxDB + Grafana) | un singur `docker compose up` pornește tot stack-ul de date, identic pe laptop și pe RPi |
| Testare | pytest, pytest-cov | unit + integration tests |
| Linting/format | ruff + black | consistență de cod fără dezbateri de stil |
| CI | GitHub Actions | rulează testele automat la fiecare PR |

Tot ce e software e gratuit și open-source, exact cum spune propunerea.

---

## 4. De la MVP la sistemul complet — 5 trepte

Fiecare treaptă e utilizabilă și demonstrabilă singură; nu așteptăm "totul gata" ca să arătăm ceva.

**MVP 0 — Modele fizice izolate (fără RL, fără hardware)**
`simulation/utl_model.py` și `simulation/pper_model.py` calculează, cu parametri fixați de mână, temperatura UTL și puterea PPER, validate cu exemplul numeric din propunere (Q=0.5 L/s, H=60m, η=0.72 → ~21W). Ieșire: un grafic simplu. Proprietar: Alexandra. Nimeni altcineva nu are nevoie de altceva ca să înceapă.

**MVP 1 — Mediu de simulare + baseline ON/OFF**
`simulation/env.py` expune un mediu Gymnasium care leagă modelele de mai sus de un "ceas" simulat (oră, tarif). Un controller simplu ON/OFF (prag fix de temperatură) rulează peste acest mediu. Dashboard-ul Dash arată temperatura și puterea în timp. Aici intră Alina și Andreea în paralel cu Alexandra — Alina scrie deja `agent/reward.py` folosind `observation`-ul definit de mediu, fără să aștepte ca mediul să fie "perfect".

**MVP 2 — Agent PPO antrenat (Faza I din propunere)**
`agent/train_ppo.py` antrenează PPO pe mediul de simulare cu funcția de recompensă completă (5 termeni). Dashboard-ul compară RL vs. baseline ON/OFF pe date simulate. **Acesta e livrabilul Fazei I.**

**MVP 3 — Pipeline IoT real, în paralel, fără buclă închisă (Faza II)**
`iot/` publică citiri reale de la DS18B20 + BMP280 către MQTT → InfluxDB → Grafana, și poate comanda manual pompa + LED-ul. Acest MVP rulează independent de simulare — nu are nevoie de agentul RL ca să fie testat. Andreea și Alexandra lucrează în paralel pe module diferite.

**MVP 4 — Buclă închisă senzor→agent→actuator (Faza III)**
`agent/inference.py` (ONNX runtime) rulează pe Raspberry Pi, primește citirile reale prin `iot/` în loc de date sintetice, și comandă pompa prin `iot/actuators/pump.py`. Se rulează în paralel sesiuni baseline vs. RL și se colectează metricile de comparație (target: −10-18% consum).

**MVP 5 — Demo & documentație (Faza IV)**
Video demonstrativ, curățare cod, README, acest plan actualizat cu rezultate reale. Nu se mai scrie cod nou de funcționalitate, doar polish.

---

## 5. Cum testăm

Testarea urmează aceeași separare pe module — fiecare persoană scrie teste pentru propriul folder, plus câteva teste de integrare comune.

- **Simulare (Alexandra) — `tests/test_simulation/`**: teste unitare care verifică ecuațiile pe cazuri cunoscute (ex: exemplul numeric PPER din propunere trebuie să dea ~21W ± toleranță; temperatura ILS la `t→∞` trebuie să tindă spre `T_undisturbed`). Sunt teste pur matematice, rapide, fără hardware.
- **Agent (Alina) — `tests/test_agent/`**: teste care verifică forma funcției de recompensă (fiecare termen se comportă cum trebuie la limite — ex. recompensa de confort e maximă în intervalul 21–24°C), și un test de "sanity" de antrenare scurtă (100 de pași) care verifică doar că nu crapă și că recompensa medie nu scade constant.
- **IoT (Andreea) — `tests/test_iot/`**: driverele de senzori/actuatoare se testează cu mock-uri (nu ai nevoie de Raspberry Pi fizic ca să rulezi CI) — se simulează un broker MQTT local (poate rula chiar Mosquitto în Docker în CI) și se verifică formatul mesajelor publicate/consumate conform contractului din `interfaces.py`.
- **Integrare (toată echipa)**: `scripts/run_comparison.py` rulează un scenariu scurt end-to-end (fie complet simulat, fie cu hardware conectat) și verifică că baseline și RL produc metrici comparabile ca format, indiferent care "câștigă".
- **CI automat**: GitHub Actions rulează `pytest` + `ruff check` + `black --check` la fiecare push și la fiecare Pull Request către `main`. Un PR nu se poate face merge dacă CI-ul e roșu — asta e regula, nu excepția.

Pe scurt: testele fizice/matematice nu au nevoie de nimic special, testele IoT folosesc mock-uri/Docker ca să nu depindă de hardware fizic în CI, iar validarea reală (cu senzori fizici) se face manual, documentată în `docs/` cu rezultatele Fazei III.

---

## 6. Structura repo-ului GitHub

```
gravitherm/
├── README.md                     # prezentare scurtă + cum se rulează
├── AGENTS.md                     # context pt. orice AI assistant (Claude, Cursor, etc.) — vezi secțiunea 7
├── CONTRIBUTING.md               # workflow git, cum facem branch-uri și PR-uri
├── docs/
│   ├── plan.md                   # acest document
│   ├── architecture.md           # diagrama celor 3 straturi (simulare / edge / date)
│   └── results.md                # completat progresiv cu rezultate din Faza III
├── requirements.txt              # sau pyproject.toml
├── .env.example                  # variabile (broker MQTT, InfluxDB token, etc.) — .env real NU se comite
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                # pytest + ruff + black la fiecare PR
├── src/
│   └── gravitherm/
│       ├── __init__.py
│       ├── interfaces.py         # contractul comun (dataclass-uri) — se schimbă doar cu acordul echipei
│       ├── config.py             # constante fizice, setpoint-uri, căi către modele
│       ├── simulation/           # ◄ Alexandra
│       │   ├── utl_model.py
│       │   ├── pper_model.py
│       │   ├── hvac_profile.py
│       │   └── env.py
│       ├── agent/                # ◄ Alina
│       │   ├── reward.py
│       │   ├── train_ppo.py
│       │   ├── train_sac.py
│       │   ├── export_onnx.py
│       │   └── inference.py
│       ├── iot/                  # ◄ Andreea
│       │   ├── sensors/
│       │   │   ├── ds18b20.py
│       │   │   └── bmp280.py
│       │   ├── actuators/
│       │   │   ├── pump.py
│       │   │   └── led.py
│       │   ├── mqtt_client.py
│       │   ├── influx_writer.py
│       │   └── rpi_main.py
│       └── dashboard/            # ◄ comun
│           └── app.py
├── tests/
│   ├── test_simulation/
│   ├── test_agent/
│   └── test_iot/
├── notebooks/                     # explorare, calibrare, nu cod de producție
├── infra/
│   ├── docker-compose.yml         # Mosquitto + InfluxDB + Grafana
│   └── grafana/                   # dashboard-uri exportate (JSON)
├── scripts/
│   └── run_comparison.py          # baseline vs RL, folosit în Faza III
└── models/                        # checkpoint-uri antrenate + export ONNX (fișiere mari → Git LFS sau .gitignore + upload separat)
```

**De ce evită conflictele de merge:** fiecare persoană scrie aproape exclusiv în folderul ei (`simulation/`, `agent/`, `iot/`). Singurele fișiere "comune" (`interfaces.py`, `config.py`, `dashboard/app.py`) se ating rar și doar după o vorbă scurtă în grupul echipei — practic, git rareori va cere să rezolvați manual aceeași linie din același fișier.

---

## 7. Context pentru agenții AI ai fiecăruia (ex: Claude, Cursor, ChatGPT)

Am pregătit fișiere `AGENTS.md` (standardul folosit de majoritatea coding assistant-elor — Claude Code, Cursor, etc.) care se pun direct în repo:

- `AGENTS.md` la rădăcină — context general despre proiect, glosar de termeni (PPER/UTL/RLAEA), arhitectură, convenții de cod, și **regula explicită: agentul trebuie să pună întrebări de clarificare înainte să scrie cod sau să dea un răspuns, dacă cerința nu e 100% clară.**
- `src/gravitherm/simulation/AGENTS.md`, `src/gravitherm/agent/AGENTS.md`, `src/gravitherm/iot/AGENTS.md` — context scopat pe fiecare modul, astfel încât atunci când Alexandra/Alina/Andreea lucrează în folderul lor, agentul lor AI vede doar ce trebuie: ecuațiile relevante, interfața pe care trebuie să o respecte, ce NU trebuie să atingă (fișierele celorlalți), și ce întrebări specifice ar trebui puse înainte de a începe (ex: "ce unitate de măsură are `H` — metri sau bar?").

Aceste fișiere sunt incluse deja în arhiva trimisă — le puneți direct în repo la locurile indicate mai sus.

---

## 8. Cronologie (aliniată cu cele 4 faze din propunere)

| Săpt. | Fază | Ce se livrează | Cine |
|---|---|---|---|
| 1 | I | `interfaces.py` stabilit împreună; `simulation/utl_model.py`, `simulation/pper_model.py` (MVP 0) | Alexandra (+ discuție comună ziua 1) |
| 2–3 | I | `simulation/env.py`, `agent/reward.py`, `agent/train_ppo.py`, dashboard Dash (MVP 1–2) | Alexandra / Alina + Andreea (dashboard) |
| 4–6 | II | `iot/` complet — senzori, actuatoare, MQTT, InfluxDB, Grafana (MVP 3) | Andreea (+ Alexandra pe conectare senzori) |
| 7–9 | III | `agent/inference.py` pe RPi, buclă închisă, comparație baseline vs RL (MVP 4) | Alexandra + Alina |
| 10–12 | IV | Video, `docs/results.md`, curățare finală (MVP 5) | Toată echipa |

---

## 9. Două verificări făcute deja pe modelele fizice (de confirmat cu echipa)

Am scris și rulat codul din `simulation/pper_model.py` și `simulation/utl_model.py` ca să validez că formulele din propunere se comportă cum ne așteptăm. Au ieșit două lucruri de clarificat înainte să le folosiți ca atare în raport/prezentare:

1. **Exemplul numeric PPER pare să aibă o eroare de zecimală.** Cu `Q=0.5 L/s, H=60m, η=0.72`, formula `P=η·ρ·g·Q·H` dă **~212W**, nu ~21W cum scrie propunerea. Cifra de ~21W rezultă corect doar dacă `Q=0.05 L/s` (de 10x mai mic). Probabil e o typo în document — de confirmat care e debitul real măsurat/estimat înainte de a-l pune în cod ca „adevăr de referință".
2. **Modelul ILS (UTL) nu converge la temperatura neperturbată pe termen lung — dimpotrivă.** Ecuația liniei-sursă infinite prezice că, sub extracție constantă de căldură, temperatura solului se *îndepărtează* logaritmic de `T_undisturbed` cu timpul ("derivă termică"), nu se stabilizează. Convergența la `T_undisturbed` se întâmplă la `t→0` (începutul extracției), nu la `t→∞`. Ambele teste din `tests/test_simulation/test_utl_model.py` verifică acest comportament corect. E un fenomen fizic real și documentat pentru bucle geotermale — merită menționat explicit în raport ca limitare cunoscută, nu ignorat.

Ambele sunt deja reflectate în cod (docstring-uri + teste), dar decizia finală (care valoare e corectă, cum se discută derivă termică în raport) rămâne a echipei.

## 10. Următorul pas concret

1. Cele 3 persoane citesc `AGENTS.md` din rădăcină + fișierul lor de modul.
2. O discuție scurtă (30 min) pentru a confirma `interfaces.py` — formatul observației, al mesajelor MQTT, al modelului ONNX.
3. Fiecare creează branch-ul propriu (`alexandra/simulation`, `alina/agent`, `andreea/iot`) și începe direct pe MVP 0/MVP 1 din folderul ei — vezi `CONTRIBUTING.md` pentru regulile de branch și PR.
