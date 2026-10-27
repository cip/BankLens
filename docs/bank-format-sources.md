# Formatquellen: Bank Austria

Geprueft am 27.10.2026. Diese Quellen sind Hintergrund, keine verifizierte
Spezifikation fuer die sichtbare Anordnung in den vorliegenden Privatkunden-PDFs.
In der ersten Engine sind keine daraus abgeleiteten PDF-Spalten fest codiert.

| Quelle | Belegt | Grenze fuer dieses Toolkit |
| --- | --- | --- |
| [24You: E-Kontoauszuege](https://www.bankaustria.at/online-banking-24you.jsp) | E-Kontoauszuege werden als PDF bereitgestellt. | Keine technische Feld- oder Koordinatenspezifikation. |
| [Kontoauszugsdienst](https://www.bankaustria.at/firmenkunden-kontoauszugsdienst.jsp) | MT940/MT942 sowie auf Anfrage camt.052/camt.053 fuer Firmenkunden. | Strukturierte Nachrichten sind keine Beschreibung des PDF-Layouts. |
| [BusinessLine News: MT940](https://www.bankaustria.at/firmenkunden-businessline-news.jsp) | SEPA-Bezeichner EREF+, MREF+, KREF+ sowie Feld-61/-86-Hinweise und Verweis auf die oesterreichische STUZZA-Dokumentation. | Nicht als Nachweis verwenden, dass dieselben Bezeichner oder Felder in jedem PDF vorkommen. |
| [Flugblatt eKontoauszug](https://www.bankaustria.at/files/FB_eKontoauszug_deutsch.pdf) | PDF-Auszug mit Belegen, Volltextsuche, Firmenkunden-Kontext. | Produktbeschreibung, keine Parser-Spezifikation. |

Der vom Benutzer erwaehnte fruehere Projektchat wurde gefunden. Die
Chat-Schnittstelle liefert fuer die damaligen Assistentenantworten jedoch nur
Inhaltsreferenzen. Die konkrete damalige Formatquelle ist dadurch bisher nicht
verifiziert. Sobald ihr Link vorliegt, Inhalt/Version und Anwendbarkeit auf die
PDFs pruefen; keine unbestaetigte Quelle als bereits implementiert ausweisen.
