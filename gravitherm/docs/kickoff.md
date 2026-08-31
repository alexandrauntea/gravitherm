# Cum începem — pas cu pas (Ziua 0 → sfârșitul Săptămânii 1)

Acest ghid urmează **modelul original din `docs/plan.md`**: fiecare persoană deține un modul (folder) pe toată durata proiectului — Alexandra pe `simulation/`, Alina pe `agent/`, Andreea pe `iot/` — fără rotație și fără roluri de backup. E modelul cel mai simplu de ținut minte și cel care evită cel mai direct conflictele de merge: fiecare lucrează aproape exclusiv în folderul ei.

---

## Ziua 0 — configurare repo (o singură persoană, ~20 min)

Oricare dintre voi trei, cu cont GitHub:

1. Creează repo nou pe GitHub: `gravitherm` (public sau privat — propunerea cere "repository GitHub public" ca livrabil final al Fazei IV, deci puteți porni privat și îl faceți public când sunteți gata de demo).
2. **Settings → Collaborators** → adaugă celelalte două colege.
3. Local, dezarhivează scheletul de repo primit și inițializează:
   ```bash
   cd gravitherm
   git init
   git add .
   git commit -m "chore: initial repo skeleton (structure, docs, stubs)"
   git branch -M main
   git remote add origin <url-ul repo-ului vostru>
   git push -u origin main
   ```
4. **Settings → Branches → Add branch protection rule** pe `main`:
   - "Require a pull request before merging" — bifat.
   - "Require status checks to pass before merging" — bifat (selectați job-ul `test` din CI după primul push).
   Asta impune automat regula din `CONTRIBUTING.md`: nimeni nu dă push direct pe `main`.
5. Fiecare din voi, local:
   ```bash
   git clone <url-ul repo-ului>
   cd gravitherm
   python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .
   cp .env.example .env
   docker --version    # confirmați că aveți Docker instalat, pentru infra/docker-compose.yml
   ```

---

## Ziua 1 — discuție de echipă, 30 minute (înainte de a scrie cod nou)

Ordinea contează — nu săriți la cod înainte de asta:

1. **Deschideți împreună `src/gravitherm/interfaces.py`.** Confirmați fiecare câmp din `Observation` — mai ales unitățile (H în metri? Q în L/s?) — și formatul mesajelor MQTT. Dacă schimbați ceva, editați fișierul pe loc, împreună, și faceți un singur commit `[shared] confirm interfaces.py contract` de pe branch-ul cine a condus discuția.
2. **Rezolvați cele două discrepanțe fizice** semnalate în `docs/plan.md` secțiunea 9 (exemplul PPER de 10x, deriva termică UTL) — decideți ce valoare/interpretare folosiți în cod și în raport. Notați decizia în `docs/decisions.md` (vedeți șablonul din fișier).
3. **Confirmați împărțirea pe module** din `docs/plan.md` secțiunea 2 (Alexandra=simulare, Alina=agent, Andreea=IoT) — dacă cineva vrea alt modul, e momentul să schimbați, nu mai târziu.

---

## Task-urile fiecărei persoane — Săptămâna 1 (MVP 0 + fundații IoT)

Toate 3 seturile de task-uri de mai jos pot începe **în paralel, din aceeași zi** — ating fișiere complet diferite, deci zero risc de conflict de merge.

### Alexandra — proprietar permanent `simulation/` — branch `alexandra/simulation-mvp0`

```bash
git checkout main && git pull
git checkout -b alexandra/simulation-mvp0
```

- **Fișiere:** `src/gravitherm/simulation/pper_model.py`, `src/gravitherm/simulation/utl_model.py` (au deja un schelet funcțional — sarcina e să-l finalizezi/calibrezi, nu să pornești de la zero).
- **Task concret:**
  1. Rezolvă discrepanța Q=0.5 vs Q=0.05 L/s din `pper_model.py` — actualizează docstring-ul și, dacă e nevoie, `config.py`, conform deciziei din `docs/decisions.md`.
  2. Rulează local: `pytest tests/test_simulation/ -v` — confirmă că toate testele trec.
  3. Dacă ai timp: începe `hvac_profile.py` (are deja un placeholder simplu) — discută cu Alina dacă profilul trebuie determinist sau cu zgomot (vezi întrebarea din `simulation/AGENTS.md`).
- **Commit-uri:** prefix `[simulation]`, ex. `[simulation] fix PPER flow rate discrepancy, update docstring`
- **Output final:** deschide PR către `main`, titlu `[simulation] finalize PPER and UTL models for MVP0`, CI verde, cere review de la Alina sau Andreea.

### Alina — proprietar permanent `agent/` — branch `alina/agent-mvp0-prep`

```bash
git checkout main && git pull
git checkout -b alina/agent-mvp0-prep
```

- **Fișiere:** `src/gravitherm/agent/reward.py` (schelet existent), `tests/test_agent/test_reward.py`.
- **Task concret:**
  1. Nu poți finaliza complet `reward.py` până `interfaces.py` e 100% confirmat (făcut la Ziua 1) — dar poți adăuga teste de graniță: comportamentul exact la 21.0°C și 24.0°C (limitele intervalului de confort), și un caz cu `pper_power_w` foarte mare (verifică `recaptured_energy_bonus`).
  2. Deschide o discuție în `docs/decisions.md` despre ponderile relative ale celor 5 termeni din reward (constantele `0.05`, `0.2`, `0.1`, `0.01` din `reward.py` sunt provizorii) — notează-le ca „de tunat în Faza I".
  3. Rulează local: `pytest tests/test_agent/ -v`.
