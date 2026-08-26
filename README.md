# Portfolio

Zwei unabhängige Flask-Anwendungen, die sich nur den dateibasierten
Datenzugriff (`shared/content.py`) teilen, aber keine Laufzeit (AE-06):

- **`web`** — öffentliche Ansicht. Rendert dynamisch aus dem Inhalts­verzeichnis,
  ausschließlich lesend, kein Build-Schritt, keine Datenbank.
- **`admin`** — Verwaltung. CRUD auf Beiträge/Notizen, Seiten und
  `site.config.json`, mit Anmeldung (Passwort + TOTP), Medien-Upload,
  Papierkorb und Versionierung des Inhaltsverzeichnisses über ein lokales
  Git-Repository ohne Remote (FA-41).

Siehe `content/uploads/anforderungskatalog-portfolio.md` (falls vorhanden)
für die vollständigen Anforderungen. Nicht enthalten: Reverse Proxy/TLS
(bereits vorhandener Host-nginx, siehe AE-01), automatisiertes Backup (FA-42).

## Schnellstart mit Docker Compose

```bash
cp .env.example .env
# SECRET_KEY eintragen: python -c "import secrets; print(secrets.token_hex(32))"

docker compose up -d
```

Das startet `web` (`http://127.0.0.1:8091`) und `admin`
(`http://127.0.0.1:8092`) mit Demo-Inhalten aus `./content`. Die eigentlichen
Laufzeitdaten liegen in `./data` (git-ignoriert, eigenes Git-Repository —
siehe unten).

Admin-Zugang einrichten (einmalig, oder um Passwort/TOTP zu ändern):

```bash
docker compose run --rm admin-cli flask --app wsgi_admin create-user
```

Dieser Befehl läuft bewusst über ein eigenes `admin-cli`-Profil und nicht
über den laufenden `admin`-Dienst: Der laufende Dienst hat auf `zugang/`
nur Lesezugriff (siehe FA-26-Tabelle) — kein über HTTP erreichbarer Code
kann die Zugangsdaten verändern.

`create-user` erzeugt neben Passwort und TOTP-Secret auch einen
**Wiederherstellungscode** (für den Login-Screen, falls das TOTP-Gerät
verloren geht — dort funktioniert er anstelle des 6-stelligen Codes).
Anders als klassische Backup-Codes ist er **nicht einmalig verwendbar**:
Aus demselben Grund (`zugang/` nur lesend im laufenden Dienst) kann der
Login ihn nicht als "verbraucht" markieren. Er bleibt gültig, bis er
manuell rotiert wird — am besten direkt nach jeder Verwendung:

```bash
docker compose run --rm admin-cli flask --app wsgi_admin rotate-recovery-code
```

Ändert nur den Wiederherstellungscode, lässt Passwort und TOTP unangetastet.

## Lokale Entwicklung ohne Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

flask --app wsgi_web run --debug --port 5000     # öffentliche Ansicht
flask --app wsgi_admin run --debug --port 5001   # Admin
```

Beide lesen standardmäßig aus `./content` (überschreibbar über die
Umgebungsvariable `CONTENT_DIR`). Admin-Zugang lokal einrichten:

```bash
FLASK_DEBUG=1 flask --app wsgi_admin create-user
```

(`FLASK_DEBUG=1` erlaubt außerhalb von Docker einen automatisch erzeugten
`SECRET_KEY` und schaltet `Secure`-Cookies ab, damit die Anmeldung auch ohne
TLS funktioniert — für echten Betrieb stattdessen `SECRET_KEY` setzen, siehe
`.env.example`.)

### Inhaltsverzeichnis

```
beitraege/
  oeffentlich/<datum>-<slug>/{meta.json, inhalt.md, medien/}
  privat/<datum>-<slug>/...          # nur admin sieht dieses Verzeichnis
