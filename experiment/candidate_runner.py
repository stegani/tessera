# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Esegue una soluzione candidata sui test, in un processo separato.

Uso:  python candidate_runner.py <tessera|python> <file del codice> <file JSON della specifica>
La specifica contiene: function, kind (plain | result | option), errors, tests [{args, expect}].
Stampa su stdout un JSON: {"compile_error": str | null, "results": [{"outcome", "got", "error"}]}.
outcome: "pass", "wrong" (risultato sbagliato senza errori) oppure "error" (il programma si e' fermato).
"""
import json
import math
import sys
import traceback
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))


def uguali(ottenuto, atteso):
    """Confronto dei valori neutri (JSON); i decimali con tolleranza, i bool mai come interi."""
    if isinstance(atteso, bool) or isinstance(ottenuto, bool):
        return isinstance(atteso, bool) and isinstance(ottenuto, bool) and atteso == ottenuto
    if isinstance(atteso, float) or isinstance(ottenuto, float):
        if not isinstance(ottenuto, (int, float)) or not isinstance(atteso, (int, float)):
            return False
        return math.isclose(ottenuto, atteso, rel_tol=1e-9, abs_tol=1e-12)
    if isinstance(atteso, list):
        return isinstance(ottenuto, list) and len(ottenuto) == len(atteso) and all(
            uguali(o, a) for o, a in zip(ottenuto, atteso))
    if isinstance(atteso, dict):
        return isinstance(ottenuto, dict) and ottenuto.keys() == atteso.keys() and all(
            uguali(ottenuto[k], atteso[k]) for k in atteso)
    return type(ottenuto) is type(atteso) and ottenuto == atteso


# ---------------------------------------------------------------- Tessera

def neutro_tessera(v):
    from tessera import values as V
    if isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        return [neutro_tessera(x) for x in v]
    if isinstance(v, V.NuovoTipo):
        return neutro_tessera(v.valore)
    if isinstance(v, V.ValoreVariante):
        if v.tipo == "Result":
            if v.nome == "Ok":
                return {"ok": neutro_tessera(v.valori[0])}
            interno = v.valori[0]
            return {"err": interno.nome if isinstance(interno, V.ValoreVariante) else V.formatta(interno, True)}
        if v.tipo == "Option":
            return {"some": neutro_tessera(v.valori[0])} if v.nome == "Some" else {"none": True}
        return {"variant": v.nome}
    return repr(v)


def esegui_tessera(file_codice, specifica):
    from tessera.checks import controlla_programma
    from tessera.errors import ErroreTessera
    from tessera.interpreter import Interprete, Programma

    try:
        programma = Programma(file_codice)
    except ErroreTessera as e:
        return {"compile_error": e.in_json(), "results": []}
    errori = controlla_programma(programma)
    funzione = programma.principale.funzioni.get(specifica["function"])
    if funzione is None:
        errori.append(ErroreTessera("nome", f"the module must define the function {specifica['function']}"))
    elif funzione.decl.effetti:
        errori.append(ErroreTessera("effetti", f"{specifica['function']} must be pure: declare effects: none",
                                    riga=funzione.decl.riga))
    if errori:
        return {"compile_error": "\n".join(e.in_json() for e in errori), "results": []}

    risultati = []
    for test in specifica["tests"]:
        interprete = Interprete(programma, eco=False)
        try:
            ottenuto = neutro_tessera(interprete.chiama_per_nome(specifica["function"], list(test["args"])))
            risultati.append({"outcome": "pass" if uguali(ottenuto, test["expect"]) else "wrong", "got": ottenuto})
        except ErroreTessera as e:
            risultati.append({"outcome": "error", "error": e.in_json()})
        except RecursionError:
            risultati.append({"outcome": "error", "error": "recursion limit exceeded"})
    return {"compile_error": None, "results": risultati}


# ---------------------------------------------------------------- Python

def neutro_python(v):
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [neutro_python(x) for x in v]
    return repr(v)


def esegui_python(file_codice, specifica):
    sorgente = Path(file_codice).read_text(encoding="utf-8")
    spazio = {"__name__": "solution"}
    try:
        exec(compile(sorgente, "solution.py", "exec"), spazio)
    except Exception:
        return {"compile_error": traceback.format_exc(limit=1).strip().splitlines()[-1], "results": []}
    funzione = spazio.get(specifica["function"])
    if not callable(funzione):
        return {"compile_error": f"the code must define the function {specifica['function']}", "results": []}

    errori_dichiarati = set(specifica.get("errors", []))
    risultati = []
    for test in specifica["tests"]:
        try:
            valore = funzione(*json.loads(json.dumps(test["args"])))
            if specifica["kind"] == "result":
                ottenuto = {"ok": neutro_python(valore)}
            elif specifica["kind"] == "option":
                ottenuto = {"none": True} if valore is None else {"some": neutro_python(valore)}
            else:
                ottenuto = neutro_python(valore)
        except RecursionError:
            risultati.append({"outcome": "error", "error": "RecursionError: maximum recursion depth exceeded"})
            continue
        except Exception as e:
            nome = type(e).__name__
            if specifica["kind"] == "result" and nome in errori_dichiarati:
                ottenuto = {"err": nome}
            else:
                risultati.append({"outcome": "error", "error": f"{nome}: {e}"})
                continue
        risultati.append({"outcome": "pass" if uguali(ottenuto, test["expect"]) else "wrong", "got": ottenuto})
    return {"compile_error": None, "results": risultati}


def main():
    lingua, file_codice, file_specifica = sys.argv[1:4]
    specifica = json.loads(Path(file_specifica).read_text(encoding="utf-8"))
    esito = esegui_tessera(file_codice, specifica) if lingua == "tessera" else esegui_python(file_codice, specifica)
    sys.stdout.write(json.dumps(esito, ensure_ascii=False))


if __name__ == "__main__":
    main()
