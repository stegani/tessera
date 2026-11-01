# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Controlla la grammatica di Tessera.

1. La grammatica deve essere LALR(1) senza conflitti (modalita' rigorosa di Lark).
2. Tutti i file examples/*.tsr devono essere accettati.
3. Ogni caso di CASI_RIFIUTATI deve essere rifiutato: dal parser o dai controlli dopo il parsing.

Uso:  pip install "lark[interegular]"   poi   python tools/check_grammar.py
"""
import json
import sys
from pathlib import Path

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput

RADICE = Path(__file__).resolve().parent.parent
GRAMMATICA = RADICE / "spec" / "tessera.lark"
ESEMPI = RADICE / "examples"


def crea_parser():
    return Lark(GRAMMATICA.read_text(encoding="utf-8"), parser="lalr", lexer="contextual", strict=True)


def errore_json(err: UnexpectedInput, testo: str) -> dict:
    """Errore in forma strutturata, pensata per essere letta da un modello."""
    trovato = getattr(err, "token", None)
    attesi = sorted(getattr(err, "expected", None) or getattr(err, "allowed", None) or [])
    return {
        "riga": err.line,
        "colonna": err.column,
        "trovato": str(trovato) if trovato is not None else testo[err.pos_in_stream : err.pos_in_stream + 1],
        "attesi": attesi[:12],
    }


def nomi_di_chiusura(albero: Tree) -> list[str]:
    """fn, type e process devono chiudersi con il proprio nome."""
    problemi = []
    for nodo in albero.iter_subtrees():
        if nodo.data not in ("fn_decl", "type_decl", "process_decl"):
            continue
        nomi = [t for t in nodo.children if isinstance(t, Token) and t.type in ("NAME", "TYPE_NAME")]
        if len(nomi) >= 2 and nomi[0] != nomi[-1]:
            problemi.append(f"riga {nomi[-1].line}: '{nomi[0]}' chiuso come '{nomi[-1]}'")
    return problemi


def analizza(parser, testo: str):
    """Restituisce (albero, None) oppure (None, errore)."""
    if not testo.endswith("\n"):
        testo += "\n"
    try:
        albero = parser.parse(testo)
    except UnexpectedInput as err:
        return None, errore_json(err, testo)
    problemi = nomi_di_chiusura(albero)
    if problemi:
        return None, {"controllo": "nome di chiusura", "dettagli": problemi}
    return albero, None


def in_funzione(corpo: str, firma: str = "  effects: none\n") -> str:
    righe = "".join(f"  {r}\n" for r in corpo.strip().splitlines())
    return f"module prova\n\nfn f(x: i32, n: i32) -> i32\n{firma}do\n{righe}end fn f\n"


# (descrizione, sorgente): ognuno deve essere rifiutato.
CASI_RIFIUTATI = [
    ("and e or mescolati senza parentesi", in_funzione("let ok = x > 0 and n > 0 or n == 1\nreturn x")),
    ("confronto a catena", in_funzione("let ok = 0 <= x < n\nreturn x")),
    ("graffe al posto di do/end", in_funzione("if x > 0 { return x }\nreturn n")),
    ("incremento ++", in_funzione("x++\nreturn x")),
    ("riferimento con &", in_funzione("let y = &x\nreturn y")),
    ("tipo generico con < >", in_funzione("let v: List<i32> = [1]\nreturn x")),
    ("clausola effects mancante", in_funzione("return x", firma="  requires: x > 0\n")),
    ("clausole fuori ordine", in_funzione("return x", firma="  requires: x > 0\n  effects: none\n")),
    ("blocco if senza end if", in_funzione("if x > 0 do\n  return x\nend\nreturn n")),
    ("import con asterisco", "module prova\nfrom std.net import *\n"),
    ("nome di tipo in minuscolo", "module prova\ntype point do\n  x: f64\nend type point\n"),
    ("nome di funzione in PascalCase", "module prova\nfn Parse() -> i32\n  effects: none\ndo\n  return 1\nend fn Parse\n"),
    ("fn chiusa con un altro nome", "module prova\nfn a() -> i32\n  effects: none\ndo\n  return 1\nend fn b\n"),
    ("punto e virgola", in_funzione("let y = x;\nreturn y")),
]


def main() -> int:
    parser = crea_parser()
    print(f"Grammatica LALR(1) senza conflitti: {GRAMMATICA.relative_to(RADICE)}")
    falliti = 0

    print("\nEsempi (devono essere accettati):")
    for file in sorted(ESEMPI.glob("*.tsr")):
        albero, errore = analizza(parser, file.read_text(encoding="utf-8"))
        if errore:
            falliti += 1
            print(f"  NO  {file.name}: {json.dumps(errore, ensure_ascii=False)}")
        else:
            funzioni = sum(1 for _ in albero.find_data("fn_decl"))
            print(f"  ok  {file.name} ({funzioni} funzioni)")

    print("\nErrori tipici (devono essere rifiutati):")
    for descrizione, sorgente in CASI_RIFIUTATI:
        _, errore = analizza(parser, sorgente)
        if errore is None:
            falliti += 1
            print(f"  NO  accettato per sbaglio: {descrizione}")
        else:
            print(f"  ok  {descrizione}: {json.dumps(errore, ensure_ascii=False)}")

    print("\nTutto in ordine." if falliti == 0 else f"\n{falliti} controlli falliti.")
    return 1 if falliti else 0


if __name__ == "__main__":
    sys.exit(main())
