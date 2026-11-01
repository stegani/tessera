# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Esecuzione isolata dei candidati: processo separato, cartella temporanea, limite di tempo.

Il codice Python generato da un modello viene prima controllato: niente import fuori da una lista
consentita, niente accesso a file, rete, eval o introspezione. Non e' una sandbox completa: per
un'esecuzione su larga scala conviene lanciare l'esperimento in un container.
Il codice Tessera non ha bisogno del filtro: il linguaggio rifiuta da solo gli effetti non dichiarati.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RUNNER = Path(__file__).resolve().parent / "candidate_runner.py"
LIMITE_SECONDI = 10

IMPORT_CONSENTITI = {"math", "re", "string", "collections", "itertools", "functools", "typing",
                     "dataclasses", "enum", "bisect", "heapq", "__future__"}
NOMI_VIETATI = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals", "locals",
                "vars", "getattr", "setattr", "delattr", "memoryview", "help", "exit", "quit"}
ATTRIBUTI_VIETATI = {"__globals__", "__subclasses__", "__builtins__", "__code__", "__dict__", "__bases__",
                     "__mro__", "__loader__", "__spec__", "__closure__", "f_globals", "f_locals", "gi_frame"}


def controlla_python(sorgente):
    """Restituisce un messaggio d'errore se il codice usa qualcosa di vietato, altrimenti None."""
    try:
        albero = ast.parse(sorgente)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name.split(".")[0] not in IMPORT_CONSENTITI:
                    return f"import of '{alias.name}' is not allowed"
        elif isinstance(nodo, ast.ImportFrom):
            if (nodo.module or "").split(".")[0] not in IMPORT_CONSENTITI:
                return f"import from '{nodo.module}' is not allowed"
        elif isinstance(nodo, ast.Name) and nodo.id in NOMI_VIETATI:
            return f"use of '{nodo.id}' is not allowed"
        elif isinstance(nodo, ast.Attribute) and nodo.attr in ATTRIBUTI_VIETATI:
            return f"access to '{nodo.attr}' is not allowed"
    return None


def esegui(lingua, codice, task, test):
    """Esegue il codice sui test indicati. Restituisce il JSON del runner, piu' gli errori di tempo."""
    if lingua == "python":
        vietato = controlla_python(codice)
        if vietato:
            return {"compile_error": vietato, "results": []}
    specifica = {"function": task["function"], "kind": task["kind"], "errors": task.get("errors", []),
                 "tests": test}
    with tempfile.TemporaryDirectory(prefix="tessera-exp-") as cartella:
        file_codice = Path(cartella) / ("solution.tsr" if lingua == "tessera" else "solution.py")
        file_codice.write_text(codice, encoding="utf-8")
        file_specifica = Path(cartella) / "spec.json"
        file_specifica.write_text(json.dumps(specifica, ensure_ascii=False), encoding="utf-8")
        ambiente = {"PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                    "PYTHONIOENCODING": "utf-8"}
        # -I: modalita' isolata (niente variabili PYTHON*, niente cartella corrente nel percorso dei moduli).
        comando = [sys.executable, "-I", "-X", "utf8", str(RUNNER), lingua, str(file_codice), str(file_specifica)]
        try:
            uscita = subprocess.run(comando, cwd=cartella, env=ambiente, capture_output=True, text=True,
                                    encoding="utf-8", timeout=LIMITE_SECONDI)
        except subprocess.TimeoutExpired:
            return {"compile_error": None,
                    "results": [{"outcome": "error", "error": f"timeout after {LIMITE_SECONDI} s"} for _ in test]}
    if uscita.returncode != 0 or not uscita.stdout.strip():
        dettaglio = (uscita.stderr or "").strip().splitlines()[-1:] or ["no output"]
        return {"compile_error": None,
                "results": [{"outcome": "error", "error": f"runner crashed: {dettaglio[0]}"} for _ in test]}
    return json.loads(uscita.stdout)
