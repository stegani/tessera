# Copyright 2026 Stefano Stegani - Airgrid Network - www.airgrid.it
# SPDX-License-Identifier: Apache-2.0
"""Il manuale in PDF: docs/manual.md -> docs/manual.pdf, docs/manual.it.md -> docs/manual.it.pdf.

  pip install markdown pypdf reportlab
  python tools/make_manual_pdf.py

Il Markdown diventa HTML, che Chrome o Edge (senza finestra) stampano in PDF. Poi su ogni pagina si
aggiunge il piede con l'autore e il numero di pagina, e il file viene protetto contro le modifiche:
si apre, si stampa e si copia liberamente, ma non si modifica. La protezione e' quella dello standard
PDF: impedisce le modifiche ai programmi che la rispettano; la copia di riferimento resta quella
archiviata con il DOI.
"""
import html
import io
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
AUTORE = "Stefano Stegani - Airgrid Network - www.airgrid.it"
REPO = "https://github.com/stegani/tessera/blob/main/"
BROWSER = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chromium-browser", "msedge",
]

MANUALI = {
    "manual.md": {"titolo": "Tessera user manual", "sottotitolo": "Writing Tessera by hand",
                  "pagina": "page", "lingua": "en"},
    "manual.it.md": {"titolo": "Manuale di Tessera", "sottotitolo": "Scrivere Tessera a mano",
                     "pagina": "pagina", "lingua": "it"},
}

CSS = """
@page { size: A4; margin: 18mm 17mm 22mm 17mm; }
body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt; line-height: 1.5;
       color: #1d2129; }
.copertina { height: 245mm; display: flex; flex-direction: column; justify-content: center;
             text-align: center; page-break-after: always; }
.copertina img { width: 120mm; margin: 0 auto 14mm auto; }
.copertina h1 { font-size: 26pt; margin: 0 0 4mm 0; border: none; }
.copertina .sotto { font-size: 14pt; color: #555; margin-bottom: 16mm; }
.copertina .autore { font-size: 12pt; font-weight: 600; }
.copertina .dati { font-size: 10pt; color: #555; margin-top: 4mm; }
h1 { font-size: 20pt; border-bottom: 2px solid #c8a24a; padding-bottom: 2mm; }
h2 { font-size: 15pt; margin-top: 9mm; border-bottom: 1px solid #ddd; padding-bottom: 1mm;
     page-break-after: avoid; }
h3 { font-size: 12pt; page-break-after: avoid; }
code { font-family: Consolas, "Cascadia Mono", "Courier New", monospace; font-size: 9.2pt;
       background: #f3f1ea; padding: 0 1.2mm; border-radius: 2px; }
pre { background: #f6f4ee; border: 1px solid #e3ddcc; border-left: 3px solid #c8a24a; padding: 3mm 4mm;
      border-radius: 2px; page-break-inside: avoid; white-space: pre-wrap; }
pre code { background: none; padding: 0; font-size: 8.8pt; line-height: 1.22; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; page-break-inside: avoid; font-size: 9.6pt; }
th, td { border: 1px solid #d9d4c7; padding: 1.4mm 2.4mm; text-align: left; vertical-align: top; }
th { background: #efe9da; }
a { color: #6b4f12; text-decoration: none; }
hr { border: none; border-top: 1px solid #ccc; margin: 8mm 0 4mm 0; }
"""


def trova_browser():
    for candidato in BROWSER:
        percorso = candidato if Path(candidato).exists() else shutil.which(candidato)
        if percorso:
            return percorso
    sys.exit("serve Chrome, Chromium o Edge per stampare il PDF")


