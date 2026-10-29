# Windows-Paket: Lizenz- und Quellcodeprüfung

Stand: 29. Oktober 2026. Diese technische Bestandsaufnahme dokumentiert den
Windows-Build aus PR #11; sie ist keine Rechtsberatung oder automatische Freigabe
für die öffentliche Verteilung. Das konkrete Installer-Artefakt und sein
Quellcode-Commit sind für jede Verteilung erneut zu prüfen.

## Was der Build beilegt und prüft

- BankLens steht unter [GPL-3.0-only](../LICENSE). `LICENSE.txt` und
  `COPYRIGHT.md` liegen im Installationsverzeichnis. `BankLens-Quellcode.zip`
  enthält den mit `git archive` erzeugten Quellstand des Builds;
  `Quellcode-Commit.txt` benennt den Commit. Der Build lehnt Änderungen an
  bereits verfolgten Dateien ab.
- `Lizenzen/` enthält Lizenz- und Copyright-Texte aus den festgelegten
  Python-Paketen, einschließlich der PDFium-Abhängigkeiten und ReportLab-
  Schrifthinweise. Zusätzliche versionsgebundene Texte für Python, Pillow-
  Bibliotheken, WebView2-SDK und `proxy_tools` liegen unter `Lizenzen/zusatz/`.
  Die Pillow-SBOM wird mit den Paketmetadaten gesammelt. `paketversionen.json`
  dokumentiert die installierten Paketversionen und aufgefundenen Lizenzdateien;
  `paket-downloads.json` enthält SHA-256-Prüfsummen der heruntergeladenen Pakete.
- `Paketinhalt.json` listet Dateien des vorbereiteten Pakets und ihre SHA-256-
  Prüfsummen auf. Die CI entpackt den Installer und vergleicht alle vorbereiteten
  Dateien mit den enthaltenen Dateien. Sie
  veröffentlicht Paketliste, Paketversionen und PyInstaller-Inventar als
  gesonderten Nachweis zum jeweiligen Lauf.
- Der Windows-Build verwendet Python 3.11.9 und festgelegte Paketversionen;
  CI verwendet NSIS 3.13.0. PyInstaller 6.11.1 hat eine
  [Ausnahme für erzeugte Programme](https://pyinstaller.org/en/v6.11.1/license.html).
  Das Skript verwendet keine NSIS-Plugins und legt zlib als Kompression fest.
- Im untersuchten CI-Paket `91a1f9e` wurden Windows-Systemlaufzeitdateien aus
  einer auf dem Runner vorhandenen Java-Installation übernommen. Dieser
  unbeabsichtigte Ursprung ist für eine Verteilung nicht belegt. Der Build
  entfernt Java-Verzeichnisse aus dem Suchpfad und schließt diese Windows-
  Systemlaufzeitdateien aus dem Paket aus. Das nicht für Windows benötigte
  `pywebview-android.jar` wird entfernt; der Build prüft anschließend, dass
  keine Java-Laufzeit oder JAR-Dateien eingebunden sind. Das Paket setzt die
  Microsoft Visual C++ 2015–2022 Runtime (x64) als Systemvoraussetzung voraus.
  Der Installer prüft den offiziellen Registry-Eintrag und bietet bei fehlender
  Runtime den Download von Microsoft an; danach muss der Nutzer BankLens-Setup
  erneut starten. Die Runtime-DLLs werden nicht mitgeliefert. Build und CI
  prüfen, dass keine `VCRUNTIME*.dll` im App-Paket enthalten ist. Der
  Windows-CI-Selbsttest läuft auf einem Runner mit installierter Runtime; das
  Fehlen der Runtime auf einem sauberen Windows-System wird nicht simuliert.
- Der nicht benötigte Testfont `reportlab/fonts/hb-test.ttf` wird aus dem
  Paket entfernt. Die verwendbaren Vera-Schriften und ihre Lizenzdatei bleiben
  erhalten.
- Die in pywebview 5.4 enthaltenen WebView2-SDK-DLLs entsprechen bytegenau dem
  Microsoft-SDK 1.0.2957.106; ihr Lizenztext liegt bei und die SHA-256-Werte
  werden im Build geprüft. Die separat installierte WebView2-Runtime wird nicht
  mitgeliefert. Für deren Verteilung gelten gesonderte
  [Microsoft-Hinweise](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution).
- Bei `proxy_tools` 0.1.0 nennen die Paketmetadaten MIT, der Quelltext dagegen
  BSD. Der Paketquelltext ist bytegleich mit dem historischen Upstream-Commit
  `77369e4d321ed7b10d7b6e4885d7fe7a7ec2dfb7`, der den zugehörigen BSD-Text
  enthält. Dieser Text liegt bei; der Build prüft die Quelltext-Prüfsumme. Der
  Widerspruch in den Metadaten ist bei einer Änderung des Pakets erneut zu prüfen.

## Vor öffentlicher Verteilung

Die Paketliste und das PyInstaller-Inventar des konkreten CI-Laufs müssen auf
mitgelieferte native Komponenten, insbesondere Microsoft-Laufzeitbibliotheken,
und deren Verteilungsbedingungen überprüft werden. Lizenzbeilagen und ein
Quellcodearchiv allein belegen nicht automatisch sämtliche GPL- oder sonstigen
Verteilungspflichten für jeden Vertriebsweg. Der gewählte Vertriebsweg muss den
zum tatsächlich verteilten Binärstand passenden vollständigen entsprechenden
Quellcode und die erforderlichen Rechte und Hinweise zugänglich machen.

Frühere geprüfte Pakete enthielten `VCRUNTIME140.dll` aus der Python-3.11.9-
Installation. Der aktuelle Build entfernt verbliebene `VCRUNTIME*.dll` und
weist deren Anwesenheit zurück. Das vermeidet die direkte Mitlieferung dieser
Runtime-Dateien durch BankLens. Im Paket enthaltene CPython-Binärdateien
können weiterhin Microsoft Distributable Code enthalten; der
[CPython-Hinweis](https://github.com/python/cpython/blob/v3.11.9/PC/crtlicense.txt)
liegt daher bei und Microsoft-Bedingungen für diese Bestandteile sind vor
öffentlicher Verteilung weiterhin zu prüfen. Die
[Microsoft-Verteilungshinweise](https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files)
beschreiben die Runtime-Voraussetzung und deren Installation.

Die Impressums- und Informationspflichten hängen zusätzlich von Sitz und
konkretem Vertriebsmodell ab; ein GitHub-Link ersetzt diese Prüfung nicht.
