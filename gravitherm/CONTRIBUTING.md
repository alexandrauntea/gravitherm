# CONTRIBUTING.md — cum lucrăm în 3 pe acest repo fără să ne stricăm munca

## Regula de bază

**Fiecare persoană lucrează, cel mai des, într-un singur folder** (vezi `docs/plan.md` secțiunea 2 pentru cine deține ce). Cât timp respectăm asta, git nu va avea aproape niciodată nevoie să combine manual aceleași linii de la doi oameni diferiți.

## Branch-uri

- `main` — mereu stabil, mereu rulabil. Nu se face push direct pe `main`.
- Un branch de lucru per persoană per funcționalitate: `alexandra/utl-model`, `alina/reward-function`, `andreea/mqtt-client`, etc. — nu un singur branch lung per persoană pentru toată durata proiectului.
- Branch-urile trăiesc puțin (câteva zile, nu săptămâni) — cu cât stau mai mult nefuzionate, cu atât cresc șansele de conflict.

## Pull Request-uri

1. Deschide PR către `main` cât mai devreme (chiar și "draft" dacă nu e gata) — e mai ușor de urmărit ce face fiecare.
2. PR-uri mici și dese bat un PR uriaș la final de fază. Țintă: sub ~300 linii schimbate per PR acolo unde e posibil.
3. CI (pytest + ruff + black) trebuie să treacă verde înainte de merge.
4. Cel puțin o altă persoană din echipă dă un review rapid (chiar și doar "citit, ok") înainte de merge — mai ales pentru schimbări în `interfaces.py`, `config.py` sau `dashboard/`.
5. Merge cu "squash and merge" ca să păstrăm istoricul pe `main` curat.

## Fișierele comune — atenție sporită

`interfaces.py`, `config.py` și `dashboard/app.py` sunt singurele locuri unde ne putem călca pe picioare. Reguli:

- Orice schimbare la `interfaces.py` se anunță în grupul echipei *înainte* de commit, nu după.
- Dacă doi oameni au nevoie să atingă `dashboard/app.py` în aceeași săptămână, coordonați cine merge primul, ca celălalt să pornească de pe versiunea proaspătă.

## Commit-uri

Mesaje scurte, la subiect, în engleză sau română (consecvent în tot repo-ul — alegeți una la început). Prefix opțional cu modulul: `[simulation] add ILS heat equation`, `[agent] tune comfort reward term`, `[iot] add MQTT publisher for BMP280`.

## Sincronizare cu `main`

Înainte de a începe o sesiune de lucru, `git pull origin main` pe branch-ul tău (`git merge main` sau `git rebase main`) — mai ales dacă altcineva a schimbat `interfaces.py` de la ultima ta sincronizare.

## Fișiere mari (modele antrenate)

Checkpoint-urile de antrenare și modelele `.onnx` nu se comit direct în git dacă depășesc câțiva MB — fie Git LFS, fie se pun în `models/` cu `.gitignore` și se distribuie separat (link Drive/GitHub Release) la final de fază.

## Secrete

Token-uri InfluxDB, parole MQTT etc. NU se comit niciodată. Se pun într-un `.env` local (ignorat de git) — vezi `.env.example` pentru câmpurile necesare.
