# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Esercizi di addestramento, nello stesso formato di experiment/tasks.json.

Un modello insegnante propone l'esercizio: descrizione, parametri, una soluzione Python di riferimento
e gli input da provare. I risultati attesi non li scrive il modello: li calcola la soluzione di
riferimento, eseguita nella sandbox. Le firme in Tessera e in Python le costruisce questo modulo a
partire dai tipi, cosi' sono sempre coerenti.

Gli esercizi dell'esperimento non devono finire nei dati: un esercizio con lo stesso nome o con una
descrizione troppo simile viene scartato.
"""
import json
import random
import re

from experiment import sandbox

TEMI = [
    "counting characters or words in text", "changing letter case and spacing", "parsing integers from text",
    "validating the format of an identifier or code", "validating a simple date or time string",
    "splitting text into tokens", "padding, trimming or aligning text", "finding substrings or positions",
    "run-length or other simple text encodings", "letter-shifting ciphers", "palindromes and anagrams",
    "sum, minimum, maximum or average of a list", "filtering a list by a condition", "sliding windows over a list",
    "sorting-related checks (sorted, rank, median)", "removing or counting duplicates", "prefix sums and differences",
    "two-pointer techniques on lists", "merging or interleaving lists", "rotating or chunking lists",
    "digits of a number", "greatest common divisor and least common multiple", "prime numbers",
    "number bases (binary, hexadecimal) as text", "arithmetic that must detect overflow",
    "integer rounding, percentages and money in cents", "safe parsing that reports why it failed",
    "checking that untrusted input stays within limits", "escaping special characters in text",
    "checking that a file path stays inside a folder", "simple rate limits and quotas",
    "searching a list for an element", "scores, grades and ranking", "simple state machines over text",
    "checksums and check digits", "intervals and ranges of numbers", "bit-free boolean logic over lists",
]
TIPI_BASE = {"i64": "int", "f64": "float", "bool": "bool", "Str": "str"}
TIPI = list(TIPI_BASE) + [f"List[{t}]" for t in TIPI_BASE]
GENERI = ["plain", "plain", "option", "result"]      # come nell'esperimento: piu' esercizi semplici
MIN_TEST, MAX_TEST, VISIBILI = 6, 12, 3
I64_MIN, I64_MAX = -2**63, 2**63 - 1

PROMPT = """You design small programming exercises that will be used as training data.

Design ONE new exercise. Topic: {tema}. Kind: {genere}.

Kinds: "plain" returns a value; "option" returns a value or nothing; "result" returns a value or one of
2-4 named failures.

