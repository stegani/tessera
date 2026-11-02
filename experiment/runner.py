# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Il ciclo dell'esperimento: richiesta, esecuzione sui test visibili, correzione, test nascosti."""
import hashlib
import json
import time
from pathlib import Path

from . import prompts, sandbox


def esegui_compito(modello, task, lingua, max_tentativi, ripetizione):
    sistema = prompts.sistema(lingua)
    messaggi = [{"role": "user", "content": prompts.richiesta(task, lingua)}]
    tentativi, codice_finale, risolto_al = [], None, None

    for n in range(1, max_tentativi + 1):
        inizio = time.monotonic()
        risposta = modello.rispondi(sistema, messaggi, task=task, lingua=lingua, tentativo=n)
        registro = {"n": n, "input_tokens": risposta.input_tokens, "output_tokens": risposta.output_tokens,
                    "cache_read": risposta.cache_read, "cache_write": risposta.cache_write,
                    "served_by": risposta.modello, "fallback": risposta.fallback, "notes": risposta.note,
                    "seconds": round(time.monotonic() - inizio, 2)}
        if risposta.rifiutata:
            registro["refusal"] = True
            tentativi.append(registro)
            break
        codice = prompts.estrai_codice(risposta.testo, lingua)
        esito = sandbox.esegui(lingua, codice, task, task["visible"])
        superati = sum(r["outcome"] == "pass" for r in esito["results"])
        registro.update({"compile_error": esito.get("compile_error"), "visible_passed": superati,
                         "visible_total": len(task["visible"]), "code": codice})
        tentativi.append(registro)
        codice_finale = codice
        if not esito.get("compile_error") and superati == len(task["visible"]):
            risolto_al = n
            break
        messaggi.append({"role": "assistant", "content": risposta.contenuto})
        messaggi.append({"role": "user", "content": prompts.correzione(task, lingua, esito)})

    nascosti = {"ran": False, "passed": 0, "wrong": 0, "error": 0, "total": len(task["hidden"])}
    if codice_finale is not None:
        esito = sandbox.esegui(lingua, codice_finale, task, task["hidden"])
        if not esito.get("compile_error"):
            nascosti["ran"] = True
            for r in esito["results"]:
                chiave = {"pass": "passed", "wrong": "wrong", "error": "error"}[r["outcome"]]
                nascosti[chiave] += 1
            nascosti["details"] = esito["results"]

    return {
        "task": task["id"], "lang": lingua, "rep": ripetizione, "security": task.get("security", False),
        "model": modello.modello, "prompt_version": hashlib.sha1(sistema.encode("utf-8")).hexdigest()[:8],
        "solved_at": risolto_al, "attempts": tentativi, "hidden": nascosti,
        "final_code": codice_finale,
    }


def gia_fatti(percorso):
    fatti = set()
    if percorso.exists():
        for riga in percorso.read_text(encoding="utf-8").splitlines():
            if riga.strip():
                r = json.loads(riga)
                fatti.add((r["task"], r["lang"], r["rep"]))
    return fatti


def esegui_esperimento(modello, tasks, lingue, ripetizioni, max_tentativi, percorso):
    """Scrive un record JSON per riga; se il file esiste riprende da dove si era fermato."""
    percorso = Path(percorso)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    fatti = gia_fatti(percorso)
    totale = len(tasks) * len(lingue) * ripetizioni
    contatore = 0
    for ripetizione in range(1, ripetizioni + 1):
        for task in tasks:
            for lingua in lingue:      # i due linguaggi alternati, cosi' eventuali variazioni nel tempo pesano uguale
                contatore += 1
                if (task["id"], lingua, ripetizione) in fatti:
                    continue
                record = esegui_compito(modello, task, lingua, max_tentativi, ripetizione)
                with percorso.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                stato = f"risolto al tentativo {record['solved_at']}" if record["solved_at"] else "non risolto"
                h = record["hidden"]
                print(f"[{contatore}/{totale}] {task['id']:<22} {lingua:<8} rip.{ripetizione}  {stato:<24} "
                      f"nascosti {h['passed']}/{h['total']}", flush=True)
