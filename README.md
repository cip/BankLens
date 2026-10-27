# BankLens: lokale Feldwerkstatt fuer Kontoauszuege

BankLens lernt aus wenigen manuell bezeichneten Textstellen, welche Felder ein
Bankauszug enthaelt und wie Buchungen aufgebaut sind. Die erste Anwendung sind
Bank-Austria-PDFs. Import, Suche, synthetische Testdaten und Anonymisierung
koennen spaeter auf denselben Feldrollen aufbauen.

## Fokus der ersten Version

Der Hauptfall ist die Vorbereitung von Zahlungsnachweisen: Kontokopf,
Kontoinhaber als Liste und ganze Buchungen mit Buchungsdatum, Wertdatum,
rechtem Buchungsbetrag sowie vollstaendigem Buchungstext. Buchungsart,
Empfaenger, Mandatsreferenz und andere Textdetails sind optionale, nachrangige
Rollen. Zeichenfolgen wie `a/`, `?` oder Referenzpraefixe werden nicht gedeutet
oder ersetzt. Die physische Buchung wird als Einheit behandelt.

Der spaetere Nachweisablauf soll den ganzen Buchungstext durchsuchen, passende
Buchungen erhalten und andere Buchungsbloecke schwaerzen. Suchfunktion,
Nachweisauswahl, CSV-Ausgabe und echte PDF-Schwaerzung sind noch nicht
implementiert. Die aktuelle Werkstatt liefert die Struktur dafuer.

## Starten

```sh
sh tools/pdf-toolkit preview /absoluter/pfad/zum/testset
```

Die ausgegebene lokale URL im Browser oeffnen. Der Starter nutzt den vorhandenen
Codex-Python-Runtime. Alternativ Python 3.11+ mit `requirements.txt` verwenden:
`python3 -m banklens_pdf preview ...`. Beenden mit Ctrl+C im Startterminal.

## Beispiele geben und den Rest erkennen

1. Text direkt auf der PDF-Seite auswaehlen. Die Auswahl verwendet die
   tatsaechlichen PDF-Woerter und ihre Positionen, keine frei aufgezogenen
   Rechtecke. Teilweise ausgewaehlte Woerter werden vollstaendig uebernommen;
   die genaue Auswahl steht rechts. Ein Klick waehlt ein Wort, **Ganze
   Textzeile** erweitert die Auswahl auf seine physische Zeile. Auch mehrere
   Zeilen einer Buchung lassen sich gemeinsam auswaehlen.
2. Eine grobe Feldrolle zuordnen: Kontoinhaber, eigene Adresszeile 1/2/3,
   Kontonummer, IBAN, Kontowaehrung, Auszugsdatum/-zeitraum, Salden oder ganze
   Buchung. Mehrere Namenszeilen werden als separate Kontoinhaber gespeichert.
   Adressen koennen einer Person oder gemeinsam zugeordnet werden. Feinere
   Rollen erscheinen erst nach Aktivieren der optionalen Feldrollen.
3. Ein Wort in einer Buchung anklicken und **Ganze Buchung auswaehlen** nutzen.
   So wird der vollstaendige Block statt nur einer physischen Zeile markiert.
   Buchungsdatum und rechter Betrag koennen als weitere Beispiele dienen;
   der gesamte Buchungstext wird als Einheit abgeleitet. **Aus Beispielen erkennen**
   sucht auf allen Seiten des gewaehlten Dokuments oder im ganzen Testset.
   Der Vorgang zeigt Fortschritt und laesst sich nach der aktuellen Seite
   anhalten. Noch unzugeordneter Text bleibt sichtbar.
4. Vorschlaege sind gelb und von Beispielen getrennt. Uebernehmen, verwerfen
   oder korrigieren. **Als Beispiel** bzw. eine gespeicherte Korrektur fuegt
   bewusst ein weiteres Lernbeispiel hinzu. Eine Sammelbestaetigung macht
   Vorschlaege nicht automatisch zu neuen Trainingsbeispielen.
5. **Profil & Zuordnungen speichern** speichert die Arbeit lokal. Ein Profil
   laesst sich mit **Gespeichertes Profil anwenden** auch auf andere PDFs im
   selben Layout anwenden. Fuer eine andere Bank ein eigenes `--state-dir`
   verwenden. Die Buchungstabelle zeigt die zugeordneten Unterfelder pro Seite.

## Wie die erste Erkennung arbeitet

Die Engine ist regelbasiert und lokal, ohne externes Modell:

- PDFium liefert Woerter, Wortpositionen und Textzeilen. Geometrie beruecksichtigt
  Beschnitt und Seitendrehung; die automatische Erkennung ist derzeit auf
  ungedrehte, textbasierte Seiten beschraenkt. Fuer Scans fehlt noch OCR.
