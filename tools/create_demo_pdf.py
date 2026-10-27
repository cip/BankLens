"""Create an entirely synthetic, two-page input for UI testing only."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.pdfgen import canvas


def main():
    output = Path("tmp/demo-input/example.pdf")
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output), pagesize=(595, 842))
    pdf.setTitle("BankLens synthetic UI fixture")
    for page in range(1, 3):
        pdf.setFillColor(colors.HexColor("#204d3c"))
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(42, 785, "MUSTERBANK")
        pdf.setFont("Helvetica", 10)
        pdf.drawRightString(553, 788, f"Kontoauszug / Seite {page}")
        pdf.setFillColor(colors.HexColor("#4d5d53"))
        pdf.setFont("Helvetica", 9)
        pdf.drawString(42, 741, "VOLLSTAENDIG KUENSTLICHE TESTDATEN")
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 11)
        pdf.drawString(42, 702, "Erika Beispiel")
        pdf.drawString(42, 685, "Musterstrasse 1")
        pdf.drawString(42, 668, "1010 Musterstadt")
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(42, 608, "Buchungsuebersicht")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(42, 585, "Konto: MUSTERKONTO-0001")
        pdf.setFillColor(colors.HexColor("#edf2ee"))
        pdf.rect(42, 535, 511, 26, stroke=0, fill=1)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(52, 544, "Datum")
        pdf.drawString(130, 544, "Buchungstext")
        pdf.drawRightString(542, 544, "Betrag EUR")
        entries = [("01.01.2026", "MUSTERGEHALT", "2.000,00"),
                   ("02.01.2026", "MUSTERMIETE", "-700,00"),
                   ("03.01.2026", "MUSTEREINKAUF", "-50,00")]
        pdf.setFont("Helvetica", 10)
        for index, (date, title, amount) in enumerate(entries):
            y = 511 - index * 42
            pdf.drawString(52, y, date)
            pdf.drawString(130, y, title)
            pdf.drawRightString(542, y, amount)
            pdf.setStrokeColor(colors.HexColor("#d9e1db"))
            pdf.line(42, y-15, 553, y-15)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(42, 65, "Nur fuer UI-Tests. Kein echtes Bankdokument.")
        pdf.showPage()
    pdf.save()
    print("Synthetic demo PDF created.")


if __name__ == "__main__":
    main()
