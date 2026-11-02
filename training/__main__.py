# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Dati di addestramento per i modelli piccoli, verificati dal compilatore di Tessera.

  python -m training tasks   --teacher ollama:qwen3.8 --n 300     esercizi nuovi con test calcolati
  python -m training solve   --teacher ollama:qwen3.8             soluzioni Tessera verificate
  python -m training dataset                                      file train.jsonl e val.jsonl
  python -m training check                                        riverifica soluzioni ed esercizi

L'addestramento vero e proprio e l'esportazione in Ollama si fanno con l'ambiente .venv-train:
vedi training/README.md.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from experiment.__main__ import carica_compiti, tieni_sveglio
from experiment.models import ModelloClaude, ModelloCompatibileOpenAI, ModelloOllama

from . import dataset, solve, tasks

QUI = Path(__file__).resolve().parent
DATI = QUI / "data"
INSEGNANTE_PREDEFINITO = "ollama:qwen3.8"


def insegnante(args):
    """Il modello che scrive esercizi e soluzioni: locale per scelta; i servizi a pagamento chiedono --yes."""
    prefisso, _, nome = args.teacher.partition(":")
    if prefisso == "ollama":
        return ModelloOllama(nome, indirizzo=args.base_url or "http://localhost:11434")
    if prefisso == "lmstudio":
        return ModelloCompatibileOpenAI(nome, indirizzo=args.base_url or "http://localhost:1234/v1")
    if prefisso == "compat":
        if not args.base_url:
            sys.exit("con compat: serve --base-url")
        chiave = os.environ.get(args.api_key_env) if args.api_key_env else None
        if args.api_key_env and not chiave:
            sys.exit(f"la variabile d'ambiente {args.api_key_env} non e' impostata")
        if urlparse(args.base_url).hostname not in ("localhost", "127.0.0.1", "::1") and not args.yes:
            sys.exit("E' un servizio remoto e le chiamate possono avere un costo. Rilancia con --yes per avviare.")
        return ModelloCompatibileOpenAI(nome, indirizzo=args.base_url, prefisso="compat", chiave=chiave)
    if args.teacher.startswith("claude-"):
        if not args.yes:
            sys.exit("Le chiamate a Claude hanno un costo. Rilancia con --yes per avviare.")
        return ModelloClaude(args.teacher, args.effort)
    sys.exit(f"insegnante '{args.teacher}' non riconosciuto: usa ollama:NOME, lmstudio:NOME, compat:NOME o claude-...")


def comando_tasks(args):
    modello = insegnante(args)
    uscita = Path(args.out)
    esistenti = dataset.leggi_jsonl(uscita)
    mancanti = args.n - len(esistenti)
    if mancanti <= 0:
        print(f"{uscita} contiene gia' {len(esistenti)} esercizi.")
        return 0
    print(f"Insegnante {modello.modello}: {mancanti} esercizi da generare (gia' presenti {len(esistenti)}).")
    tieni_sveglio()
    tasks.genera(modello, mancanti, carica_compiti(), esistenti, lambda t: dataset.aggiungi_jsonl(uscita, t),
                 seme=args.seed if args.seed is not None else len(esistenti))
    return 0


def comando_solve(args):
    modello = insegnante(args)
    esercizi = dataset.leggi_jsonl(args.tasks)
    uscita = Path(args.out)
    fatti = {(r["task"], r["sample"]) for r in dataset.leggi_jsonl(uscita)}
    da_fare = [(t, s) for s in range(1, args.samples + 1) for t in esercizi if (t["id"], s) not in fatti]
    print(f"Insegnante {modello.modello}: {len(da_fare)} soluzioni da scrivere (gia' fatte {len(fatti)}).")
    tieni_sveglio()
    risolti = 0
    for i, (task, campione) in enumerate(da_fare, 1):
        record = solve.risolvi(modello, task, args.max_attempts)
        record["sample"] = campione
        dataset.aggiungi_jsonl(uscita, record)
        risolti += record["solved"]
        stato = f"risolto al tentativo {len(record['attempts'])}" if record["solved"] else "non risolto"
        print(f"[{i}/{len(da_fare)}] {task['id']:<28} campione {campione}  {stato}", flush=True)
    print(f"\nRisolti {risolti} su {len(da_fare)}.")
    return 0