Reply with one JSON object in a single ```json code block, with exactly these keys:
- "function": a new snake_case function name
- "description": 1-4 precise sentences; state what happens in every edge case (empty input, zero,
  negative numbers, limits){result_hint}
- "params": a list of [name, type] pairs, 1 to 3 parameters
- "returns": the type of the returned value
- "errors": {errors_hint}
- "python_reference": a correct Python 3 function with that name and those parameters.{python_hint}
  Use only the standard library modules math and string; do not print or read files.
- "inputs": {n} argument lists (one list per call, values in parameter order) that cover normal cases
  and every edge case. Keep strings under 60 characters and lists under 20 elements.

Types: {tipi}. "i64" is a signed 64-bit integer, "f64" a floating-point number, "Str" text.
Do not use any of these names: {nomi}."""

SUGGERIMENTI = {
    "plain": ("", "a list with no elements: []", ""),
    "option": (", and when the function returns nothing", "a list with no elements: []",
               " Return None for nothing."),
    "result": (", and which failure is reported in each case",
               "a list of 2-4 failure names in CamelCase, for example [\"Empty\", \"TooLong\"]",
               " Define one exception class per failure name (class Empty(Exception): pass) and raise it."),
}


def prompt(tema, genere, nomi_usati, n=10):
    risultato, errori, python = SUGGERIMENTI[genere]
    return PROMPT.format(tema=tema, genere=genere, result_hint=risultato, errors_hint=errori,
                         python_hint=python, n=n, tipi=", ".join(TIPI),
                         nomi=", ".join(sorted(nomi_usati)) or "(none)")


def estrai_json(testo):
    blocchi = re.findall(r"```(?:json)?[ \t]*\n(.*?)```", testo, re.DOTALL)
    for candidato in blocchi + [testo[testo.find("{"):testo.rfind("}") + 1]]:
        try:
            dati = json.loads(candidato)
        except ValueError:
            continue
        if isinstance(dati, dict):
            return dati
    return None


# ---------------------------------------------------------------- tipi

def tipo_python(tipo):
    if tipo.startswith("List["):
        return f"list[{TIPI_BASE[tipo[5:-1]]}]"
    return TIPI_BASE[tipo]


def conforme(valore, tipo):
    """Il valore JSON e' del tipo Tessera indicato? Per f64 accetta anche gli interi (2 vale 2.0)."""
    if tipo.startswith("List["):
        return isinstance(valore, list) and all(conforme(v, tipo[5:-1]) for v in valore)
    if tipo == "bool":
        return isinstance(valore, bool)
    if tipo == "i64":
        return isinstance(valore, int) and not isinstance(valore, bool) and I64_MIN <= valore <= I64_MAX
    if tipo == "f64":
        return isinstance(valore, (int, float)) and not isinstance(valore, bool) and abs(valore) < 1e300
    if tipo == "Str":
        return isinstance(valore, str)
    return False


def in_decimale(valore, tipo):
    """Gli interi passati dove serve un f64 diventano decimali: Tessera non mescola i due tipi."""
    if tipo.startswith("List["):
        return [in_decimale(v, tipo[5:-1]) for v in valore]
    return float(valore) if tipo == "f64" else valore


def pascal(nome):
    return "".join(parte.capitalize() for parte in nome.split("_"))


# ---------------------------------------------------------------- dall'idea all'esercizio

class Scartato(Exception):
    """L'esercizio proposto non e' utilizzabile; il messaggio dice perche'."""


def costruisci(proposta, genere):
    """Dalla proposta del modello alle firme dei due linguaggi. Non esegue ancora nulla."""
    for chiave in ("function", "description", "params", "returns", "python_reference", "inputs"):
        if chiave not in proposta:
            raise Scartato(f"manca '{chiave}'")
    funzione = proposta["function"]
    if not isinstance(funzione, str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", funzione):
        raise Scartato(f"nome non valido: {funzione!r}")
    parametri = proposta["params"]
    if not isinstance(parametri, list) or not 1 <= len(parametri) <= 3:
        raise Scartato("da 1 a 3 parametri")
    for p in parametri:
        if not (isinstance(p, list) and len(p) == 2 and re.fullmatch(r"[a-z][a-z0-9_]*", str(p[0]))
                and p[1] in TIPI):
            raise Scartato(f"parametro non valido: {p!r}")
    if proposta["returns"] not in TIPI:
        raise Scartato(f"tipo restituito non valido: {proposta['returns']!r}")

    ritorno = proposta["returns"]
    task = {"id": funzione, "function": funzione, "kind": genere, "description": str(proposta["description"]),
            "params": parametri, "returns": ritorno, "python_reference": str(proposta["python_reference"])}
    firma = ", ".join(f"{n}: {t}" for n, t in parametri)
    firma_py = ", ".join(f"{n}: {tipo_python(t)}" for n, t in parametri)
    if genere == "plain":
        task["tessera_signature"] = f"pub fn {funzione}({firma}) -> {ritorno}"
        task["python_signature"] = f"def {funzione}({firma_py}) -> {tipo_python(ritorno)}"
    elif genere == "option":
        task["tessera_signature"] = f"pub fn {funzione}({firma}) -> Option[{ritorno}]"
        task["python_signature"] = f"def {funzione}({firma_py}) -> {tipo_python(ritorno)} | None"
    else:
        errori = proposta.get("errors")
        if (not isinstance(errori, list) or not 2 <= len(errori) <= 4 or len(set(errori)) != len(errori)
                or not all(isinstance(e, str) and re.fullmatch(r"[A-Z][A-Za-z0-9]{1,30}", e) for e in errori)
                or set(errori) & {"Ok", "Err", "Some", "None"}):
            raise Scartato(f"errori non validi: {errori!r}")
        tipo_errore = pascal(funzione) + "Error"
        task["errors"] = errori
        task["tessera_types"] = (f"pub type {tipo_errore} do\n" + "".join(f"  case {e}\n" for e in errori)
                                 + f"end type {tipo_errore}")
        task["tessera_signature"] = f"pub fn {funzione}({firma}) -> Result[{ritorno}, {tipo_errore}]"
        task["python_signature"] = f"def {funzione}({firma_py}) -> {tipo_python(ritorno)}"
    return task


def firma_valida(task):
    """La firma costruita deve essere accettata dalla grammatica di Tessera."""
    from tessera.errors import ErroreTessera
    from tessera.parser import analizza
    testo = ("module solution\n\n" + (task.get("tessera_types", "") + "\n\n" if "tessera_types" in task else "")
             + task["tessera_signature"] + "\n  effects: none\ndo\n  return x\nend fn " + task["function"] + "\n")
    try:
        analizza(testo)
    except ErroreTessera as e:
        raise Scartato(f"firma rifiutata dalla grammatica: {e}") from None


def calcola_test(task, proposta):
    """Esegue la soluzione di riferimento sugli input proposti; i risultati diventano i valori attesi."""
    tipi = [t for _, t in task["params"]]
    argomenti = []
    for args in proposta["inputs"] if isinstance(proposta["inputs"], list) else []:
        if (isinstance(args, list) and len(args) == len(tipi) and all(conforme(a, t) for a, t in zip(args, tipi))
                and len(json.dumps(args)) <= 400):
            args = [in_decimale(a, t) for a, t in zip(args, tipi)]
            if args not in argomenti:
                argomenti.append(args)
    if len(argomenti) < MIN_TEST:
        raise Scartato(f"solo {len(argomenti)} input validi")
    argomenti = argomenti[:MAX_TEST]

    esito = sandbox.esegui("python", task["python_reference"], task, [{"args": a, "expect": None} for a in argomenti])
    if esito.get("compile_error"):
        raise Scartato(f"la soluzione di riferimento non funziona: {esito['compile_error']}")
    test = []
    for args, r in zip(argomenti, esito["results"]):
        if r["outcome"] == "error" or "got" not in r:
            continue                        # un input che fa fallire il riferimento non dice nulla
        atteso = r["got"]
        valore = atteso.get("ok", atteso.get("some")) if isinstance(atteso, dict) else atteso
        if isinstance(atteso, dict) and "err" in atteso:
            if atteso["err"] not in task.get("errors", []):
                continue
        elif isinstance(atteso, dict) and "none" in atteso:
            pass
        elif not conforme(valore, task["returns"]):
            continue
        else:
            valore = in_decimale(valore, task["returns"])
            atteso = {"ok": valore} if task["kind"] == "result" else (
                {"some": valore} if task["kind"] == "option" else valore)
        test.append({"args": args, "expect": atteso})
    if len(test) < MIN_TEST:
        raise Scartato(f"solo {len(test)} test utilizzabili")
    if len({json.dumps(t["expect"], sort_keys=True) for t in test}) < 2:
        raise Scartato("tutti i test danno lo stesso risultato")
    if task["kind"] == "result" and not (any("err" in t["expect"] for t in test)
                                         and any("ok" in t["expect"] for t in test)):
        raise Scartato("servono test con successo e con fallimento")
    if task["kind"] == "option" and not (any("none" in t["expect"] for t in test)
                                         and any("some" in t["expect"] for t in test)):
        raise Scartato("servono test con un valore e senza")
    return test


# ---------------------------------------------------------------- contaminazione e doppioni

def parole(testo):
    return set(re.findall(r"[a-z0-9]+", testo.lower()))


def somiglianza(a, b):
    pa, pb = parole(a), parole(b)
    return len(pa & pb) / len(pa | pb) if pa | pb else 0.0


def controlla_novita(task, valutazione, esistenti, soglia_valutazione=0.5, soglia_doppioni=0.7):
    """Scarta gli esercizi dell'esperimento (stesso nome o descrizione simile) e i doppioni."""
    for t in valutazione:
        if task["function"] == t["function"]:
            raise Scartato(f"stesso nome di un esercizio dell'esperimento: {t['function']}")
        if somiglianza(task["description"], t["description"]) >= soglia_valutazione:
            raise Scartato(f"troppo simile all'esercizio dell'esperimento {t['function']}")
    for t in esistenti:
        if task["function"] == t["function"]:
            raise Scartato(f"nome gia' usato: {t['function']}")
        if somiglianza(task["description"], t["description"]) >= soglia_doppioni:
            raise Scartato(f"doppione di {t['function']}")


def da_proposta(testo, genere, valutazione, esistenti):
    """Dal testo del modello all'esercizio completo di test. Solleva Scartato se non va bene."""
    proposta = estrai_json(testo)
    if proposta is None:
        raise Scartato("nessun JSON leggibile nella risposta")
    task = costruisci(proposta, genere)
    controlla_novita(task, valutazione, esistenti)
    firma_valida(task)
    test = calcola_test(task, proposta)
    task["visible"], task["hidden"] = test[:VISIBILI], test[VISIBILI:]
    return task


def genera(modello, n, valutazione, esistenti, scrivi, seme=None, stampa=print):
    """Chiede esercizi al modello finche' non ne ha n validi; ognuno viene passato a scrivi()."""
    caso = random.Random(seme)
    nomi = {t["function"] for t in valutazione} | {t["function"] for t in esistenti}
    validi = tentativi = 0
    while validi < n and tentativi < n * 4:
        tentativi += 1
        tema, genere = caso.choice(TEMI), caso.choice(GENERI)
        # Al modello basta un campione dei nomi gia' usati: tutti renderebbero il prompt troppo lungo.
        campione = caso.sample(sorted(nomi), min(len(nomi), 60))
        try:
            risposta = modello.rispondi("You are a careful programming teacher.",
                                        [{"role": "user", "content": prompt(tema, genere, campione)}])
            task = da_proposta(risposta.testo, genere, valutazione, esistenti)
        except Scartato as e:
            stampa(f"[{validi}/{n}] scartato ({genere}, {tema}): {e}")
            continue
        task["topic"] = tema
        scrivi(task)
        esistenti.append(task)
        nomi.add(task["function"])
        validi += 1
        stampa(f"[{validi}/{n}] {task['function']} ({genere}): {len(task['visible']) + len(task['hidden'])} test")
    return validi
