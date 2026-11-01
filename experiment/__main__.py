# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Esperimento della fase 1: un modello scrive gli stessi esercizi in Tessera e in Python.

  python -m experiment check                         verifica esercizi e soluzioni di riferimento
  python -m experiment run --model reference         prova a costo zero con le soluzioni di riferimento
  python -m experiment run --yes                     esperimento vero con Claude (serve una chiave API)
  python -m experiment report experiment/results/FILE.jsonl
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

from . import references, sandbox
from .models import MODELLO_PREDEFINITO, PREZZI, ModelloClaude, ModelloRiferimento
from .report import rapporto
from .runner import esegui_esperimento

QUI = Path(__file__).resolve().parent
LINGUE = ["tessera", "python"]


def carica_compiti(scelti=None):
    tasks = json.loads((QUI / "tasks.json").read_text(encoding="utf-8"))
    for task in tasks:
        task.setdefault("function", task["id"])     # il nome della funzione e' l'identificativo dell'esercizio
    if scelti and scelti != "all":
        nomi = scelti.split(",")
        sconosciuti = [n for n in nomi if n not in {t["id"] for t in tasks}]
        if sconosciuti:
            sys.exit(f"esercizi sconosciuti: {', '.join(sconosciuti)}")
        tasks = [t for t in tasks if t["id"] in nomi]
    return tasks


def comando_check(args):
    """Ogni soluzione di riferimento deve superare tutti i test, visibili e nascosti, nei due linguaggi."""
    tasks = carica_compiti(args.tasks)
    falliti = 0
    for task in tasks:
        stati = []
        for lingua in LINGUE:
            codice = (references.TESSERA if lingua == "tessera" else references.PYTHON)[task["id"]]
            esito = sandbox.esegui(lingua, codice, task, task["visible"] + task["hidden"])
            if esito.get("compile_error"):
                falliti += 1
                stati.append(f"{lingua}: NON COMPILA {esito['compile_error'][:200]}")
                continue
            sbagliati = [(t, r) for t, r in zip(task["visible"] + task["hidden"], esito["results"])
                         if r["outcome"] != "pass"]
            if sbagliati:
                falliti += 1
                t, r = sbagliati[0]
                stati.append(f"{lingua}: {len(sbagliati)} test falliti, es. {t['args']} -> {r}")
            else:
                stati.append(f"{lingua}: ok")
        print(f"{task['id']:<22} " + " | ".join(stati))
    n_test = sum(len(t["visible"]) + len(t["hidden"]) for t in tasks)
    print(f"\n{len(tasks)} esercizi, {n_test} test per linguaggio: "
          + ("tutto in ordine." if not falliti else f"{falliti} problemi."))
    return 1 if falliti else 0


def comando_run(args):
    tasks = carica_compiti(args.tasks)
    lingue = args.langs.split(",")
    chiamate = len(tasks) * len(lingue) * args.reps
    if args.model in ("reference", "reference-broken"):
        modello = ModelloRiferimento(sbaglia_prima=args.model == "reference-broken")
    else:
        if args.model not in PREZZI:
            print(f"attenzione: prezzo di {args.model} sconosciuto, il costo non sara' stimato")
        print(f"Modello {args.model}, sforzo {args.effort}: {len(tasks)} esercizi x {len(lingue)} linguaggi x "
              f"{args.reps} ripetizioni = da {chiamate} a {chiamate * args.max_attempts} chiamate all'API.")
        if not args.yes:
            print("Le chiamate hanno un costo. Rilancia con --yes per avviare l'esperimento.")
            return 0
        modello = ModelloClaude(args.model, args.effort, fallback=not args.no_fallback)
    uscita = Path(args.out) if args.out else (
        QUI / "results" / f"{datetime.datetime.now():%Y%m%d-%H%M%S}-{modello.modello}.jsonl")
    esegui_esperimento(modello, tasks, lingue, args.reps, args.max_attempts, uscita)
    testo = rapporto(uscita)
    uscita.with_suffix(".md").write_text(testo, encoding="utf-8")
    print("\n" + testo)
    print(f"\nRisultati: {uscita}\nRapporto:  {uscita.with_suffix('.md')}")
    return 0


def comando_report(args):
    testo = rapporto(args.file)
    print(testo)
    Path(args.file).with_suffix(".md").write_text(testo, encoding="utf-8")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="experiment", description="Esperimento della fase 1: Tessera contro Python")
    sotto = parser.add_subparsers(dest="comando", required=True)

    p = sotto.add_parser("check", help="verifica esercizi e soluzioni di riferimento")
    p.add_argument("--tasks", default="all")
    p.set_defaults(azione=comando_check)

    p = sotto.add_parser("run", help="esegue l'esperimento")
    p.add_argument("--model", default=MODELLO_PREDEFINITO,
                   help=f"modello Claude (predefinito {MODELLO_PREDEFINITO}), oppure reference / reference-broken")
    p.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--langs", default="tessera,python")
    p.add_argument("--tasks", default="all", help="elenco separato da virgole, oppure all")
    p.add_argument("--reps", type=int, default=3, help="ripetizioni di ogni esercizio")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--out", help="file JSONL dei risultati (se esiste, l'esperimento riprende)")
    p.add_argument("--no-fallback", action="store_true", help="disattiva il fallback lato server sui rifiuti")
    p.add_argument("--yes", action="store_true", help="conferma le chiamate a pagamento")
    p.set_defaults(azione=comando_run)

    p = sotto.add_parser("report", help="rapporto da un file di risultati")
    p.add_argument("file")
    p.set_defaults(azione=comando_report)

    args = parser.parse_args(argv)
    return args.azione(args)


if __name__ == "__main__":
    sys.exit(main())