def in_html(testo, dati):
    import markdown
    from markdown.extensions.toc import slugify_unicode

    # Il titolo, la riga delle lingue e quella dell'autore stanno gia' nella copertina.
    righe = testo.splitlines()
    corpo = "\n".join(r for r in righe[:6] if not r.startswith(("# ", "*English", "*[English]", "**Tessera 0.2**"))) \
        + "\n" + "\n".join(righe[6:])
    pagina = markdown.markdown(corpo, extensions=["tables", "fenced_code", "toc"],
                               extension_configs={"toc": {"slugify": slugify_unicode}})
    # I link relativi del repository diventano indirizzi su GitHub; le ancore interne restano.
    pagina = re.sub(r'href="(?!https?:|#|mailto:)(?:\.\./)?([^"]+)"',
                    lambda m: f'href="{REPO}{m.group(1) if m.group(0).count("../") else "docs/" + m.group(1)}"', pagina)
    logo = (RADICE / "docs" / "brand" / "tessera-logo.png").as_uri()
    copertina = f"""
<div class="copertina">
  <img src="{logo}" alt="Tessera">
  <h1>{html.escape(dati["titolo"])}</h1>
  <div class="sotto">{html.escape(dati["sottotitolo"])} · Tessera 0.2</div>
  <div class="autore">{html.escape(AUTORE)}</div>
  <div class="dati">Apache 2.0 · DOI 10.5281/zenodo.23855820 · github.com/stegani/tessera</div>
</div>"""
    return (f'<!doctype html><html lang="{dati["lingua"]}"><head><meta charset="utf-8">'
            f'<title>{html.escape(dati["titolo"])}</title><style>{CSS}</style></head>'
            f"<body>{copertina}{pagina}</body></html>")


def stampa(browser, file_html, file_pdf, cartella):
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--user-data-dir={cartella / 'profilo'}", "--allow-file-access-from-files",
                    f"--print-to-pdf={file_pdf}", file_html.as_uri()],
                   check=True, capture_output=True, timeout=120)
    if not file_pdf.exists():
        sys.exit("il browser non ha prodotto il PDF")


def piede(n, totale, larghezza, altezza, parola):
    from reportlab.pdfgen import canvas
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(larghezza, altezza))
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(48, 30, AUTORE)
    c.drawRightString(larghezza - 48, 30, f"Tessera 0.2  -  {parola} {n} / {totale}")
    c.save()
    buffer.seek(0)
    from pypdf import PdfReader
    return PdfReader(buffer).pages[0]


def rifinisci(grezzo, finale, dati):
    from pypdf import PdfReader, PdfWriter
    from pypdf.constants import UserAccessPermissions as P

    lettore = PdfReader(grezzo)
    scrittore = PdfWriter()
    totale = len(lettore.pages)
    for n, pagina in enumerate(lettore.pages, 1):
        if n > 1:       # la copertina resta pulita
            larghezza, altezza = float(pagina.mediabox.width), float(pagina.mediabox.height)
            pagina.merge_page(piede(n, totale, larghezza, altezza, dati["pagina"]))
        scrittore.add_page(pagina)
    scrittore.add_metadata({"/Title": dati["titolo"], "/Author": AUTORE, "/Subject": "Tessera 0.2",
                            "/Creator": "tools/make_manual_pdf.py"})
    # Si apre senza password; la password del proprietario e' casuale e non viene salvata:
    # nessuno puo' togliere la protezione, il PDF si rigenera dai sorgenti.
    permessi = P.PRINT | P.PRINT_TO_REPRESENTATION | P.EXTRACT | P.EXTRACT_TEXT_AND_GRAPHICS
    scrittore.encrypt(user_password="", owner_password=secrets.token_hex(24), permissions_flag=permessi,
                      algorithm="AES-256")
    with open(finale, "wb") as f:
        scrittore.write(f)
    return totale


def main():
    browser = trova_browser()
    with tempfile.TemporaryDirectory(prefix="tessera-pdf-") as tmp:
        cartella = Path(tmp)
        for nome, dati in MANUALI.items():
            sorgente = RADICE / "docs" / nome
            file_html = cartella / (nome + ".html")
            file_html.write_text(in_html(sorgente.read_text(encoding="utf-8"), dati), encoding="utf-8",
                                 newline="\n")
            grezzo = cartella / (nome + ".pdf")
            stampa(browser, file_html, grezzo, cartella)
            finale = sorgente.with_suffix(".pdf")
            pagine = rifinisci(grezzo, finale, dati)
            print(f"{finale.relative_to(RADICE)}: {pagine} pagine")
    return 0


if __name__ == "__main__":
    sys.exit(main())
