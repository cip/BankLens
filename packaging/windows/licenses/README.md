# Lizenztexte zusätzlicher Bestandteile

Diese Dateien ergänzen die bei jedem Build aus den installierten Paketen
gesammelten Lizenztexte. Sie stammen aus folgenden versionsgebundenen Quellen:

- `python-3.11.9.txt`: [CPython 3.11.9](https://github.com/python/cpython/blob/v3.11.9/LICENSE).
- `python-3.11.9-weitere-lizenzen.rst`: [Lizenzdokumentation von CPython 3.11.9](https://github.com/python/cpython/blob/v3.11.9/Doc/license.rst).
- `python-3.11.9-microsoft-crt.txt`: [Hinweis zu Microsoft Distributable Code von CPython 3.11.9](https://github.com/python/cpython/blob/v3.11.9/PC/crtlicense.txt).
- `pillow-dependencies/`: [Pillow 12.3.0, wheels/dependency_licenses](https://github.com/python-pillow/Pillow/tree/12.3.0/wheels/dependency_licenses).
  Die Sammlung ist vorsorglich breiter als die tatsächlich im Paket verwendeten
  Bibliotheken. Pillow liefert zusätzlich eine SBOM in den Paketmetadaten.
- `webview2-sdk-1.0.2957.106.txt`: `LICENSE.txt` aus dem Microsoft-NuGet-Paket
  `Microsoft.Web.WebView2` 1.0.2957.106. Die in pywebview 5.4 enthaltenen
  SDK-DLLs wurden bytegenau mit diesem Paket verglichen; der Build prüft ihre
  SHA-256-Werte erneut. Die separat installierte WebView2-Runtime ist nicht
  enthalten.
- `proxy_tools-0.1.0-BSD.txt`: [Upstream-Lizenz](https://github.com/jtushman/proxy_tools/blob/77369e4d321ed7b10d7b6e4885d7fe7a7ec2dfb7/LICENSE.txt).
  Der Paketquelltext ist bytegleich mit dem Quelltext dieses Commits, der BSD
  nennt; die Paketmetadaten nennen dagegen MIT. Der Build prüft den Quelltext
  anhand seiner SHA-256-Prüfsumme. Die widersprüchlichen Metadaten bleiben
  dokumentiert und sollten bei einer späteren Aktualisierung erneut geprüft
  werden.

- `noto-sans-khmer-OFL.txt`: [SIL OFL 1.1 von Noto Sans Khmer](https://github.com/notofonts/khmer/blob/main/OFL.txt), Copyright 2022 The Noto Project Authors. Der unveränderte ReportLab-Testfont `hb-test.ttf` enthält diesen Copyright-Eintrag; der Build prüft seine SHA-256-Prüfsumme.
