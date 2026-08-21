# Portfolio — öffentliche Ansicht

Flask-Anwendung, die die öffentlichen Seiten eines Portfolios dynamisch aus
einem dateibasierten Inhaltsverzeichnis rendert (kein Build-Schritt, keine
Datenbank). Siehe `content/uploads/anforderungskatalog-portfolio.md` (falls
vorhanden) für die vollständigen Anforderungen; diese Anwendung deckt den
öffentlichen Teil (`web`) ab — kein Admin, kein Deployment-Setup.

## Entwicklung

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
flask --app wsgi run --debug
```

Die Anwendung liest Inhalte aus `./content` (überschreibbar über die
Umgebungsvariable `CONTENT_DIR`). Struktur:

```
content/
  beitraege/oeffentlich/<datum>-<slug>/{meta.json, inhalt.md, medien/}
  seiten/{impressum.md, datenschutz.md, ueber-mich.md}
  site.config.json
```

In Produktion liegt dieses Verzeichnis außerhalb des Repositories (Bind-Mount);
für diese Demo ist es mit Platzhalterinhalten eingecheckt.

## Tests

```bash
pytest
```