- Bekannte gedruckte Spaltenkoepfe und Beispielspalten unterscheiden das linke
  Buchungsdatum von Kaufdaten im Kartentext, Wertdatum und rechtem Betrag.
  Buchungen werden bis zum naechsten linken Datum als Block erfasst. Ein
  rechter Abschlussbetrag erlaubt unterschiedlich viele Fortsetzungszeilen.
  Inline-Betraege bleiben Teil des Buchungstexts.
- Der gesamte Textblock wird ohne Deutung von Kuerzeln erhalten. Nur die
  getrennten Buchungs-/Wertdaten und der rechte Betrag werden dem Textfeld
  entnommen. Zeichen innerhalb der Woerter bleiben unveraendert; Abstaende und
  Zeilenumbrueche werden aus den PDF-Wortpositionen rekonstruiert.
- Seitliche gedrehte Stempel und bekannte Fortsetzungsfusszeilen gehoeren nicht
  zur Buchung. Offene Bloecke werden gekennzeichnet; ein passender Anfang der
  direkt folgenden Seite kann als Fortsetzung verknuepft werden. Die beiden
  Seitenbereiche bleiben separat adressierbar.
- Offensichtlich unpassende Beispiele, etwa die Ueberschrift Betrag statt
  eines Betragswerts, werden in der UI abgewiesen bzw. beim Lernen ignoriert.
  Kontoinhaber sind wiederholbare Eintraege, kein einzelnes Namensfeld.
- Kopfpositionen, Spaltentitel und Datumsformate bleiben Layoutannahmen.
  Nicht erkannte Seitengrenzen, andere Formate und reine Bildseiten koennen
  weitere Regeln brauchen. Eine vollstaendige Bank-Austria-Erkennung ist noch
  nicht nachgewiesen. Die Originale werden vom Assistenten nicht gelesen.
- Verwerfungen bleiben an den jeweiligen Dokumenttext gebunden. Korrekturen
  sind explizite neue Beispiele. Ein Profil ist kein anonymisierter Datensatz.

## Lokale Speicherung und Datenschutzgrenze

Originale bleiben ausserhalb des Projekts und werden nur lesend geoeffnet.
Keine Originaltexte, Dateinamen oder Metadatenwerte erscheinen in CLI-Ausgaben
oder Serverlogs. Nur der Browser des Benutzers erhaelt die Seitenbilder und
den Originaltext der jeweils angezeigten Seite. Der Assistent ruft keine privaten Seiten- oder Textantworten ab. Eine lokale
Diagnose darf PDFs und Zuordnungen im Toolkit verarbeiten und ausschliesslich
die unten beschriebenen technischen Zaehler an den Chat zurueckgeben.

Der Server bindet nur an `127.0.0.1` und schuetzt seine Routen mit einem
zufaelligen Sitzungsschluessel sowie Host-/Origin-Pruefungen. Es gibt keine
externen Skripte, Schriften oder Dienste. Seitenbilder und Textlayouts bleiben
im Arbeitsspeicher; HTTP-Antworten verwenden `no-store`.

Unter `private/review/` werden mit Dateirechten `0600` gespeichert:

- `field-profile.json`: wiederverwendbare Feldrollen, Formatklassen und
  Layoutregeln. Keine ausgelesenen Beispielwerte oder Originaldateinamen;
  der Profilname wird vom Benutzer eingegeben.
- `field-workspace-<set-id>.json`: Zuordnungen, Token-IDs und Pruefstatus,
  gebunden an Pruefsummen der konkreten PDFs. Unterschiedliche Testsets haben
  eigene Arbeitsstaende; das Bankprofil kann weiterverwendet werden.

`--state-dir private/andere-bank` trennt Bankprofile. Alte grafische
`review-plan.json`-Dateien bleiben erhalten, werden jedoch nicht automatisch als
Feldbeispiele interpretiert. PDFs, `private/`, `tmp/` und `output/` sind in
`.gitignore` ausgeschlossen. Browser/Betriebssystem koennen eigene
Sitzungsdaten verwalten.

## Weitere Werkzeuge und Tests

```sh
sh tools/pdf-toolkit inspect /absoluter/pfad/zum/testset --report output/inspection.json
/Users/cip/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests -v
node tools/test_preview_ui.cjs
```

`inspect` meldet nur neutrale Dokumentnummern, Seitenzahlen und technische
Statuswerte. Es anonymisiert nichts. Der Bericht muss eine neue JSON-Datei
ausserhalb des Eingabeordners sein.

Tests verwenden ausschliesslich kuenstliche PDFs/Layouts. Sie pruefen unter
anderem native Textauswahl im Browser, Erkennung aus einem mehrzeiligen
Beispiel, Uebertragung auf geaenderte Werte und Zeilenpositionen, Ablehnung von
Vorschlaegen, Speicherung ohne Beispielwerte, Zugriffsschutz und unveraenderte
Quelldateien. Der UI-Test erwartet `tmp/demo-input/example.pdf`, erzeugbar mit
`tools/create_demo_pdf.py`; er darf niemals auf echte Auszuege umgestellt werden.