seiten/{impressum.md, datenschutz.md, ueber-mich.md, portrait.*}
zugang/benutzer.json                  # Passwort-Hash + TOTP-Secret, chmod 600
.papierkorb/                          # gelöschte Beiträge, manuell zu leeren
site.config.json
```

`./content` in diesem Repository ist Demo-/Seed-Material (siehe Struktur
oben), keine echten Daten. `content/site.config.json` enthält bei Bedarf
echte personenbezogene Angaben und ist deshalb in `.gitignore` eingetragen;
Vorlage: `content/site.config.example.json`.

In Docker Compose ist `DATA_DIR` (Umgebungsvariable, Standard `./data`) das
eigentliche Laufzeitverzeichnis — git-ignoriert und ein eigenes Git-Repository
(FA-41), darf also nicht mit diesem Code-Repository verschachtelt sein. Beim
ersten Start richtet der `init`-Dienst die Struktur ein und kopiert optional
die Demo-Inhalte aus `./content`.

**Wichtig für jedes CI/deploy-gesteuerte Setup:** `DATA_DIR` muss außerhalb
jedes Verzeichnisses liegen, das ein Checkout-Tool neu anlegen oder aufräumen
könnte — die Container schreiben dort als uid 1000, und ein Cleanup-Schritt,
der als anderer Host-Benutzer läuft (z. B. ein GitHub-Actions-Runner-Dienst-
konto), kann diese Dateien dann nicht mehr entfernen. In `.env`
`DATA_DIR=/var/lib/portfolio` setzen (Pfad laut Anforderungskatalog) — siehe
`.env.example`.

## Tests

```bash
pytest
```

56 Tests: `tests/` für `web` (Slug-Auflösung, Pfad-Traversal-Schutz,
Markdown-Sanitisierung, Fehlerseiten, Feed, `/healthz`), `tests/admin/` für
`admin` (Anmeldung/TOTP/Wiederherstellungscode/Rate-Limit, CSRF,
Medien-Upload-Validierung, CRUD-Lebenszyklus, strukturelle Trennung
privat/öffentlich, CLI-Befehle, Einstellungsformular).

## CI/CD

`.github/workflows/deploy.yml`: bei jedem Push auf `main` (und manuell
auslösbar) laufen zuerst `pytest` sowie ein echter Docker-Smoke-Test (bauen,
hochfahren, auf `healthy` warten, `/healthz` beider Dienste abfragen — beide
bisherigen echten Bugs in diesem Projekt zeigten sich nur beim tatsächlichen
Containerstart, nie in reinen Python-Tests). Erst wenn beides grün ist, deployt
ein self-hosted Runner auf dem Server per `docker compose up --build -d`,
analog zur bestehenden Pipeline eines anderen Projekts auf demselben Server.

**Vor dem ersten Lauf auf dem Server einzurichten** (nicht Teil dieses Repos):
- `/etc/portfolio/.env` mit `SECRET_KEY=...` anlegen, lesbar für den
  Runner-Nutzer (Pfad in `deploy.yml` anpassen, falls ein anderer gewünscht ist).
- Ein self-hosted Runner muss für dieses Repository registriert sein.
- Admin-Zugang bleibt weiterhin ein manueller, einmaliger Schritt auf dem
  Server: `docker compose run --rm admin-cli flask --app wsgi_admin create-user`.

## Lizenz

Der Code steht unter der **GNU General Public License v3.0** (siehe
[`LICENSE`](LICENSE)) — frei nutzbar, veränderbar und weiterverbreitbar unter
den GPLv3-Bedingungen.

**Ausnahme:** Die Logo-/Icon-Dateien unter `web/static/icons/` und
`admin/static/icons/` (`logo.svg`, `logo-mono.svg`, `favicon.svg`,
`banner.svg`) sind **nicht** Teil dieser Lizenz — eigenes Artwork, alle Rechte
vorbehalten. Details siehe [`NOTICE`](NOTICE). Wichtig, falls dieses
Repository (oder Teile davon) irgendwann als Vorlage/Open-Source-Grundgerüst
weitergegeben werden: diese Dateien vorher entfernen bzw. durch frei
lizenzierte Icons ersetzen.
