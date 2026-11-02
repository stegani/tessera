# Copyright 2026 Stefano Stegani - Airgrid Network - www.airgrid.it
# SPDX-License-Identifier: Apache-2.0
"""Genera il logo di Tessera in SVG (e in PNG, se e' installato vl-convert-python).

L'icona e' una griglia di tessere di mosaico: cinque formano una T, la tessera in fondo,
di colore diverso, e' la "tessera" di riconoscimento, il permesso unico.

Uso:  pip install vl-convert-python   poi   python tools/make_logo.py
"""
from pathlib import Path

USCITA = Path(__file__).resolve().parent.parent / "docs" / "brand"

FONDO = "#0E1726"
VUOTA = "#1A2740"
BORDO = "#2B3B57"
TEAL = ["#2EC4B6", "#3DD6C6", "#26AFA2", "#34CDBE"]
AMBRA = "#F4B942"
TESTO_SCURO = "#0E1726"
TESTO_CHIARO = "#FFFFFF"
GRIGIO = "#6B7A90"
CARATTERE = "'Segoe UI', Inter, 'Helvetica Neue', Arial, sans-serif"

# Posizioni (colonna, riga) delle tessere che formano la T, nell'ordine dei colori.
T = [(0, 0), (1, 0), (2, 0), (1, 1)]
CHIAVE = (1, 2)


def tessere(x0, y0, lato, spazio, raggio):
    """Griglia 3x3: la T in verde acqua, la tessera chiave in ambra, le altre vuote."""
    parti = []
    for riga in range(3):
        for colonna in range(3):
            x, y = x0 + colonna * (lato + spazio), y0 + riga * (lato + spazio)
            if (colonna, riga) in T:
                colore = TEAL[T.index((colonna, riga))]
                parti.append(f'<rect x="{x}" y="{y}" width="{lato}" height="{lato}" rx="{raggio}" fill="{colore}"/>')
            elif (colonna, riga) == CHIAVE:
                parti.append(f'<rect x="{x}" y="{y}" width="{lato}" height="{lato}" rx="{raggio}" fill="{AMBRA}"/>')
            else:
                parti.append(f'<rect x="{x + 2}" y="{y + 2}" width="{lato - 4}" height="{lato - 4}" rx="{raggio}" '
                             f'fill="{VUOTA}" stroke="{BORDO}" stroke-width="4"/>')
    return "\n  ".join(parti)


def icona(dimensione=512):
    lato, spazio = 112, 16
    inizio = (512 - (3 * lato + 2 * spazio)) // 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{dimensione}" height="{dimensione}" viewBox="0 0 512 512" '
            f'role="img" aria-label="Tessera">\n  <title>Tessera</title>\n'
            f'  <rect width="512" height="512" rx="104" fill="{FONDO}"/>\n  {tessere(inizio, inizio, lato, spazio, 16)}\n</svg>\n')


def logo(chiaro):
    """Icona + nome + motto, 1200x360, sfondo trasparente. chiaro=True: testo scuro per sfondi chiari."""
    testo = TESTO_SCURO if chiaro else TESTO_CHIARO
    sfondo = ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="360" viewBox="0 0 1200 360" role="img" '
            f'aria-label="Tessera: written by AI, hardened against AI">\n  <title>Tessera</title>\n  {sfondo}'
            f'<g transform="translate(40 40) scale(0.546875)">\n    <rect width="512" height="512" rx="104" fill="{FONDO}"/>\n'
            f'    {tessere(72, 72, 112, 16, 16)}\n  </g>\n'
            f'  <text x="352" y="196" font-family="{CARATTERE}" font-size="150" font-weight="700" fill="{testo}" '
            f'letter-spacing="-3">Tessera</text>\n'
            f'  <text x="358" y="262" font-family="{CARATTERE}" font-size="38" fill="{GRIGIO}">'
            f'written by AI, hardened against AI</text>\n</svg>\n')


def scheda_social():
    """Immagine 1280x640 per GitHub (social preview) e per i post."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640" role="img" '
            f'aria-label="Tessera: written by AI, hardened against AI">\n  <title>Tessera</title>\n'
            f'  <rect width="1280" height="640" fill="{FONDO}"/>\n'
            f'  <g transform="translate(96 160) scale(0.625)">\n    <rect width="512" height="512" rx="104" fill="#13203A"/>\n'
            f'    {tessere(72, 72, 112, 16, 16)}\n  </g>\n'
            f'  <text x="470" y="300" font-family="{CARATTERE}" font-size="132" font-weight="700" fill="{TESTO_CHIARO}" '
            f'letter-spacing="-3">Tessera</text>\n'
            f'  <text x="476" y="370" font-family="{CARATTERE}" font-size="40" fill="#C9D3E0">'
            f'A programming language written by AI,</text>\n'
            f'  <text x="476" y="422" font-family="{CARATTERE}" font-size="40" fill="#C9D3E0">hardened against AI.</text>\n'
            f'  <text x="476" y="500" font-family="{CARATTERE}" font-size="30" fill="{AMBRA}">'
            f'github.com/stegani/tessera</text>\n'
            f'  <text x="476" y="542" font-family="{CARATTERE}" font-size="30" fill="{AMBRA}">'
            f'doi.org/10.5281/zenodo.23855820</text>\n</svg>\n')


def main():
    USCITA.mkdir(parents=True, exist_ok=True)
    file = {
        "tessera-icon.svg": icona(),
        "tessera-logo.svg": logo(chiaro=True),
        "tessera-logo-dark.svg": logo(chiaro=False),
        "tessera-social.svg": scheda_social(),
    }
    for nome, svg in file.items():
        (USCITA / nome).write_text(svg, encoding="utf-8", newline="\n")
    try:
        import vl_convert as vlc
    except ImportError:
        print("vl-convert-python non installato: scritti solo gli SVG")
        return
    for nome, scala in (("tessera-icon.svg", 1), ("tessera-icon.svg", 2), ("tessera-logo.svg", 1),
                        ("tessera-logo-dark.svg", 1), ("tessera-social.svg", 1)):
        png = vlc.svg_to_png((USCITA / nome).read_text(encoding="utf-8"), scale=scala)
        destinazione = USCITA / (Path(nome).stem + ("@2x" if scala == 2 else "") + ".png")
        destinazione.write_bytes(png)
    print("scritti:", ", ".join(sorted(p.name for p in USCITA.iterdir())))


if __name__ == "__main__":
    main()
