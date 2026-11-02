# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Test della generazione dei dati di addestramento (senza modelli veri e senza GPU)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiment.__main__ import carica_compiti          # noqa: E402
from experiment.models import Risposta                  # noqa: E402
from training import dataset, solve, tasks              # noqa: E402

VOCALI = {
    "function": "count_vowels",
    "description": "Count the letters a, e, i, o, u in the text, ignoring case. Empty text has zero vowels.",
    "params": [["text", "Str"]],
    "returns": "i64",
    "python_reference": "def count_vowels(text):\n    return sum(1 for c in text.lower() if c in 'aeiou')\n",
    "inputs": [["hello"], [""], ["AEIOU"], ["xyz"], ["Banana"], ["a e"], ["hello"], [42]],
}

PERCENTUALE = {
    "function": "parse_percent",
    "description": "Read a whole percentage between 0 and 100 written with ASCII digits only.",
    "params": [["text", "Str"]],
    "returns": "i64",
    "errors": ["Empty", "Invalid", "OutOfRange"],
    "python_reference": (
        "class Empty(Exception): pass\nclass Invalid(Exception): pass\nclass OutOfRange(Exception): pass\n"
        "def parse_percent(text):\n    if text == '':\n        raise Empty()\n"
        "    if not all(c in '0123456789' for c in text):\n        raise Invalid()\n"
        "    v = int(text)\n    if v > 100:\n        raise OutOfRange()\n    return v\n"),
    "inputs": [["50"], ["0"], ["100"], ["101"], [""], ["abc"], ["7"]],
}

VOCALI_TSR = """module solution

pub fn count_vowels(text: Str) -> i64
  effects: none
do
  var n = 0
  for c in text.chars() do
    if "aeiou".contains(c.lower()) do
      n += 1
    end if
  end for
  return n
end fn count_vowels
"""


def in_risposta(proposta):
    return "Here it is:\n```json\n" + json.dumps(proposta) + "\n```"


def test_esercizio_semplice_con_test_calcolati():
    task = tasks.da_proposta(in_risposta(VOCALI), "plain", carica_compiti(), [])
    assert task["tessera_signature"] == "pub fn count_vowels(text: Str) -> i64"
    assert task["python_signature"] == "def count_vowels(text: str) -> int"
    tutti = task["visible"] + task["hidden"]
    # l'input ripetuto e quello del tipo sbagliato (42) sono scartati; i valori attesi li calcola Python
    assert [t["args"] for t in tutti] == [["hello"], [""], ["AEIOU"], ["xyz"], ["Banana"], ["a e"]]
    assert [t["expect"] for t in tutti] == [2, 0, 5, 0, 3, 2]
    assert len(task["visible"]) == tasks.VISIBILI


def test_esercizio_con_errori():
    task = tasks.da_proposta(in_risposta(PERCENTUALE), "result", carica_compiti(), [])
    assert task["tessera_signature"] == "pub fn parse_percent(text: Str) -> Result[i64, ParsePercentError]"
    assert "case OutOfRange" in task["tessera_types"]
    attesi = {t["args"][0]: t["expect"] for t in task["visible"] + task["hidden"]}
    assert attesi == {"50": {"ok": 50}, "0": {"ok": 0}, "100": {"ok": 100}, "101": {"err": "OutOfRange"},
                      "": {"err": "Empty"}, "abc": {"err": "Invalid"}, "7": {"ok": 7}}
    tasks.firma_valida(task)


def test_decimali_e_option():
    proposta = {
        "function": "mean_value", "description": "Mean of the values, nothing for an empty list.",
        "params": [["values", "List[f64]"]], "returns": "f64",
        "python_reference": "def mean_value(values):\n    return sum(values) / len(values) if values else None\n",
        "inputs": [[[1, 2]], [[]], [[2.5]], [[-1, 1]], [[3, 3, 3]], [[0.5, 1.5]]],
    }
    task = tasks.da_proposta(in_risposta(proposta), "option", carica_compiti(), [])
    primo = task["visible"][0]
    assert primo["args"] == [[1.0, 2.0]] and isinstance(primo["args"][0][0], float)
    assert primo["expect"] == {"some": 1.5}
    assert task["visible"][1]["expect"] == {"none": True}


@pytest.mark.parametrize("modifica, messaggio", [
    ({"function": "word_count"}, "esperimento"),
    ({"description": "Count the words in the text. Words are separated by one or more space characters"}, "simile"),
    ({"function": "Bad-Name"}, "nome"),
    ({"returns": "Dict[Str, i64]"}, "tipo restituito"),
    ({"params": [["text", "string"]]}, "parametro"),
    ({"python_reference": "import os\ndef count_vowels(text):\n    return 0\n"}, "riferimento"),
    ({"inputs": [["a"], ["b"]]}, "input validi"),
    ({"python_reference": "def count_vowels(text):\n    return 1\n"}, "stesso risultato"),
])
def test_proposte_scartate(modifica, messaggio):
    with pytest.raises(tasks.Scartato, match=messaggio):
        tasks.da_proposta(in_risposta(dict(VOCALI, **modifica)), "plain", carica_compiti(), [])


def test_errori_senza_fallimenti_scartati():
    proposta = dict(PERCENTUALE, inputs=[["1"], ["2"], ["3"], ["4"], ["5"], ["6"]])
    with pytest.raises(tasks.Scartato, match="fallimento"):
        tasks.da_proposta(in_risposta(proposta), "result", carica_compiti(), [])


def test_doppione_scartato():
    primo = tasks.da_proposta(in_risposta(VOCALI), "plain", carica_compiti(), [])
    with pytest.raises(tasks.Scartato, match="nome"):
        tasks.da_proposta(in_risposta(VOCALI), "plain", carica_compiti(), [primo])


class Insegnante:
    """Un insegnante finto: risponde con le soluzioni indicate, una per tentativo."""
    modello = "finto"

    def __init__(self, risposte):
        self.risposte = list(risposte)

    def rispondi(self, sistema, messaggi, **_):
        testo = self.risposte.pop(0)
        return Risposta(testo=testo, contenuto=testo, modello=self.modello)


def test_soluzione_con_correzione_e_dataset():
    task = tasks.da_proposta(in_risposta(VOCALI), "plain", carica_compiti(), [])
    sbagliato = "```tessera\n" + VOCALI_TSR.replace("var n = 0", "let mut n = 0") + "```"
    giusto = "```tessera\n" + VOCALI_TSR + "```"
    record = solve.risolvi(Insegnante([sbagliato, giusto]), task, max_tentativi=3)
    assert record["solved"] and len(record["attempts"]) == 2
    assert "Hint" in record["attempts"][0]["feedback"]

    esempi = solve.esempi(task, record)
    assert [e["type"] for e in esempi] == ["direct", "repair"]
    riparazione = esempi[1]["messages"]
    assert riparazione[2]["train"] is False and "let mut" in riparazione[2]["content"]
    assert riparazione[-1]["content"].startswith("```tessera\nmodule solution")

    record["sample"] = 1
    doppio = dict(record, sample=2)
    addestramento, validazione, statistiche = dataset.costruisci([task], [record, doppio], carica_compiti())
    assert len(addestramento) == 2 and validazione == []
    assert statistiche["scartati"] == {"soluzione doppia": 1}
    assert dataset.verifica([task], [record]) == []


def test_soluzione_non_trovata():
    task = tasks.da_proposta(in_risposta(VOCALI), "plain", carica_compiti(), [])
    record = solve.risolvi(Insegnante(["no code"] * 2), task, max_tentativi=2)
    assert not record["solved"] and solve.esempi(task, record) == []