## Noch offen

- Verifizierte Bank-Austria-PDF-Spezifikation bzw. dokumentierte Sonderfaelle
  einarbeiten; siehe `docs/bank-format-sources.md`.
- Weitere Layoutvarianten, OCR und mehrdeutige oder mehrseitige Fortsetzungen.
- Zahlungsnachweissuche ueber den ganzen Buchungstext und passende Blockauswahl.
- Strukturierter Import und Suche ueber alle Auszuege.
- Synthetische Testauszuege und echte PDF-Anonymisierung mit separater
  Nachpruefung. Die Feldwerkstatt exportiert bisher keine anonymisierten PDFs.

## Querformat-Test der groben Strukturen

```sh
/Users/cip/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tools/create_multiline_demo_pdf.py
node tools/test_multiline_ui.cjs
```

Dieses kuenstliche PDF prueft zwei Kontoinhaber, Zwei- und Vierzeilenbuchungen,
Inline-Betraege, nachgestellte Minuszeichen, seitlichen Text und eine Buchung
ueber zwei Seiten. Keine Werte aus dem bereitgestellten Screenshot werden als
Testdaten uebernommen. Details zum Rollenmodell: `docs/coarse-structure.md`.

## Versionen und Diagnose

Die Oberflaeche zeigt ihre Version im Kopf. Backend und Oberflaeche pruefen die
API-Version; bei einem aelteren laufenden Server erscheint ein Neustarthinweis.
Automatische Vorschlaege tragen eine Erkennungsrevision. Nicht versionierte
oder aeltere Vorschlaege werden ausgeblendet und koennen mit **Vorschlaege neu
berechnen** ersetzt werden. Beispiele und Bestaetigungen bleiben erhalten.
Die Standardansicht zeigt Kopfbereiche und zusammenhaengende Buchungsrahmen;
Unterfelder lassen sich ueber den Filter einblenden.

Die Fortsetzungsuebergabe ist unabhaengig davon, ob der Beginn neu vorgeschlagen,
bereits als Beispiel gespeichert oder bestaetigt wurde. Status und Verknuepfung
werden aus der aktuellen Blockberechnung abgeleitet; Seitenausschnitte bleiben
separat adressierbar.

```sh
sh tools/pdf-toolkit diagnose /absoluter/pfad/zum/testset --document 1 --page 3
```

Dieser reine Lesevorgang verarbeitet PDFs und Beispiele ausschliesslich lokal.
Die Ausgabe enthaelt nur technische Zaehler (Blockanfaenge, offene Bloecke,
Verknuepfungen, alte Vorschlaege, gedrehten Text) und Versionsangaben. Keine
Originaltexte, Namen, Kontodaten, Token-IDs oder Dateinamen werden ausgegeben;
kein Arbeitsstand wird gespeichert oder ueberschrieben. So kann der Assistent
Fehler untersuchen, ohne die privaten Inhalte in den Chat zu uebernehmen.

## Reparatur bestehender Feldzuordnungen

Ab v0.3.2 werden vorhandene Betrags-, Datums- und andere Buchungsfelder beim
Laden wieder einem eindeutig passenden gespeicherten Block zugeordnet, wenn
ihre Verbindung fehlt oder auf einen entfernten Block zeigt. Feldinhalt,
Auswahl und Pruefstatus bleiben erhalten. Mehrdeutige Zuordnungen werden nicht
geraten. Die Reparatur wird zunaechst nur im geladenen Arbeitsstand angewendet;
die Oberflaeche kennzeichnet ihn als ungespeichert. Erst explizites Speichern
schreibt die korrigierten Verknuepfungen auf die Platte.

Eine erneute Erkennung uebermittelt zusaetzlich Verknuepfungen fuer bereits
vorhandene Beispiele und bestaetigte Felder. Damit wird ein existierender
Betrag nicht nur wegen seiner frueheren Markierung als erledigt behandelt,
wenn ihm noch die Verbindung zur neu erkannten Buchung fehlt.

## Schlussseite und Summenbereich

Ab v0.3.3 begrenzen die Abschlussbeschriftungen alter/neuer Kontostand sowie
Summe der Belastungen/Gutschriften die Buchungstabelle. Die Zahl im rechten
Kontostandskasten darf nicht als Betrag der letzten Buchung verwendet werden.
Ein einzelner alter Kontostand oberhalb der ersten Buchung beendet die Tabelle
nicht. Die Tests enthalten sowohl diesen Fall als auch eine Schlussseite mit
vier Summen-/Saldofeldern. Nach Aktualisierung dieser Erkennungsregel muessen
alte Vorschlaege neu berechnet werden; Beispiele und Bestaetigungen bleiben
bestehen. Die Diagnose meldet dazu nur Grenz- und Trefferzaehler, keine Werte.
