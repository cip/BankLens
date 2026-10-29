# Windows-Paket: Stand der Lizenzprüfung

Stand: 29. Oktober 2026. Diese Bestandsaufnahme ist keine Freigabe zur
öffentlichen Verteilung. Grundlage sind der CI-Lauf für Commit `f4661ea`, seine
Installations- und Build-Protokolle sowie die dazugehörigen Windows-Pakete.
Ein installiertes Paket wurde für diese Bestandsaufnahme nicht vollständig
inventarisiert. Spätere Builds können andere Abhängigkeitsversionen enthalten.

## Feststellungen

- BankLens steht unter [GPL-3.0-only](../LICENSE). Der Installer legt die
  BankLens-Lizenz und [Copyright-Angaben](../COPYRIGHT.md) jetzt bei. Bei einer
  Verteilung des Binärpakets sind außerdem die GPL-Pflichten zur Bereitstellung
  des entsprechenden Quellcodes und der weiteren erforderlichen Unterlagen
  anhand des konkreten Verteilungswegs zu erfüllen. Ein Link auf den aktuellen
  Repository-Stand allein belegt das nicht.
- Der Windows-Build installiert unter anderem pypdf 6.10.0 (BSD-3-Clause),
  pypdfium2 5.14.0 (BSD-3-Clause und Apache-2.0 sowie weitere Lizenzen seiner
  PDFium-Binärdatei), Pillow 12.3.0 (MIT-CMU), ReportLab 4.4.9 (BSD),
  pywebview 5.4 (BSD-3-Clause), pythonnet 3.2.1 (MIT), clr_loader 0.3.1
  (MIT), cffi 2.1.1 (MIT-0), pycparser 3.12 (BSD-3-Clause), bottle 0.13.4
  (MIT), charset-normalizer 3.5.2 (MIT) und typing_extensions 4.16.0
  (PSF-2.0). Die Angaben stammen aus den Metadaten und Lizenzdateien der für
  diesen Lauf ermittelten Pakete; sie sind keine vollständige Inhaltsliste des
  Installers. Insbesondere enthalten PDFium, Pillow, ReportLab und Python
  weitere Bestandteile mit eigenen Lizenztexten und Hinweisen.
- `proxy_tools` 0.1.0 meldet in den Paketmetadaten MIT, nennt im Quelltext
  hingegen BSD und enthält im heruntergeladenen Quellpaket keine Lizenzdatei.
  Das [Upstream-Repository](https://github.com/jtushman/proxy_tools) enthält
  eine Lizenzdatei; deren Zuordnung zur konkret verwendeten Version und der
  Widerspruch müssen vor Veröffentlichung geklärt werden.
- [PyInstaller 6.11.1](https://pyinstaller.org/en/v6.11.1/license.html) hat
  für erzeugte Programme eine Ausnahme; die Bedingungen der gebündelten
  Abhängigkeiten bleiben trotzdem zu erfüllen. NSIS ist ein Build-Werkzeug;
  welche Teile und Hinweise im konkreten Installer betroffen sind, ist noch zu
  prüfen.
- pywebview enthält WebView2-SDK-Bibliotheken. Die separat installierte
  WebView2-Runtime ist nicht gleichbedeutend mit diesen Bibliotheken und wird
  durch das aktuelle Buildskript nicht als Runtime-Installer mitgeliefert.
  Versionsbezogene Lizenz- und Hinweistexte der tatsächlich enthaltenen SDK-
  Dateien sowie die [Microsoft-Verteilungshinweise](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution)
  sind für die gewählte Verteilung zu prüfen.

## Vor öffentlicher Verteilung offen

1. Den tatsächlich installierten Paketinhalt einschließlich nativer Bibliotheken,
   eingebetteter Schriften und Toolchain-Artefakte inventarisieren und den
   konkreten Paketversionen und Quellen zuordnen; Abhängigkeiten reproduzierbar
   festlegen.
2. Vollständige Copyright-, Lizenz- und gegebenenfalls NOTICE-Texte sämtlicher
   tatsächlich verteilter Komponenten zusammenstellen, insbesondere PDFium,
   Pillow-Abhängigkeiten, Python, ReportLab-Schriften und WebView2-SDK.
   Diese Texte bei jedem Installer-Build beilegen und das fertige Artefakt
   darauf prüfen. Die im Installer enthaltene BankLens-Lizenz allein reicht
   dafür nicht aus.
3. Die widersprüchlichen Angaben zu `proxy_tools` anhand der konkreten Version
   klären und die einschlägigen Hinweise beilegen.
4. Das Angebot des zum Binärpaket passenden Quellcodes und die übrigen
  GPL-Verteilungspflichten für den geplanten Veröffentlichungsweg festlegen.
  Ein Installer-Artefakt ist bis dahin kein öffentliches Release.
5. Impressums- und Informationspflichten anhand von Sitz und konkretem
   Vertriebsmodell gesondert prüfen; ein GitHub-Link ersetzt diese Prüfung nicht.