- **Commit-uri:** prefix `[agent]`, ex. `[agent] add boundary tests for comfort reward term`
- **Output final:** PR titlu `[agent] reward function boundary tests + open questions on term weights`, CI verde.

### Andreea — proprietar permanent `iot/` — branch `andreea/iot-foundation`

```bash
git checkout main && git pull
git checkout -b andreea/iot-foundation
```

- **Fișiere:** `infra/docker-compose.yml` (există deja — sarcina e să-l pornești și să confirmi că merge), `scripts/simulate_sensors.py` (fișier nou, trimis separat — adaugă-l în `scripts/`), `src/gravitherm/iot/AGENTS.md` (deja are o secțiune nouă „Cum rulez fără hardware" — verific-o).
- **Task concret:**
  1. `docker compose -f infra/docker-compose.yml up -d`
  2. `python scripts/simulate_sensors.py --interval 2`
  3. Deschide `localhost:3000` (Grafana) — confirmă vizual că vin date. Dacă Grafana nu are încă un dashboard configurat, notează asta ca task pentru MVP 3, nu bloca pe el acum.
  4. Documentează în `docs/decisions.md` orice problemă întâlnită la pornirea stack-ului Docker (porturi ocupate, versiuni etc.).
- **Commit-uri:** prefix `[iot]`, ex. `[iot] add sensor simulator script, verify docker-compose stack`
- **Output final:** PR titlu `[iot] add sensor simulator + verify local data pipeline`, CI verde.

---

## Convenții de sincronizare (aplicabile din Ziua 1 și pe tot proiectul)

| Convenție | Regulă exactă |
|---|---|
| Nume de branch | `<prenume>/<descriere-scurta>` (litere mici, cratimă) — ex. `alexandra/pper-fix`, NU `alexandra-branch` sau `fix1` |
| Prefix de commit | `[simulation]`, `[agent]`, `[iot]`, `[shared]`, `[docs]` — primul cuvânt al mesajului |
| Sincronizare cu main | La începutul FIECĂREI sesiuni de lucru: `git checkout main && git pull && git checkout -b <branch-nou>` |
| Mărime PR | Sub ~300 linii schimbate acolo unde e posibil; deschideți PR devreme (chiar "Draft") ca ceilalți să vadă progresul |
| Anunț de PR | Mesaj scurt în grupul echipei: „PR #X gata de review" — nu presupuneți că ceilalți verifică GitHub din proprie inițiativă |
| Review | Minim o persoană citește PR-ul înainte de merge (chiar „citit, ok") — obligatoriu pentru orice atinge `interfaces.py` sau `config.py` |
| CI | Trebuie verde (`pytest` + `ruff` + `black`) înainte de merge — impus automat de branch protection |
| Merge | „Squash and merge" — păstrează istoricul lui `main` curat |
| Fișiere comune | `interfaces.py`, `config.py`, `dashboard/app.py` — anunțați ÎNAINTE de a le modifica, nu după |
| Decizii | Orice alegere netrivială (o valoare, o interpretare, un compromis) → un bloc nou în `docs/decisions.md`, în același PR |

---

## Ritm de sincronizare pe parcursul săptămânii

- **Zilnic** (text, nu neapărat apel video): 2-3 propoziții în grup — ce am făcut ieri, ce fac azi, ce mă blochează.
- **La finalul Săptămânii 1 / MVP 0** (15 min, toată echipa):
  - Treceți împreună peste `docs/decisions.md` — nimic nu trebuie să rămână doar „în capul cuiva".
  - Confirmați că `interfaces.py` încă reflectă realitatea — dacă cineva a avut nevoie să-l schimbe pe parcurs, se spune acum, cu tot cu motiv.

---

## Cum continuă, dincolo de Săptămâna 1

Proprietatea pe module rămâne fixă pe tot proiectul (nu se rotește):

| MVP | Ce se livrează | Cine |
|---|---|---|
| MVP 0 (Săpt. 1) | Modele fizice izolate — `simulation/pper_model.py`, `utl_model.py` | Alexandra |
| MVP 1 (Săpt. 1-3) | Mediu de simulare + reward + baseline — `simulation/env.py`, `agent/reward.py` | Alexandra + Alina |
| MVP 2 (Săpt. 2-3) | Agent PPO antrenat + dashboard — `agent/train_ppo.py`, `dashboard/app.py` | Alina + Andreea |
| MVP 3 (Săpt. 4-6) | Instrumentare IoT reală — tot `iot/` | Andreea (+ Alexandra pe conectare senzori, conform `docs/plan.md`) |
| MVP 4 (Săpt. 7-9) | Buclă închisă + comparație baseline/RL — `agent/inference.py`, `iot/rpi_main.py`, `scripts/run_comparison.py` | Alexandra + Alina |
| MVP 5 (Săpt. 10-12) | Demo, video, curățare documentație | Toată echipa |

Detalii complete pentru fiecare MVP: `docs/plan.md` secțiunile 2 și 4. Odată ce cele 3 PR-uri din Săptămâna 1 sunt merge-uite pe `main`, treceți la task-urile MVP 1 după același tipar: branch pe persoană, fișiere separate, PR mic, review înainte de merge.
