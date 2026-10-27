# Beitraege zu BankLens

Danke, dass du BankLens verbessern moechtest. Issues und Pull Requests sind
willkommen.

## Aenderungen vorbereiten

- Halte Aenderungen klein und beschreibe den beobachteten Fehler oder Nutzen.
- Verwende ausschliesslich kuenstliche oder synthetische Auszugsdaten in
  Beispielen und Tests. Lade niemals echte Kontoauszuege, Namen, IBANs,
  Kontostaende, Originaldateinamen oder Export-PDFs in GitHub hoch.
- Aktualisiere README oder `docs/`, wenn sich Bedienung, Grenzen oder
  Datenschutzverhalten aendern.
- Beitraege werden unter GPL-3.0-only veroeffentlicht. Wenn du zusaetzlich
  erlauben moechtest, dass dein Beitrag spaeter unter anderen Bedingungen
  lizenziert wird, klaere das ausdruecklich vor dem Merge.
- Fuehre die passenden Pruefungen mit den kuenstlichen Testdaten aus.

## Entwicklungsumgebung

Python 3.11+ und Node.js werden fuer die Entwicklung benoetigt. Die Python-
Abhaengigkeiten lassen sich wie im README installieren:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Die Browser-Tests benoetigen ausserdem Playwright fuer Node.js sowie einen
installierten Chrome-Browser. Falls Node.js Playwright nicht direkt aufloesen
kann, kann `BANKLENS_PLAYWRIGHT_PATH` auf das Playwright-Modul zeigen.

## Kuenstliche Pruefungen

```sh
python -m unittest discover -s tests -v
python tools/create_demo_pdf.py
node tools/test_preview_ui.cjs
python tools/create_multiline_demo_pdf.py
node tools/test_multiline_ui.cjs
node tools/test_proof_ui.cjs
```

Die UI-Pruefungen verwenden nur die erzeugten Dateien unter `tmp/`. Niemals
Testskripte auf echte Kontoauszuege umstellen. Generierte PDFs, persoenliche
Arbeitsstaende und lokale Beispieldateien gehoeren nicht in Commits.

Details zu Erkennung, Speicherung, Konfiguration und Diagnose stehen in der
[technischen Dokumentation](docs/technical-details.md).
