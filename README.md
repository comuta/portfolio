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

Das startet `web` (`http://127.0.0.1:8081`) und `admin`
(`http://127.0.0.1:8082`) mit Demo-Inhalten aus `./content`. Die eigentlichen
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

In Docker Compose ist `./data` das eigentliche Laufzeitverzeichnis (entspricht
`/var/lib/portfolio` in Produktion) — ein separates, git-ignoriertes
Verzeichnis, weil es selbst ein Git-Repository ist (FA-41) und das nicht mit
diesem Code-Repository verschachtelt sein darf. Beim ersten Start richtet der
`init`-Dienst die Struktur ein und kopiert optional die Demo-Inhalte aus
`./content`.

## Tests

```bash
pytest
```

38 Tests: `tests/` für `web` (Slug-Auflösung, Pfad-Traversal-Schutz,
Markdown-Sanitisierung, Fehlerseiten), `tests/admin/` für `admin`
(Anmeldung/TOTP/Rate-Limit, CSRF, Medien-Upload-Validierung,
CRUD-Lebenszyklus, strukturelle Trennung privat/öffentlich).
