# Copyright 2026 Stefano Stegani - Airgrid Network - www.airgrid.it
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
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import references, sandbox
from .models import PREZZI, ModelloClaude, ModelloCompatibileOpenAI, ModelloOllama, ModelloRiferimento

# Tessera e' pensato per i modelli locali: il punto di partenza e' un modello servito da Ollama.
MODELLO_PREDEFINITO = "ollama:qwen3.8"
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


def tieni_sveglio():
    """Su Windows impedisce la sospensione per inattivita' finche' questo processo e' in esecuzione.
    Non cambia le impostazioni del sistema: l'effetto finisce con il processo."""
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


def comando_run(args):
    tasks = carica_compiti(args.tasks)
    lingue = args.langs.split(",")
    chiamate = len(tasks) * len(lingue) * args.reps
    prefisso, _, nome = args.model.partition(":")
    if args.model in ("reference", "reference-broken"):
        modello = ModelloRiferimento(sbaglia_prima=args.model == "reference-broken")
    elif prefisso == "ollama":
        modello = ModelloOllama(nome, indirizzo=args.base_url or "http://localhost:11434")
        print(f"Modello locale {nome} via Ollama: nessun costo, {chiamate}-{chiamate * args.max_attempts} chiamate.")
    elif prefisso == "lmstudio":
        modello = ModelloCompatibileOpenAI(nome, indirizzo=args.base_url or "http://localhost:1234/v1")
        print(f"Modello locale {nome} via LM Studio: nessun costo, {chiamate}-{chiamate * args.max_attempts} chiamate.")
    elif prefisso == "compat":
        # Qualsiasi servizio compatibile con OpenAI, locale o commerciale.
        if not args.base_url:
            sys.exit("con compat: serve --base-url, per esempio https://api.openai.com/v1")
        chiave = os.environ.get(args.api_key_env) if args.api_key_env else None
        if args.api_key_env and not chiave:
            sys.exit(f"la variabile d'ambiente {args.api_key_env} non e' impostata")
        remoto = urlparse(args.base_url).hostname not in ("localhost", "127.0.0.1", "::1")
        print(f"Modello {nome} su {args.base_url}: {chiamate}-{chiamate * args.max_attempts} chiamate.")
        if remoto and not args.yes:
            print("E' un servizio remoto e le chiamate possono avere un costo. Rilancia con --yes per avviare.")
            return 0
        modello = ModelloCompatibileOpenAI(nome, indirizzo=args.base_url, prefisso="compat", chiave=chiave)
    elif not args.model.startswith("claude-"):
        sys.exit(f"modello '{args.model}' non riconosciuto: usa ollama:NOME, lmstudio:NOME, compat:NOME con --base-url, "
                 f"o un modello Claude (claude-...)")
    else:
        if args.model not in PREZZI:
            print(f"attenzione: prezzo di {args.model} sconosciuto, il costo non sara' stimato")
        print(f"Modello {args.model}, sforzo {args.effort}: {len(tasks)} esercizi x {len(lingue)} linguaggi x "
              f"{args.reps} ripetizioni = da {chiamate} a {chiamate * args.max_attempts} chiamate all'API.")
        if not args.yes:
            print("Le chiamate hanno un costo. Rilancia con --yes per avviare l'esperimento.")
            return 0
        modello = ModelloClaude(args.model, args.effort, fallback=not args.no_fallback)
    tieni_sveglio()
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
                   help=f"ollama:NOME (predefinito {MODELLO_PREDEFINITO}), lmstudio:NOME, compat:NOME con --base-url, "
                        f"un modello Claude (claude-opus-5-5, ...), oppure reference / reference-broken")
    p.add_argument("--base-url", help="indirizzo del server (per compat:, o per cambiare quello di Ollama o LM Studio)")
    p.add_argument("--api-key-env", help="nome della variabile d'ambiente con la chiave del servizio (per compat:)")
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
