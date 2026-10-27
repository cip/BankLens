# V1: grobe Strukturen fuer Zahlungsnachweise

Die Werkstatt kennzeichnet Kopfbereiche und Buchungen. Sie interpretiert nicht
die Bedeutung einzelner Kuerzel oder interner Kennungen im Buchungstext.

| Ebene | Rollen | Zweck |
| --- | --- | --- |
| Kontokopf | Wiederholbares `owner.name`, Adresszeilen, Kontonummer/IBAN, Kontowaehrung | Personen und Konto zum Auszug zuordnen; spaeter zentrale Angaben maskieren. |
| Auszug | Auszugsdatum/-zeitraum und Salden | Kontext zum jeweiligen Dokument. |
| Buchung | `transaction.row` | Gesamten physischen Block einschliesslich seiner Zeilen und Positionen adressieren. |
| Grobe Werte | `transaction.booking_date`, `transaction.value_date`, `transaction.amount` | Daten und rechten Buchungsbetrag separat erfassen. |
| Volltext | `transaction.full_text` | Alle verbleibenden Textzeilen gemeinsam fuer die spaetere Suche verwenden. Auch Inline-Betraege und Kaufdaten bleiben darin. |

Zuordnungen speichern PDF-Token-IDs statt kopierter Originaltexte. Die exakten
Zeichen innerhalb der Woerter bleiben erhalten; Abstaende/Zeilenumbrueche
werden aus dem Layout rekonstruiert. Eine Zeichenfolge mit Fragezeichen wird
nicht ohne Nachweis in eine vermeintlich richtige Schreibweise umgewandelt.

`owner.name` ist eine Liste eigenstaendiger Zuordnungen. `entity_id` identifiziert
einen neutralen Platz wie `holder-1` oder `holder-2`; Adressfelder koennen auf
diesen Platz verweisen oder gemeinsam gelten. Das Profil speichert keine Namen.

An einer Seitengrenze bleibt ein offener Block mit `partial` markiert. Wird
die passende Fortsetzung auf der direkt folgenden Seite gefunden, verweist
`continuation_of` auf den Beginn; dieser erhaelt `continued_on`. Die Positionen
beider Seiten bleiben erhalten. Ein unvollstaendiger Block wird nicht durch
einen geratenen Betrag vervollstaendigt. Mehrdeutige bzw. ueber mehrere Seiten
reichende Fortsetzungen sind noch nicht allgemein geloest.

Fuer den vorgesehenen Zahlungsnachweis soll spaeter der gesamte Buchungstext
gematcht und der passende Block erhalten werden. Andere Bloecke werden dann
als Einheiten geschwaerzt. Die aktuelle Version fuehrt diese Suche,
Nachweiserstellung, Schwaerzung und CSV-Ausgabe noch nicht aus.

Empfaenger, Textausschnitt, Mandatsreferenz und Creditor-ID sind optionale
Feldrollen fuer spaetere Erweiterungen. Ihre Erkennung ist keine Voraussetzung
fuer die Erfassung einer vollstaendigen Buchung.
