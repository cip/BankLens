# Entwicklung: vom Issue zum Pull Request

BankLens verwendet kurze Arbeitsbranches und Pull Requests gegen `main`.
Der Hauptbranch enthält den integrierten Stand. Die Arbeitsregeln für Agenten
stehen in [AGENTS.md](../AGENTS.md); sie werden in diesem Repository gepflegt.

## Aufgabe und Issue klären

Für Fehler, neue Funktionen und größere Wartungsaufgaben wird ein Issue angelegt.
Prüfe vorher auch geschlossene Issues, damit Beobachtungen und Lösungen beim
passenden Eintrag bleiben. Kleine Nachbesserungen an einem bestehenden PR
gehören normalerweise zum selben Issue.

Ein Fehlerbericht beschreibt erwartetes und beobachtetes Verhalten,
Reproduktionsschritte und die betroffene BankLens-Version beziehungsweise den
Commit. Unbekannte Angaben bleiben als unbekannt gekennzeichnet. Trenne die
Beobachtung von einer vermuteten Ursache.

Verwende ausschließlich künstliche Beispieldaten. Keine echten Kontoauszüge,
persönlichen Dateinamen, Bankdaten oder exportierten Zahlungsnachweise in Issues,
Screenshots und PRs hochladen.

## Auf einem kurzen Branch arbeiten

Prüfe vor einer neuen Aufgabe den lokalen Arbeitsstand und den aktuellen
Hauptbranch. Bei einem sauberen Arbeitsverzeichnis kannst du beispielsweise
so beginnen:

```sh
git fetch origin main
git switch -c codex/123-kurze-beschreibung origin/main
```

Ersetze `123` durch die Issue-Nummer. Vorhandene lokale Änderungen bleiben
erhalten; bei der Fortsetzung eines PRs wird dessen eigener Branch verwendet.
Änderungen werden normalerweise über den PR integriert. Ein direkter Commit
oder Push nach `main` ist eine ausdrückliche Ausnahme des Projektinhabers.

## Passende Prüfungen ausführen

| Änderung | Relevante Prüfung |
| --- | --- |
| Dokumentation oder Vorlagen | `git diff --check`, lokale Links, Markdown- und YAML-Struktur |
| Agentenregeln oder Skills | Zusätzlich eindeutige Auslöser, gültige Skill-Frontmatter, vorhandene Referenzen und passende Berechtigungsgrenzen prüfen |
| Python-Verhalten | Betroffene Tests aus `tests/`; bei Änderungen über mehrere Module die gesamte Python-Suite |
| PDF-Erkennung oder Schwärzung | Synthetische Erkennungs- und Exportfälle, sichtbare und verdeckte Bereiche sowie Ausgabeinhalt prüfen |
| Browser-Bedienung oder Ordnersitzungen | Passende UI-Prüfung mit künstlichen PDFs; bei API-Änderungen auch Server- und Sitzungstests |

Die Befehle werden im Hauptverzeichnis mit der eingerichteten Python-Umgebung
ausgeführt. Für einen gezielten Exporttest und die gesamte Python-Suite:

```sh
python -m unittest discover -s tests -p 'test_proof.py' -v
python -m unittest discover -s tests -v
```

Die Browser-Prüfungen und ihre künstlichen Eingaben sind in
[CONTRIBUTING.md](../CONTRIBUTING.md) beschrieben. Sie dürfen nicht auf echte
Kontoauszüge umgestellt werden.

Fehlende Abhängigkeiten oder blockierte Werkzeuge werden mit dem betroffenen
Befehl dokumentiert. Ein nicht ausgeführter Test gilt nicht als bestanden.
Ein Testfehler wird untersucht und nicht durch eine bequemere Erwartung
verdeckt. Eine Reproduktion mit künstlichen Daten sagt noch nichts über alle
Layouts einer Bank aus.

## Commit und Pull Request erstellen

Commits sollen einen zusammenhängenden, prüfbaren Schritt enthalten. Pushe den
Arbeitsbranch und erstelle einen PR gegen `main` mit:

- Bezug zum Issue, etwa `Closes #123`, wenn der PR die Aufgabe vollständig löst.
- Beschreibung der Änderung und ihres Nutzens.
- Tatsächlich ausgeführten Prüfungen und ihren Ergebnissen.
- Offenen Punkten, ausgelassenen Prüfungen oder nötigen manuellen Kontrollen.

Ein Implementierungsauftrag umfasst das Vorbereiten dieses reviewbaren PRs.
Unfertige Arbeiten erhalten den Draft-Status. Verwende für Folgeänderungen
denselben Branch und aktualisiere die PR-Beschreibung auf den endgültigen Umfang.

## Review, Merge und Übergabe

Prüfe vor der Übergabe, dass Issue, PR, Zielbranch, Diff und Commit zur Aufgabe
gehören. Existierende CI-Läufe müssen dem richtigen Stand zugeordnet werden;
ein Ergebnis eines älteren Commits gilt nicht für neue Änderungen.

Ein PR wird erst nach ausdrücklicher Merge-Freigabe des Projektinhabers und nach
Erfüllung der geltenden Prüf- und Review-Anforderungen integriert. Der Auftrag,
eine Änderung zu implementieren oder zu pushen, ist keine Merge-Freigabe.
Diese Dokumentation richtet keine Branch-Protection oder automatische
Merge-Funktion ein.

Wenn für den zusammengeführten `main`-Commit CI startet, gehört deren Ergebnis
zur Übergabe. Wenn keine Workflows eingerichtet sind, wird das so benannt.
Ein Push oder ein fertiger Commit allein ist kein Nachweis erfolgreicher CI.

Die Übergabe nennt PR, Branch und Commit sowie Prüfungen und offene Punkte.
Wird später eine installierbare Anwendung oder ein Release erstellt, müssen
Download und Version zum tatsächlichen Artefakt passen. Ein Quellcode-PR
belegt noch keine getestete Installation.
