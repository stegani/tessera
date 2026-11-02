# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Soluzioni in Tessera scritte da un modello insegnante e verificate dal compilatore e dai test.

Lo stesso ciclo dell'esperimento (richiesta, errori, correzione), con due differenze: i messaggi di
correzione usano tutti i test, perche' questi esercizi non servono a misurare ma a insegnare, e la
conversazione viene conservata per intero, cosi' anche le correzioni diventano esempi.
"""
import time

from experiment import prompts, sandbox


def blocco(codice):
    return f"```tessera\n{codice.strip()}\n```"


def risolvi(modello, task, max_tentativi=4):
    """Restituisce il record della soluzione: i tentativi con codice ed errori, e se e' stata risolta."""
    sistema = prompts.sistema("tessera")
    richiesta = prompts.richiesta(task, "tessera")
    tutti = task["visible"] + task["hidden"]
    completo = dict(task, visible=tutti)         # per i messaggi di correzione
    messaggi = [{"role": "user", "content": richiesta}]
    tentativi, risolto = [], False
    for n in range(1, max_tentativi + 1):
        inizio = time.monotonic()
        risposta = modello.rispondi(sistema, messaggi, task=task, lingua="tessera", tentativo=n)
        if risposta.rifiutata:
            break
        codice = prompts.estrai_codice(risposta.testo, "tessera")
        esito = sandbox.esegui("tessera", codice, task, tutti)
        superati = sum(r["outcome"] == "pass" for r in esito["results"])
        risolto = not esito.get("compile_error") and superati == len(tutti)
        tentativo = {"n": n, "code": codice, "compile_error": esito.get("compile_error"), "passed": superati,
                     "total": len(tutti), "seconds": round(time.monotonic() - inizio, 2)}
        if not risolto:
            tentativo["feedback"] = prompts.correzione(completo, "tessera", esito)
        tentativi.append(tentativo)
        if risolto:
            break
        messaggi.append({"role": "assistant", "content": risposta.contenuto})
        messaggi.append({"role": "user", "content": tentativo["feedback"]})
    return {"task": task["id"], "teacher": modello.modello, "solved": risolto, "attempts": tentativi}


def esempi(task, record):
    """Gli esempi di addestramento ricavati da una soluzione verificata.

    - diretto: richiesta -> codice giusto;
    - correzione: richiesta -> codice sbagliato -> errore con suggerimento -> codice giusto.
      Il codice sbagliato resta nella conversazione ma non si impara ("train": false).
    """
    if not record["solved"]:
        return []
    sistema = prompts.sistema("tessera")
    richiesta = prompts.richiesta(task, "tessera")
    giusto = record["attempts"][-1]["code"]
    risultato = [{"task": task["id"], "type": "direct", "messages": [
        {"role": "system", "content": sistema},
        {"role": "user", "content": richiesta},
        {"role": "assistant", "content": blocco(giusto)},
    ]}]
    for sbagliato in record["attempts"][:-1]:
        risultato.append({"task": task["id"], "type": "repair", "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": richiesta},
            {"role": "assistant", "content": blocco(sbagliato["code"]), "train": False},
            {"role": "user", "content": sbagliato["feedback"]},
            {"role": "assistant", "content": blocco(giusto)},
        ]})
    return risultato
