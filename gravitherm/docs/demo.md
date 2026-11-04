# Ghid Rulare Demo Live GraviTherm (Etapa II, TechChallenge Honeywell 2026)

Acest document descrie procedura completă pas cu pas pentru susținerea demonstrației live în fața juriului, precum și planurile de rezervă în caz de anomalii hardware sau de rețea.

---

## 1. Pornire Pas cu Pas (Procedura Nominală pe Hardware Real)

### Pasul 1: Conectare SSH la Raspberry Pi 4
De pe laptopul de prezentare conectat la aceeași rețea Wi-Fi / hotspot cu Raspberry Pi:
```bash
ssh alexandra@<ip-rpi>
cd ~/gravitherm/gravitherm
```

### Pasul 2: Verificare apă în rezervor & montaj
- Verificați nivelul apei în rezervorul superior (pentru amorsarea pompei QR50D).
- Asigurați-vă că furtunul de silicon trece prin tubulatura machetei 3D și returul este orientat în vas.

### Pasul 3: Pornire script demo
```bash
# Pornire pe hardware real, cu pompa autorizată să funcționeze
python scripts/demo_live.py --enable-pump
```
*Notă de siguranță:* Fără flag-ul `--enable-pump`, pompa este blocată software împotriva mersului în gol pe birou.

### Pasul 4: Deschidere Dashboard pe laptopul conectat la proiector
1. Deschideți browser-ul (Chrome / Edge / Firefox) la adresa afișată în terminal:
   ```text
   http://<ip-rpi>:8050
   ```
2. Apăsați **F11** pentru modul **Fullscreen** (16:9 fără scroll la 1920×1080 sau 1366×768).

---

## 2. Comenzi în Timpul Prezentării

Comenzile sunt disponibile **direct din fereastra de browser** (fără a ieși din ecranul proiectat), prin butoanele discrete din colțul din dreapta-sus sau din terminalul SSH:

| Comandă / Tastă | Acțiune | Detalii |
|---|---|---|
| **`Space`** sau **`→`** | **Faza următoare** | Declanșează trecerea la următoarea fază a zilei simulate. Când o fază se termină, ceasul simulat îngheață discret și așteaptă apăsarea tastei Space. |
| **`P`** | **Pauză / Reluare** | Îngheață ceasul simulat și menține starea curentă a actuatorilor (util când vorbiți mai mult despre un grafic). |
| **`R`** | **Reset Demo** | Resetează totul la Faza 0 (ora 00:00), golește istoricul și oprește pompa și Peltierul. |
| **`S`** | **STOP DE URGENȚĂ** | **Decuplare forțată instantanee** a pompei și a modulului Peltier. Comenzile sunt blocate până la apăsarea tastei R. |

---

## 3. Scenariul celor 6 Faze ale Prezentării (~5 minute)

| # | Nume Fază | Ora simulată | Durată | Pompă (reală) | Peltier (real) | Mesaj cheie pentru juriu |
|---|---|---|---|---|---|---|
| **0** | Noapte, pornire sistem | 00:00 → 06:00 | 25 s | OPRITĂ | **PORNIT** | Pre-răcire termică UTL a clădirii pentru a reduce sarcina termică a orelor de vârf de peste zi. |
| **1** | Dimineață, sosire angajați | 06:00 → 10:00 | 70 s | **PORNITĂ** | **PORNIT** | Cererea de apă pe coloană crește → **Micro-turbina PPER generează energie**. LED-ul fizic se aprinde! |
| **2** | Prânz + caniculă (34°C afară) | 10:00 → 15:00 | 80 s | **PORNITĂ continuu** | **PORNIT** | Caniculă extremă: bucla UTL răcește pasiv clădirea, evitând chillerul mecanic clasic. Confortul rămâne în 21–24°C. |
| **3** | Vârf de consum / cerere rețea | 15:00 → 18:00 | 50 s | **PULSURI** (8s ON / 4s OFF) | OPRIT | Sarcina maximă pe rețea → Prioritizăm energia recuperată PPER și minimizăm importul din rețea. LED-ul clipește în sincron cu apa! |
| **4** | Seară, clădirea se golește | 18:00 → 24:00 | 25 s | OPRITĂ | OPRIT | Ocuparea scade, sistemul intră în standby economic. |
| **5** | Sumar rezultate finale | 24:00 (înghețat) | 30 s | OPRITĂ | OPRIT | **Overlay mare cu rezultatele**: -13.7% kWh economisiți, -13.7% cost lei (pe tarif fix 1.00 lei/kWh; -20% pe tarif dinamic), ~1.840 kg CO₂ evitat/an. |

---

## 4. Planuri de Rezervă (Troubleshooting & Fallback)

### Planul A: Oprire rapidă la anomalii mecanice / scurgeri de apă
- Apăsați imediat tasta **`S`** (sau butonul roșu **STOP (S)** din colțul paginii).
- Pompa și Peltierul sunt decuplate în mai puțin de 50 ms prin hardware manager.
- Watchdog-ul intern decuplează de asemenea automat dacă procesul Python sau conexiunea îngheață mai mult de 3 secunde.

### Planul B: Rulare pe laptop pentru repetiții sau avarie hardware RPi (`--mock`)
Dacă la prezentare conexiunea Wi-Fi către RPi cade sau un senzor fizic refuză să funcționeze:
1. Rulați scriptul direct local pe laptop (Windows / macOS / Linux):
   ```bash
   python scripts/demo_live.py --mock
   ```
2. Deschideți în browser `http://localhost:8050`. Toate graficele, animațiile SVG, deciziile agentului și calculele de economii funcționează **100% identic** cu varianta fizică, folosind actuatori și senzori virtuali.

### Planul C: Prezentare fără interacțiune cu tastatura (`--auto`)
Dacă doriți ca fazele să avanseze automat fără să apăsați Space:
```bash
python scripts/demo_live.py --mock --auto
# sau pe RPi:
python scripts/demo_live.py --enable-pump --auto
```

---

## 5. Configurare Tarif: Fix vs. Dinamic

Comportamentul tarifului de energie electrică este configurabil în `src/gravitherm/demo/demo_config.py`:
- **`fixed_tariff_enabled: bool = True`** (implicit activat):
  - Preț fix: **`1.00 leu / kWh`** (`fixed_tariff_lei_kwh`).
  - Faza 3 este denumită *„Vârf de consum / cerere rețea”*, iar agentul prioritizează reducerea solicitării rețelei și maximizarea autoconsumului PPER.
  - Economia de cost este direct proporțională cu economia de energie (~13.7%).
- **`fixed_tariff_enabled = False`** (comutare opțională pe tarif variabil pe tranșe orare):
  - 0.45 lei/kWh (noapte 00:00–06:00), 0.85 lei/kWh (dimineață), 1.15 lei/kWh (prânz), 1.70 lei/kWh (vârf 15:00–18:00), 0.90 lei/kWh (seară).
  - Economia de cost crește la ~20.4% prin arbitraj tarifar.

---

## 6. Rulare Teste de Validare

Pentru a verifica funcționarea întregii suite înainte de prezentare:
```bash
pytest tests/test_demo -v
```
Toate cele 13 teste (continuitate faze, ceas monoton, tarif fix și dinamic, bandă de confort 21–24°C, economie energie 10–25%, arbitraj cost, watchdog și stop de urgență) trebuie să treacă cu `PASSED`.

