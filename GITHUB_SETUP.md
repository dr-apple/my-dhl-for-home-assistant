# GitHub Repository für HACS einrichten

Diese Anleitung erklärt wie du das Repository auf GitHub veröffentlichst, damit es über HACS installierbar ist.

---

## 1. GitHub Repository erstellen

1. Gehe zu https://github.com/new
2. Repository-Name: `dhl-meine-sendungen-ha`
3. **Public** auswählen (HACS benötigt öffentliche Repos)
4. Kein README, keine .gitignore hinzufügen
5. **Create repository**

---

## 2. Dateien hochladen

### Option A: GitHub Web-Interface (einfach)

1. Im neuen Repository auf **"uploading an existing file"** klicken
2. Alle Dateien aus dem ZIP hochladen – **die Ordnerstruktur muss erhalten bleiben:**
   ```
   dhl-meine-sendungen-ha/
   ├── custom_components/
   │   └── dhl_meine_sendungen/
   │       ├── __init__.py
   │       ├── config_flow.py
   │       ├── const.py
   │       ├── coordinator.py
   │       ├── manifest.json
   │       ├── scraper.py
   │       ├── sensor.py
   │       ├── strings.json
   │       └── translations/
   │           └── de.json
   ├── hacs.json          ← WICHTIG für HACS
   ├── info.md            ← HACS Beschreibungsseite
   ├── README.md
   └── LICENSE
   ```
3. Commit: `"Initial release v1.0.0"`

### Option B: Git (Kommandozeile)

```bash
cd dhl-meine-sendungen-ha/
git init
git add .
git commit -m "Initial release v1.0.0"
git branch -M main
git remote add origin https://github.com/DEIN-USERNAME/dhl-meine-sendungen-ha.git
git push -u origin main
```

---

## 3. GitHub Release erstellen (WICHTIG für HACS!)

HACS erkennt Integrationen nur wenn mindestens ein **Release mit Tag** existiert.

1. Im Repository auf **Releases** → **"Create a new release"**
2. **Tag:** `v1.0.0` (neu erstellen)
3. **Title:** `v1.0.0 – Initial Release`
4. **Description:**
   ```
   ## DHL Meine Sendungen v1.0.0
   
   Erste Version der Integration.
   
   ### Features
   - Login bei dhl.de
   - Alle Sendungen als HA-Sensoren
   - Live-Tracking (Stops, Zeitfenster, Position)
   ```
5. **Publish release** klicken

---

## 4. In HACS als Custom Repository hinzufügen

1. Home Assistant öffnen → **HACS**
2. **Integrationen** → oben rechts **⋮** → **Benutzerdefinierte Repositories**
3. Eingeben:
   - URL: `https://github.com/DEIN-USERNAME/dhl-meine-sendungen-ha`
   - Kategorie: **Integration**
4. **Hinzufügen** klicken
5. Jetzt erscheint **"DHL Meine Sendungen"** in der HACS-Integrationsliste
6. **Herunterladen** → HA neu starten

---

## 5. Vor der Veröffentlichung: GitHub-Username ersetzen

**Ersetze in diesen Dateien `dein-github-user` mit deinem echten GitHub-Username:**

- `custom_components/dhl_meine_sendungen/manifest.json`
  - `"documentation"` URL
  - `"issue_tracker"` URL  
  - `"codeowners"` Array
- `README.md` – alle Links
- `info.md` – Links

---

## 6. Zukünftige Updates veröffentlichen

Wenn du Updates machst:

1. Version in `manifest.json` erhöhen (z. B. `1.0.1`)
2. Änderungen committen und pushen
3. Neues GitHub Release erstellen mit neuem Tag (z. B. `v1.0.1`)
4. HACS erkennt das Update automatisch und zeigt es den Nutzern an

---

## Optionaler nächster Schritt: HACS Default Repository

Wenn die Integration gut funktioniert und du sie offiziell in den HACS-Standardkatalog aufnehmen möchtest:
- https://hacs.xyz/docs/publish/integration
