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
- Die von PyInstaller gesammelten Paketdateien bleiben erhalten. Insbesondere
  werden weder Pythons `VCRUNTIME140.dll` noch pywebviews Android-JAR oder
  ReportLabs Testfont nachträglich gelöscht. Das Android-JAR enthält nur
  pywebview-Klassen und installiert oder startet keine Java-Laufzeit.
- Die DLL-Suche verwendet einen begrenzten Suchpfad mit der ausgewählten Python-
  Installation, Windows und den Build-Werkzeugen. Der Build lehnt native
  Abhängigkeiten aus fremden Java-Installationen ab. Dies verhindert zufällige
  Übernahmen vom CI-Rechner, ohne Bestandteile der Abhängigkeiten zu löschen.
  `VCRUNTIME140.dll` muss bytegleich mit der Datei aus Python 3.11.9 sein.
- Die Weitergabe von Python in Quell- und Binärform ist nach der
  [PSF-Lizenz von Python 3.11.9](https://github.com/python/cpython/blob/v3.11.9/LICENSE)
  erlaubt. Lizenz und Copyright-Hinweise werden mitgeliefert. BankLens bündelt
  den unveränderten Interpreter und eine durch PyInstaller zusammengestellte
  Auswahl der Bibliotheken; Python selbst wird nicht gepatcht. Python führt
  Versionen ab 2.2 als GPL-kompatibel auf.
- Der unveränderte ReportLab-Testfont `hb-test.ttf` enthält einen Ausschnitt
  aus Noto Sans Khmer, Copyright 2022 The Noto Project Authors. Die SIL OFL 1.1
  erlaubt die gebündelte Weitergabe; ihr Text liegt zusätzlich bei. Der Build
  prüft diesen Font und das Android-JAR gegen die installierten Paketdateien.
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

Der [Windows-Hinweis von CPython 3.11.9](https://github.com/python/cpython/blob/v3.11.9/PC/crtlicense.txt)
beschreibt die Weitergabe von Microsoft Distributable Code mit dem Python-
Windows-Build. Er erlaubt sie unter den dort genannten Voraussetzungen:
Microsoft-Hinweise nicht verändern, keine Microsoft-Unterstützung suggerieren,
nur für Microsoft-Plattformen verteilen und nicht für schädliche oder täuschende
Programme verwenden. Diese Vorgaben werden für BankLens berücksichtigt; der
vollständige Hinweis liegt bei. Der Hinweis spricht zusätzlich die Zustimmung
externer Nutzer und Weiterverteiler zu Schutzbedingungen für Microsoft-Code an.
Der Installer zeigt deshalb den vollständigen unveränderten CPython-Hinweis
vor dem Kopieren der Dateien und verlangt die Zustimmung ausdrücklich nur für
Microsoft Distributable Code. BankLens bleibt unter GPL-3.0-only; die Seite
fügt dessen Lizenz keine zusätzlichen Bedingungen hinzu. Der Hinweis bleibt
auch nach der Installation im Lizenzverzeichnis zugänglich. Die technische
Umsetzung ersetzt keine individuelle Rechtsberatung, dokumentiert aber die
konkrete Weitergabebedingung und ihre Umsetzung. Eine Notwendigkeit zum
Entfernen einzelner Dateien wurde aus dem Hinweis nicht abgeleitet.

Die Impressums- und Informationspflichten hängen zusätzlich von Sitz und
konkretem Vertriebsmodell ab; ein GitHub-Link ersetzt diese Prüfung nicht.
