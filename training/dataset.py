# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Dalle soluzioni verificate ai file di addestramento (JSONL, un esempio di conversazione per riga).

La divisione tra addestramento e validazione e' per esercizio, non per esempio: le varianti dello
stesso esercizio stanno tutte dalla stessa parte, altrimenti la validazione misurerebbe la memoria.
"""
import json
import random
from collections import Counter
from pathlib import Path

from experiment import sandbox

from .solve import esempi
from .tasks import Scartato, controlla_novita


def leggi_jsonl(percorso):
    percorso = Path(percorso)
    if not percorso.exists():
        return []
    return [json.loads(r) for r in percorso.read_text(encoding="utf-8").splitlines() if r.strip()]


def aggiungi_jsonl(percorso, record):
    percorso = Path(percorso)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with percorso.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def normalizza(codice):
    return "\n".join(r.rstrip() for r in codice.strip().splitlines() if r.strip() and not r.strip().startswith("--"))


def costruisci(tasks, soluzioni, valutazione, quota_validazione=0.05, seme=0):
    """Restituisce (addestramento, validazione, statistiche)."""
    per_id = {t["id"]: t for t in tasks}
    scartati = Counter()
    esempi_per_task, visti = {}, set()
    for record in soluzioni:
        task = per_id.get(record["task"])
        if task is None:
            scartati["esercizio sconosciuto"] += 1
            continue
        try:
            controlla_novita(task, valutazione, [])
        except Scartato:
            scartati["esercizio dell'esperimento"] += 1
            continue
        if not record["solved"]:
            continue
        chiave = (task["id"], normalizza(record["attempts"][-1]["code"]))
        if chiave in visti:
            scartati["soluzione doppia"] += 1
            continue
        visti.add(chiave)
        esempi_per_task.setdefault(task["id"], []).extend(esempi(task, record))

    ids = sorted(esempi_per_task)
    random.Random(seme).shuffle(ids)
    n_val = max(1, round(len(ids) * quota_validazione)) if len(ids) >= 10 else 0
    validazione = [e for i in ids[:n_val] for e in esempi_per_task[i]]
    addestramento = [e for i in ids[n_val:] for e in esempi_per_task[i]]
    statistiche = {
        "esercizi": len(tasks), "esercizi_risolti": len(ids), "esercizi_validazione": n_val,
        "esempi_addestramento": len(addestramento), "esempi_validazione": len(validazione),
        "per_tipo": dict(Counter(e["type"] for e in addestramento + validazione)),
        "scartati": dict(scartati),
    }
    return addestramento, validazione, statistiche


def verifica(tasks, soluzioni):
    """Riesegue ogni soluzione dichiarata giusta: il file potrebbe venire da una versione precedente."""
    per_id = {t["id"]: t for t in tasks}
    problemi = []
    for record in soluzioni:
        task = per_id.get(record["task"])
        if not record["solved"] or task is None:
            continue
        tutti = task["visible"] + task["hidden"]
        esito = sandbox.esegui("tessera", record["attempts"][-1]["code"], task, tutti)
        if esito.get("compile_error") or any(r["outcome"] != "pass" for r in esito["results"]):
            problemi.append(record["task"])
    return problemi
