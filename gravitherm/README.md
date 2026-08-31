# GraviTherm

Sistem integrat de recaptare pasivă a energiei și răcire AI-adaptivă pentru clădiri de birouri înalte — prototip pentru TechChallenge by Honeywell 2026 (UPB, Facultatea de Automatică și Calculatoare).

Echipă: Untea Alexandra-Nicoleta, Râncă Alina-Maria, Ionescu Andreea.

## Ce este acest repo

Prototip de laborator ("simulate-then-scale") pentru cele 3 subsisteme din propunere: **PPER** (recuperare energie hidro-gravitațională), **UTL** (răcire geotermală pasivă) și **RLAEA** (agent RL multi-obiectiv pentru control HVAC).

Documentul complet de plan tehnic, cu tot ce ține de arhitectură, stack, split de lucru pe echipă, MVP-uri și testare: **[`docs/plan.md`](docs/plan.md)**.

Dacă lucrezi cu un AI assistant (Claude, Cursor etc.) în acest repo, citește întâi **[`AGENTS.md`](AGENTS.md)**.

## Instalare rapidă

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env   # completează valorile locale

# infrastructura de date (Mosquitto + InfluxDB + Grafana)
docker compose -f infra/docker-compose.yml up -d

# rulează testele
pytest
```

## Structură

Vezi `docs/plan.md` secțiunea 6 pentru structura completă a repo-ului și cine deține ce folder.

## Contribuție

Vezi [`CONTRIBUTING.md`](CONTRIBUTING.md) pentru workflow-ul de git (branch-uri, PR-uri, cum evităm conflictele de merge lucrând în 3 persoane).
