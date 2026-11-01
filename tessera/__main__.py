# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Riga di comando di Tessera.

  python -m tessera esegui   file.tsr              esegue il process o fn main()
  python -m tessera verifica file.tsr [--json]     controlli statici, senza eseguire
  python -m tessera prova    file.tsr              esegue le clausole example
  python -m tessera compila  file.tsr [-o cartella]  produce .wat e .wasm
  python -m tessera chiama   file.tsr funzione arg... [--wasm]
"""
import argparse
import json
import sys
from pathlib import Path

from .errori import ErroreTessera


def stampa_errori(errori, in_json):
    for e in errori:
        print(e.in_json() if in_json else str(e), file=sys.stderr)


def carica(file):
    from .controlli import controlla_programma
    from .interprete import Programma
    programma = Programma(file)
    return programma, controlla_programma(programma)


def comando_verifica(args):
    _, errori = carica(args.file)
    stampa_errori(errori, args.json)
    if not errori and not args.json:
        print(f"{args.file}: nessun errore")
    return 1 if errori else 0


def comando_esegui(args):
    from .interprete import Interprete
    programma, errori = carica(args.file)
    if errori:
        stampa_errori(errori, args.json)
        return 1
    Interprete(programma).esegui_programma()
    return 0


def comando_prova(args):
    from .interprete import Interprete
    programma, errori = carica(args.file)
    if errori:
        stampa_errori(errori, args.json)
        return 1
    esiti = Interprete(programma, eco=False).esegui_esempi()
    falliti = [e for e in esiti if not e[2]]
    for funzione, testo, superato, dettaglio in esiti:
        if args.json:
            print(json.dumps({"funzione": funzione, "esempio": testo, "superato": superato, "dettaglio": dettaglio},
                             ensure_ascii=False))
        else:
            print(f"  {'ok' if superato else 'NO'}  {funzione}: {testo}" + (f"  ->  {dettaglio}" if dettaglio else ""))
    if not args.json:
        print(f"{len(esiti) - len(falliti)} esempi superati su {len(esiti)}")
    return 1 if falliti else 0


def comando_compila(args):
    from .compilatore_wasm import binario, compila_modulo
    from .sintassi import analizza_file
    _, errori = carica(args.file)
    if errori:
        stampa_errori(errori, args.json)
        return 1
    risultato = compila_modulo(analizza_file(args.file))
    cartella = Path(args.o) if args.o else Path(args.file).parent
    cartella.mkdir(parents=True, exist_ok=True)
    base = cartella / Path(args.file).stem
    base.with_suffix(".wat").write_text(risultato.wat, encoding="utf-8")
    dimensione = None
    try:
        dati = binario(risultato.wat)
        base.with_suffix(".wasm").write_bytes(dati)
        dimensione = len(dati)
    except ImportError:
        print("wasmtime non installato: scritto solo il testo .wat", file=sys.stderr)
    print(f"compilate ({len(risultato.compilate)}): {', '.join(risultato.compilate) or '-'}")
    for nome, motivo in risultato.saltate.items():
        print(f"  saltata {nome}: {motivo}")
    print(f"scritto {base.with_suffix('.wat')}" + (f" e {base.with_suffix('.wasm')} ({dimensione} byte)" if dimensione else ""))
    return 0 if risultato.compilate else 1


def converti(testo, tipo):
    nome = getattr(tipo, "nome", None)
    if nome == "bool":
        if testo not in ("true", "false"):
            raise ErroreTessera("tipo", f"'{testo}' non e' bool: scrivi true o false")
        return testo == "true"
    if nome in ("f16", "bf16", "f32", "f64"):
        return float(testo)
    if nome in ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"):
        return int(testo)
    if nome == "Str":
        return testo
    raise ErroreTessera("tipo", f"dalla riga di comando non si puo' passare un {nome}")


def comando_chiama(args):
    from .interprete import Interprete
    from .valori import formatta
    programma, errori = carica(args.file)
    if errori:
        stampa_errori(errori, args.json)
        return 1
    funzione = programma.principale.funzioni.get(args.funzione)
    if funzione is None:
        raise ErroreTessera("nome", f"funzione {args.funzione} non trovata")
    parametri = funzione.decl.parametri
    if len(args.argomenti) != len(parametri):
        raise ErroreTessera("tipo", f"{args.funzione} vuole {len(parametri)} argomenti")
    valori = [converti(t, p.tipo) for t, p in zip(args.argomenti, parametri)]
    if args.wasm:
        from .compilatore_wasm import Esecutore, compila_modulo
        risultato = Esecutore(compila_modulo(programma.principale.ast)).chiama(args.funzione, valori)
    else:
        risultato = Interprete(programma).chiama_per_nome(args.funzione, valori)
    print(formatta(risultato, dentro=True))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tessera", description="Prototipo di Tessera: interprete e compilatore")
    sotto = parser.add_subparsers(dest="comando", required=True)

    def comando(nome, funzione, aiuto, alias):
        p = sotto.add_parser(nome, help=aiuto, aliases=[alias])
        p.add_argument("file")
        p.add_argument("--json", action="store_true", help="errori in JSON, uno per riga")
        p.set_defaults(azione=funzione)
        return p

    comando("esegui", comando_esegui, "esegue il process o fn main()", "run")
    comando("verifica", comando_verifica, "controlli statici senza eseguire", "check")
    comando("prova", comando_prova, "esegue le clausole example", "test")
    comando("compila", comando_compila, "compila in WebAssembly", "build").add_argument("-o", help="cartella di uscita")
    p = comando("chiama", comando_chiama, "chiama una funzione con argomenti", "call")
    p.add_argument("funzione")
    p.add_argument("argomenti", nargs="*")
    p.add_argument("--wasm", action="store_true", help="usa la versione compilata")

    args = parser.parse_args(argv)
    try:
        return args.azione(args)
    except ErroreTessera as e:
        e.file = e.file or args.file
        stampa_errori([e], args.json)
        return 1


if __name__ == "__main__":
    sys.exit(main())
