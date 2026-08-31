# AGENTS.md — modul `iot/` (proprietar: Andreea)

Citește mai întâi `AGENTS.md` de la rădăcina repo-ului (regula #0 despre întrebări de clarificare se aplică la fel aici).

## Scopul acestui modul

Tot ce atinge hardware fizic sau infrastructura de date: citirea senzorilor, comanda actuatoarelor, publicarea pe MQTT, scrierea în InfluxDB, și bucla principală care rulează pe Raspberry Pi.

## Fișiere și ce trebuie să facă fiecare

- `sensors/ds18b20.py` — citește temperatura de la cei 3 senzori DS18B20 (protocol 1-Wire, librăria `w1thermsensor`).
- `sensors/bmp280.py` — citește presiunea/temperatura de la BMP280 (I²C).
- `actuators/pump.py` — controlează pompa DC 12V prin driverul L298N (`gpiozero` sau `RPi.GPIO`).
- `actuators/led.py` — controlează LED RGB (verde = recirculare activă, roșu = blocare, albastru = pre-răcire).
- `mqtt_client.py` — publică citirile senzorilor și starea actuatoarelor pe broker-ul Mosquitto local; subscrie la comenzile venite de la agent.
- `influx_writer.py` — consumă mesajele MQTT și le scrie în InfluxDB (time-series).
- `rpi_main.py` — bucla principală de pe Raspberry Pi: citește senzori → publică MQTT → primește decizia agentului (`agent/inference.py`) → comandă actuatoarele. Acesta e punctul de intrare pentru Faza III/IV (buclă închisă).

## Interfața pe care trebuie să o respecți

Topic-urile și formatul payload-ului MQTT sunt definite în `../interfaces.py` (ex: `gravitherm/sensors/temp1`, payload JSON cu `timestamp`, `value`, `unit`). Nu schimba topic-uri sau format fără să anunți echipa — Grafana și `influx_writer.py` depind de ele.

## Ce să NU faci

- Nu depinde de `agent/train_ppo.py` sau de Stable-Baselines3 — acest modul consumă doar `agent/inference.py` (ONNX runtime), care are dependențe ușoare.
- Nu scrie direct în InfluxDB din codul senzorilor — trece mereu prin MQTT, ca să păstrăm arhitectura din propunere (senzor → MQTT → InfluxDB → Grafana) și ca să putem testa fără hardware fizic (publicăm mesaje MQTT de test).

## Întrebări de pus înainte de a implementa ceva aici

- Frecvența de publicare pentru fiecare senzor (o dată pe secundă? pe 10 secunde?) — afectează rata de scriere InfluxDB și granularitatea graficelor Grafana.
- Ce se întâmplă dacă un senzor nu răspunde (retry, valoare implicită, alertă)? Comportamentul trebuie definit explicit, nu presupus.
- Broker-ul MQTT rulează local pe RPi sau pe alt device din rețea în timpul demo-ului?

## Testare

`tests/test_iot/` — teste cu mock-uri pentru senzori/actuatoare (nu necesită Raspberry Pi fizic în CI); pentru MQTT, se poate folosi un broker Mosquitto pornit în Docker chiar în pipeline-ul de CI, testând doar formatul mesajelor conform contractului din `interfaces.py`. Validarea cu hardware fizic real se face manual și se documentează în `docs/results.md`.

## Cum rulez acest modul fără hardware (macheta nu a sosit încă)

1. `docker compose -f infra/docker-compose.yml up -d` — pornește Mosquitto + InfluxDB + Grafana local.
2. `python scripts/simulate_sensors.py` — publică pe MQTT date sintetice de temperatură/presiune, în formatul exact pe care l-ar publica `sensors/ds18b20.py`/`bmp280.py` reale.
3. Deschide Grafana la `localhost:3000` — dacă vezi valori care se actualizează, tot pipeline-ul MQTT → InfluxDB → Grafana funcționează, indiferent dacă senzorii sunt reali sau simulați.
4. Când vine hardware-ul fizic, singura schimbare e sursa datelor: `rpi_main.py` cheamă `sensors/ds18b20.py`/`bmp280.py` în loc de `scripts/simulate_sensors.py` — restul (`mqtt_client.py`, `influx_writer.py`, dashboard-ul Grafana) rămâne neschimbat și deja testat.
