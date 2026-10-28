# Technische Details und Diagnose

Diese Dokumentation vertieft die [Anleitung im README](../README.md):
Ordnersitzungen, Erkennung, PDF-Ausgabe, lokale Speicherung und Diagnose.
Hinweise zur Entwicklungsumgebung und zu Beiträgen stehen in
[CONTRIBUTING.md](../CONTRIBUTING.md).

Alle relativen Dateipfade und Terminalbefehle beziehen sich auf das
Hauptverzeichnis des Repositorys.

## Konfiguration

Der Starter `tools/pdf-toolkit` verwendet bevorzugt die Python-Umgebung unter
`.venv/`. Mit `BANKLENS_PYTHON` lässt sich ein anderer Interpreter angeben.
Alternativ lässt sich der Server direkt mit
`python -m banklens_pdf preview /pfad/zu/den/auszuegen` starten.

`--state-dir private/andere-bank` wählt einen eigenen Ordner für Bankprofil
und Arbeitsstände. `--port` legt bei Bedarf den lokalen Port fest; ohne diese
Angabe wird ein freier Port gewählt.

Jede exportierte PDF-Seite verweist standardmäßig auf
[`github.com/cip/BankLens`](https://github.com/cip/BankLens). Für einen Fork
kann `BANKLENS_REPOSITORY_URL` vor dem Start auf
`https://github.com/OWNER/REPOSITORY` gesetzt werden. Der Vermerk und der Link
erscheinen auch in der geschwärzten Vorschau.

## Auszugsordner laden

In beiden Modi steht oben **Auszugsordner auf diesem Rechner**. **Ordner
auswaehlen …** oeffnet den Systemdialog; alternativ den lokalen Ordnerpfad
eintragen und **Pfad laden** waehlen. Vollstaendige Pfade und `~/…`
funktionieren, ebenso Pfade mit Leerzeichen oder paarigen Anfuehrungszeichen
aus dem Finder. Auf dem Mac kopiert Option+Command+C den Pfad eines im Finder
ausgewaehlten Ordners.

Das Toolkit laedt die PDF-Dateien direkt in diesem Ordner. Andere Dateitypen,
Datei-Symlinks und Unterordner werden ignoriert. Es erstellt keine Kopien der
Originale. Im Nachweis-Modus startet danach automatisch das Einlesen der
Buchungen. Die Feldwerkstatt oeffnet die erste Seite des neuen Auszugsordners.
Ein ungueltiger Pfad oder ein Fehler beim Oeffnen laesst den bisherigen
Arbeitsstand und die Ergebnisse erhalten.

Jeder Ladevorgang erhaelt eigene Sitzungs-URLs fuer beide Modi. Bereits offene
Tabs bleiben bei ihrem bisherigen Ordner; ihre Auswahl und laufende Exporte
werden nicht auf andere Dateien umgebogen. Ungespeicherte Beispiele vor dem
Verlassen eines Tabs speichern. Vorhandene Zuordnungen werden anhand der
Dateipruefsummen geladen, das Bankprofil bleibt wiederverwendbar. Sitzungs-URLs
gelten bis zum naechsten Serverneustart. Dann die Startadresse verwenden und
den gewuenschten Ordner erneut laden.

Der ausgewaehlte Ordnerpfad wird nur in lokalen API-Anfragen und in der
Oberflaeche verwendet; er erscheint weder in URLs noch in Serverlogs. Der
Server braucht Leserechte fuer den Ordner. Eingabe- und Arbeitsstandsordner
muessen getrennt bleiben.

## Zahlungsnachweise im Browser (POC ab v0.4.0)

1. Oben **Zahlungsnachweise** waehlen und **Auszuege einlesen** starten. Die
   Struktur wird aus gespeicherten Beispielen bzw. dem Bankprofil und den
   aktuellen PDF-Seiten neu berechnet. Ohne Beispiele greifen bekannte
   Spaltenkoepfe. Vorhandene Verwerfungen werden beruecksichtigt. Ungespeicherte
   Aenderungen der Feldwerkstatt vorher speichern.
2. Freitext eingeben. Alle Suchwoerter muessen innerhalb einer Buchung
   vorkommen, verteilt ueber Buchungsdatum, Wertdatum, Betrag und gesamten
   Buchungstext. Die Suche ignoriert Gross-/Kleinschreibung; Anfuehrungszeichen
   suchen eine zusammenhaengende Phrase. Leere Suche zeigt alle Buchungen.
   Nachgestellte Minuszeichen sowie Suchwerte wie `-18,00` funktionieren.
3. Passende Treffer sind vorausgewaehlt und lassen sich einzeln abwaehlen.
   Verknuepfte Fortsetzungen werden als eine Buchung mit mehreren Originalseiten
   angezeigt und durchsucht. Ungeklaerte Fortsetzungen sind sichtbar, aber fuer
   den Export gesperrt. Maximal 500 Treffer werden angezeigt; bei mehr Treffern
   die Suche eingrenzen. Ein Export umfasst hoechstens 200 Seiten.
4. **Schwaerzung in der Vorschau pruefen** zeigt ausschliesslich die maskierte
   Fassung. Zwischen den ausgewaehlten Seiten wechseln und das Ergebnis pruefen.
5. **Geschwaerzte PDF erstellen** erzeugt standardmaessig eine gemeinsame PDF
   mit allen ausgewaehlten Seiten, geordnet nach Quelldatei und Originalseite.
   Eine Seite mit mehreren Treffern erscheint nur einmal. Fortsetzungen gehoeren
   dazu. Unter **Ausgabe** bleiben Einzel-PDFs mit zusaetzlicher ZIP-Datei
   auswaehlbar; Seiten ohne ausgewaehlte Buchungen werden ausgelassen.

Jede Ausgabeseite bekommt eine Fusszeile mit **Originaldateiname und
Originalseite**. Es wird nur der Dateiname ohne Ordnerpfad uebernommen. Unter
**Quellverweis auf jeder Seite** laesst sich stattdessen die neutrale
Dokumentnummer waehlen. Lange Namen umbrechen in einem eigenen Rand unterhalb
der Originalseite, damit keine Buchungsdaten ueberdeckt werden. Umlaute werden
mit einer eingebetteten Schrift wiedergegeben. Die geschwaerzte Vorschau zeigt
dieselbe Fusszeile. Bereits erstellte PDFs bleiben unveraendert; fuer die neue
Darstellung erneut exportieren.

Erkannte Kontokopffelder lassen sich fuer Vorschau und Export getrennt
auswaehlen: Kontoinhaber 1 und 2, eigene Adresse, Kontonummer, IBAN,
Kontowaehrung, Auszugsdatum und -zeitraum sowie Anfangs- und Endsaldo.
Kontoinhaber, Adresse, Kontonummer, IBAN und Salden sind standardmaessig
ausgewaehlt. Ein Feld ohne passende Regel im Bankprofil ist deaktiviert. Auf
Seiten, fuer deren Seitenart keine passende Regel greift, bleibt es sichtbar;
die Feldliste zeigt an, ob eine Regel fuer die erste Seite, Folgeseiten oder
beide vorhanden ist. Beispiele fuer fehlende Seitenarten muessen in der
Feldwerkstatt zugeordnet und gespeichert werden. Die Auswahl wird als feste
Liste validiert und fuer Vorschau und Export gleich angewendet. Andere
Buchungen, Summen und Salden
unterhalb der Buchungstabelle werden geschwaerzt. Die Vorschau und die PDFs
entstehen aus einer anfangs schwarzen Bildflaeche, auf die nur der Kontokopf,
abzueglich der ausgewaehlten Feldmasken, sowie ausgewaehlte Buchungsbereiche
kopiert werden. Ist die Tabellengrenze nicht bekannt, bricht der Export ab.

Die Kopie ist ein neues Bild-PDF: Originaltextschichten, Anhaenge, Formulare,
Metadatenwerte und digitale Signaturen werden nicht uebernommen. Die Originale
bleiben unveraendert. Die Lesbarkeit und Vollstaendigkeit haengen weiterhin
von der Strukturerkennung ab; deshalb jede Kopie vor dem Weitergeben pruefen.
Es gibt weder OCR noch eine automatische Zusicherung der Erkennungsqualitaet.

Der Suchindex und die Auswahl bleiben im Arbeitsspeicher des lokalen Servers
bzw. Browsers. Exportdateien liegen unter `output/pdf/<zufaellige-export-id>/`
(Dateien `0600`, Exportordner `0700`) und sind von Git ausgeschlossen. Die
Downloadlinks gelten fuer die laufende Serversitzung; die Dateien bleiben
bis zum manuellen Loeschen auf der Platte. Bei neuen oder geaenderten Originalen
den Ordner erneut mit **Pfad laden** oder **Ordner auswählen …** oeffnen; dabei werden die aktuellen
Dateien und ihre Pruefsummen neu erfasst.

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
   laesst sich mit **Gewähltes Profil anwenden** auch auf andere PDFs im
   selben Layout anwenden. Mehrere lokale Profile koennen im selben `--state-dir` liegen. Die Buchungstabelle zeigt die zugeordneten Unterfelder pro Seite.

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
die lokal angefragten Seiten- bzw. Buchungstexte. Der Assistent ruft keine privaten Seiten- oder Textantworten ab. Eine lokale
Diagnose darf PDFs und Zuordnungen im Toolkit verarbeiten und ausschliesslich
die unten beschriebenen technischen Zaehler an den Chat zurueckgeben.

Der Server bindet nur an `127.0.0.1` und schuetzt seine Routen mit einem
zufaelligen Sitzungsschluessel sowie Host-/Origin-Pruefungen. Es gibt keine
externen Skripte, Schriften oder Dienste. Seitenbilder und Textlayouts bleiben
im Arbeitsspeicher; HTTP-Antworten verwenden `no-store`.

Unter `private/review/` werden auf POSIX-Systemen mit Dateirechten `0600`
gespeichert. Unter Windows werden die Dateien mit einer geschützten ACL für den
Dateieigentümer, SYSTEM und Administratoren angelegt. Ohne unterstützte ACL
schlägt das Anlegen fehl; bereits vorhandene Dateien werden nicht überschrieben:

- `field-profile.json`: bisheriges Einzelprofil, weiterhin lesbar; wird von
  neuen Speichervorgängen nicht überschrieben.
- `profiles/<id>/<revision>.json`: lokale Profile mit stabiler zufälliger ID und
  unveränderlichen Revisionen. Der frei eingegebene Profilname wird niemals als
  Dateipfad verwendet.
- `profile-selection-<set-id>.json`: zuletzt gewählte Profilreferenz für genau
  diese PDF-Prüfsummen. Bestehende Tabs behalten ihre Auswahl.
- `field-workspace-<set-id>.json`: Zuordnungen, Token-IDs und Pruefstatus,
  gebunden an Pruefsummen der konkreten PDFs. Unterschiedliche Testsets haben
  eigene Arbeitsstaende; das Bankprofil kann weiterverwendet werden.

`--state-dir private/andere-bank` trennt komplette lokale Sammlungen. Alte grafische
`review-plan.json`-Dateien bleiben erhalten, werden jedoch nicht automatisch als
Feldbeispiele interpretiert. PDFs, `private/`, `tmp/` und `output/` sind in
`.gitignore` ausgeschlossen. Browser/Betriebssystem koennen eigene
Sitzungsdaten verwalten.

## Weitere Werkzeuge und Tests

```sh
sh tools/pdf-toolkit inspect /absoluter/pfad/zum/testset --report output/inspection.json
python -m unittest discover -s tests -v
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

## Querformat-Test der groben Strukturen

```sh
python tools/create_multiline_demo_pdf.py
node tools/test_multiline_ui.cjs
```

Dieses kuenstliche PDF prueft zwei Kontoinhaber, Zwei- und Vierzeilenbuchungen,
Inline-Betraege, nachgestellte Minuszeichen, seitlichen Text und eine Buchung
ueber zwei Seiten. Keine Werte aus dem bereitgestellten Screenshot werden als
Testdaten uebernommen. Details zum Rollenmodell: [Grobe Strukturen](coarse-structure.md).

`node tools/test_proof_ui.cjs` nutzt ausschliesslich Kopien dieses kuenstlichen
Testdokuments fuer Suche, Auswahl, seitenuebergreifende Vorschau, PDF-/ZIP-Download
und Moduswechsel. Die Python-Tests pruefen zusaetzlich schwarze Pixel ausserhalb
der freigegebenen Bereiche, ausgeschlossene Fremdbuchungen und Salden sowie das
Fehlen urspruenglicher Textschichten, Metadaten und Anhaenge in der Kopie.

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


## Profilkatalog ab v0.8.0

Das mitgelieferte Bank-Austria-Profil liegt unter
[`banklens_pdf/profiles/bank-austria.json`](../banklens_pdf/profiles/bank-austria.json)
im Git. Es ist eine auf numerische Geometrie, feste Feldrollen und Formatklassen
reduzierte Fassung des lokal angelernten Profils. Private Beispiele und
Arbeitsstände gehören nicht dazu. Das Profil deckt das angelernte Layout ab;
Tests mit künstlichen Daten sind kein Nachweis für alle Bank-Austria-Formate.

| Ebene | Identität und Änderung |
| --- | --- |
| Anwendung / API | `banklens_pdf/version.py`; v0.8.0 / API 9 führt Katalog und Auswahl ein. |
| Erkennungslogik | `RECOGNITION_REVISION`; bleibt bei reiner Profilverwaltung unverändert. |
| Katalogdatei | `catalog_schema_version: 1`; enthält ID, Revision und strukturelles Profil. Unbekannte Versionen werden abgewiesen. |
| Regelstruktur | `schema_version: 1` mit unterstützter Engine `layout-examples-v1` oder `layout-examples-v2`; ältere Erkennungsrevisionen bleiben bei gleicher Regelstruktur lesbar. |
| Profilrevision | Positive ganze Zahl pro stabiler ID; jede Änderung erhält eine neue Datei. Mitgelieferte Referenz derzeit `bundled:bank-austria:1`, lokale Referenzen `local:<id>:<revision>`. |
| Arbeitsbeispiele | Explizite Auswahl `examples`; wird aus dem gespeicherten PDF-Arbeitsstand neu gelernt und ist keine feste Profilrevision. |

Lokale Revisionen liegen im gewählten `--state-dir` unter `profiles/`.
Profilname ändern erzeugt eine neue ID. Derselbe Name beim bereits ausgewählten
lokalen Profil erzeugt die nächste Revision dieser ID, auch wenn zuvor eine
ältere Revision ausgewählt war. Gleiche Anzeigenamen anderer IDs werden nicht
zusammengeführt. Speichern lernt aus den Arbeitsbeispielen; es ergänzt das
mitgelieferte Profil nicht automatisch. Ohne passende Beispiele werden nur die
Zuordnungen gespeichert. Alte Revisionen und die bisherige `field-profile.json`
bleiben erhalten. Die Auswahl wird pro PDF-Satz gespeichert, nicht global.

Ein explizit gewähltes Profil wird im Nachweis-Modus auch dann verwendet, wenn
der Arbeitsstand noch Beispiele enthält. **Arbeitsbeispiele** lässt das bisherige
Lernverhalten ausdrücklich auswählen. Die Feldwerkstatt kann mit
**Aus Beispielen erkennen** vorübergehend aus ungespeicherten Beispielen lernen;
die Statusanzeige benennt diese Quelle. Für Zahlungsnachweise zuerst speichern.
Automatische Vorschläge tragen zusätzlich den SHA-256 ihres Profils. Nach einem
Wechsel werden unpassende oder noch nicht zugeordnete alte Vorschläge ausgeblendet
und müssen neu berechnet werden.
Vorhandene Beispiele und Bestätigungen im PDF-Arbeitsstand bleiben beim Wechsel
erhalten; sie werden nicht automatisch zu Regeln des ausgewählten Profils.

Ein Profilwechsel erzeugt eigene Sitzungs-URLs und einen leeren Suchindex.
Der neue Tab muss die Auszüge neu einlesen. Bestehende Tabs, Indizes und Exporte
bleiben bei ihrer bisherigen Sitzung. Der Nachweis-Modus zeigt zusätzlich das
Profil des eingelesenen Stands, damit eine spätere Speicherung in der
Feldwerkstatt nicht als bereits neu eingelesener Stand erscheint.

`GET api/profiles` liefert Auswahl, Herkunft, Revision, Regelstruktur, Engine
und SHA-256 der Regeln; `POST api/profile/select` nimmt nur eine bekannte
Profilreferenz an und unterliegt denselben Sitzungs-, Host-, Origin- und
Request-Header-Prüfungen wie andere Änderungen. Ungültige Katalogeinträge
werden gezählt und in der Auswahl gemeldet. Ein nicht mehr verfügbares explizit
gewähltes Profil wird nicht still durch ein anderes ersetzt. Symlinks und zu
große Profildateien werden abgewiesen.

### Weitere Schritte

Die erste Stufe umfasst Auswahl, lokale Kopien, mehrere Namen, unveränderliche
Revisionen und kompatibles Lesen des Einzelprofils. Noch offen sind ein geprüfter
Import/Export, Umbenennen und Löschen einzelner Profile, eine gesonderte
Profilverwaltung ohne geladenen Auszugsordner sowie automatische Layoutzuordnung.
Eine spätere automatische Zuordnung braucht einen unabhängigen Strukturvergleich
und eine sichtbare Bestätigung; der Bankname allein genügt nicht. Neue
mitgelieferte Revisionen brauchen synthetische Erkennungs- und Schwärzungsfälle
für die betroffenen Layoutvarianten. Private Trainingsdateien werden auch dafür
nicht ins Git übernommen.
