# Copyright 2026 Stefano Stegani - Airgrid Network - www.airgrid.it
# SPDX-License-Identifier: Apache-2.0
"""Prompt per il modello, identici nella struttura per i due linguaggi.

Le uniche differenze volute: il prompt di sistema di Tessera contiene il manuale del linguaggio
(il modello non lo conosce), e gli esempi sono scritti nella sintassi di ciascun linguaggio.
I testi sono in inglese: e' la lingua in cui i modelli rendono meglio.
"""
import re
from pathlib import Path

QUI = Path(__file__).resolve().parent

ISTRUZIONI = {
    "tessera": ("You write code in Tessera, a new programming language. Its complete reference is below: "
                "use only what it describes.\n\nReply with one complete module in a single ```tessera code "
                "block, starting with `module solution`, and nothing else."),
    "python": ("You write Python 3.12 code.\n\nReply with the complete code in a single ```python code block "
               "and nothing else. If you need standard library modules, use only: math, re, string, collections, "
               "itertools, functools, bisect, heapq. Do not read or write files, use the network, or print."),
}


def sistema(lingua):
    if lingua == "tessera":
        return ISTRUZIONI["tessera"] + "\n\n" + (QUI / "tessera_reference.md").read_text(encoding="utf-8")
    return ISTRUZIONI["python"]


# ---------------------------------------------------------------- letterali

def letterale(valore, lingua):
    if lingua == "python":
        return repr(valore)
    if isinstance(valore, bool):
        return "true" if valore else "false"
    if isinstance(valore, (int, float)):
        return repr(valore)
    if isinstance(valore, str):
        sostituzioni = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "{": "\\{", "}": "\\}"}
        return '"' + "".join(sostituzioni.get(c, c) for c in valore) + '"'
    if isinstance(valore, list):
        return "[" + ", ".join(letterale(x, lingua) for x in valore) + "]"
    return repr(valore)


def tipo_errore(task):
    trovato = re.search(r"type (\w+)", task.get("tessera_types", ""))
    return trovato.group(1) if trovato else "Error"


def chiamata(task, args, lingua):
    return f"{task['function']}({', '.join(letterale(a, lingua) for a in args)})"


def descrivi_valore(valore, task, lingua):
    """Un valore neutro (come nei test) scritto nella sintassi del linguaggio."""
    if isinstance(valore, dict):
        if "ok" in valore:
            return f"Ok({letterale(valore['ok'], lingua)})" if lingua == "tessera" else letterale(valore["ok"], lingua)
        if "err" in valore:
            return f"Err({tipo_errore(task)}.{valore['err']})" if lingua == "tessera" else f"raises {valore['err']}"
        if "some" in valore:
            return f"Some({letterale(valore['some'], lingua)})" if lingua == "tessera" else letterale(valore["some"], lingua)
        if "none" in valore:
            return "None"
        if "variant" in valore:
            return valore["variant"]
    return letterale(valore, lingua)


def esempio(task, test, lingua):
    testo_chiamata = chiamata(task, test["args"], lingua)
    atteso = descrivi_valore(test["expect"], task, lingua)
    if lingua == "python" and isinstance(test["expect"], dict) and "err" in test["expect"]:
        return f"{testo_chiamata}  # {atteso}"
    if lingua == "python" and isinstance(test["expect"], dict) and "none" in test["expect"]:
        return f"{testo_chiamata} is None"
    return f"{testo_chiamata} == {atteso}"


# ---------------------------------------------------------------- richiesta e correzione

def richiesta(task, lingua):
    blocco = "tessera" if lingua == "tessera" else "python"
    firma = task["tessera_signature"] if lingua == "tessera" else task["python_signature"]
    parti = [f"Write the function `{task['function']}`.", "", task["description"], "",
             "Signature:", f"```{blocco}", firma, "```"]
    if task["kind"] == "result":
        if lingua == "tessera":
            parti += ["", "Define and use exactly this error type:", "```tessera", task["tessera_types"], "```"]
        else:
            nomi = ", ".join(task["errors"])
            parti += ["", f"Report each failure by raising an exception. Define one exception class per failure, "
                          f"named exactly: {nomi}."]
    if task["kind"] == "option" and lingua == "python":
        parti += ["", "Return None for \"nothing\"."]
    parti += ["", "Examples:", f"```{blocco}"] + [esempio(task, t, lingua) for t in task["visible"]] + ["```"]
    return "\n".join(parti)


def errori_leggibili(testo):
    """Gli errori di Tessera arrivano come JSON, uno per riga: li riscrive come 'line N: ...' con il suggerimento."""
    import json
    righe = []
    for riga in testo.splitlines():
        try:
            e = json.loads(riga)
        except ValueError:
            righe.append(riga)
            continue
        prefisso = f"line {e['riga']}: " if e.get("riga") else ""
        righe.append(prefisso + e.get("messaggio", riga))
        if e.get("suggerimento"):
            righe.append(f"  Hint: {e['suggerimento']}")
    return "\n".join(righe)


def correzione(task, lingua, esito):
    """Messaggio di ritorno dopo un tentativo fallito: solo i test visibili, mai quelli nascosti."""
    if esito.get("compile_error"):
        return ("Your code was rejected:\n```\n" + errori_leggibili(esito["compile_error"]) +
                "\n```\nFix it and reply with the complete corrected code.")
    righe = []
    for test, r in zip(task["visible"], esito["results"]):
        if r["outcome"] == "pass":
            continue
        atteso = descrivi_valore(test["expect"], task, lingua)
        testo_chiamata = chiamata(task, test["args"], lingua)
        if r["outcome"] == "error":
            righe.append(f"- {testo_chiamata}: expected {atteso}, but it stopped with: {r['error']}")
        else:
            righe.append(f"- {testo_chiamata}: expected {atteso}, got {descrivi_valore(r['got'], task, lingua)}")
    return "Some examples fail:\n" + "\n".join(righe) + "\nFix it and reply with the complete corrected code."


def estrai_codice(testo, lingua):
    blocchi = re.findall(r"```([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```", testo, re.DOTALL)
    for etichetta, codice in blocchi:
        if etichetta.lower() in ({"tessera", "tsr"} if lingua == "tessera" else {"python", "py"}):
            return codice.strip() + "\n"
    if blocchi:
        return blocchi[0][1].strip() + "\n"
    return testo.strip() + "\n"