def comando_dataset(args):
    esercizi = dataset.leggi_jsonl(args.tasks)
    soluzioni = dataset.leggi_jsonl(args.solutions)
    addestramento, validazione, statistiche = dataset.costruisci(esercizi, soluzioni, carica_compiti(),
                                                                 args.val, args.seed)
    cartella = Path(args.out_dir)
    cartella.mkdir(parents=True, exist_ok=True)
    for nome, esempi in (("train.jsonl", addestramento), ("val.jsonl", validazione)):
        (cartella / nome).write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in esempi),
                                     encoding="utf-8")
    (cartella / "stats.json").write_text(json.dumps(statistiche, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(statistiche, ensure_ascii=False, indent=2))
    return 0


def comando_check(args):
    esercizi = dataset.leggi_jsonl(args.tasks)
    valutazione = carica_compiti()
    problemi = 0
    for i, t in enumerate(esercizi):
        try:
            tasks.controlla_novita(t, valutazione, esercizi[:i])
        except tasks.Scartato as e:
            problemi += 1
            print(f"esercizio {t['id']}: {e}")
    sbagliate = dataset.verifica(esercizi, dataset.leggi_jsonl(args.solutions))
    for nome in sbagliate:
        print(f"soluzione di {nome}: non supera piu' i test")
    problemi += len(sbagliate)
    print(f"{len(esercizi)} esercizi controllati: " + ("tutto in ordine." if not problemi else f"{problemi} problemi."))
    return 1 if problemi else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="training", description="Dati di addestramento verificati per Tessera")
    sotto = parser.add_subparsers(dest="comando", required=True)

    def opzioni_insegnante(p):
        p.add_argument("--teacher", default=INSEGNANTE_PREDEFINITO,
                       help=f"ollama:NOME (predefinito {INSEGNANTE_PREDEFINITO}), lmstudio:NOME, compat:NOME, claude-...")
        p.add_argument("--base-url")
        p.add_argument("--api-key-env")
        p.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
        p.add_argument("--yes", action="store_true", help="conferma le chiamate a pagamento")

    p = sotto.add_parser("tasks", help="genera esercizi nuovi con test calcolati da una soluzione di riferimento")
    opzioni_insegnante(p)
    p.add_argument("--n", type=int, default=300, help="numero totale di esercizi da avere nel file")
    p.add_argument("--out", default=str(DATI / "tasks.jsonl"))
    p.add_argument("--seed", type=int)
    p.set_defaults(azione=comando_tasks)

    p = sotto.add_parser("solve", help="soluzioni Tessera verificate dal compilatore e dai test")
    opzioni_insegnante(p)
    p.add_argument("--tasks", default=str(DATI / "tasks.jsonl"))
    p.add_argument("--out", default=str(DATI / "solutions.jsonl"))
    p.add_argument("--samples", type=int, default=1, help="soluzioni indipendenti per esercizio")
    p.add_argument("--max-attempts", type=int, default=4)
    p.set_defaults(azione=comando_solve)

    p = sotto.add_parser("dataset", help="scrive train.jsonl e val.jsonl")
    p.add_argument("--tasks", default=str(DATI / "tasks.jsonl"))
    p.add_argument("--solutions", default=str(DATI / "solutions.jsonl"))
    p.add_argument("--out-dir", default=str(DATI))
    p.add_argument("--val", type=float, default=0.05, help="quota di esercizi per la validazione")
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(azione=comando_dataset)

    p = sotto.add_parser("check", help="riverifica esercizi (contaminazione, doppioni) e soluzioni")
    p.add_argument("--tasks", default=str(DATI / "tasks.jsonl"))
    p.add_argument("--solutions", default=str(DATI / "solutions.jsonl"))
    p.set_defaults(azione=comando_check)

    args = parser.parse_args(argv)
    return args.azione(args)


if __name__ == "__main__":
    sys.exit(main())
