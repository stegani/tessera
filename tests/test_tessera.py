# Copyright 2026 Stefano Stegani - Airgrid Network - www.airgrid.it
# SPDX-License-Identifier: Apache-2.0
"""Test del prototipo: grammatica, esempi, semantica dell'interprete, controlli statici, compilatore."""
import random
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
sys.path.insert(0, str(RADICE / "tools"))

from tessera.wasm_compiler import Esecutore, compila_modulo  # noqa: E402
from tessera.checks import controlla_programma  # noqa: E402
from tessera.errors import ErroreTessera  # noqa: E402
from tessera.interpreter import Interprete, Programma  # noqa: E402
from tessera.parser import analizza_file  # noqa: E402

ESEMPI = RADICE / "examples"
ESEGUIBILI = ["hello", "checkout", "warehouse", "permissions", "prices", "numbers"]


def programma(tmp_path, sorgente, nome="prova.tsr"):
    f = tmp_path / nome
    f.write_text(sorgente, encoding="utf-8")
    return Programma(f)


def errori_statici(tmp_path, sorgente):
    return controlla_programma(programma(tmp_path, sorgente))


def esegui(tmp_path, sorgente):
    interprete = Interprete(programma(tmp_path, sorgente), eco=False)
    interprete.esegui_programma()
    return interprete.uscite


def main(corpo, effetti="console"):
    righe = "".join(f"  {r}\n" for r in corpo.strip().splitlines())
    return f"module prova\n\nfn main()\n  effects: {effetti}\ndo\n{righe}end fn main\n"


def fallisce(tmp_path, sorgente, tipo, frammento=""):
    with pytest.raises(ErroreTessera) as info:
        esegui(tmp_path, sorgente)
    assert info.value.tipo == tipo, str(info.value)
    assert frammento in info.value.messaggio, str(info.value)
    return info.value


# ---------- grammatica ed esempi ----------

def test_grammatica():
    import check_grammar
    assert check_grammar.main() == 0


@pytest.mark.parametrize("nome", ESEGUIBILI)
def test_esempi_senza_errori_statici(nome):
    assert controlla_programma(Programma(ESEMPI / f"{nome}.tsr")) == []


@pytest.mark.parametrize("nome", ["prices", "numbers", "warehouse"])
def test_clausole_example(nome):
    esiti = Interprete(Programma(ESEMPI / f"{nome}.tsr"), eco=False).esegui_esempi()
    assert esiti and all(e[2] for e in esiti), [e for e in esiti if not e[2]]


def uscite(nome):
    interprete = Interprete(Programma(ESEMPI / f"{nome}.tsr"), eco=False)
    interprete.esegui_programma()
    return interprete.uscite


def test_ciao():
    assert uscite("hello") == ["Ciao, Tessera!"]


def test_cassa():
    assert uscite("checkout")[-2:] == ["Totale: 16.49 EUR", "Con lo sconto del 10%: 14.85 EUR"]


def test_magazzino():
    righe = uscite("warehouse")
    assert "rifiutato: scorte insufficienti di viti: 120 disponibili, 500 richiesti" in righe
    assert righe[-1] == "Archiviati: viti, bulloni"


def test_permessi():
    assert uscite("permissions")[0].startswith("Letto: Questo file si puo' leggere")


# ---------- semantica dell'interprete ----------

def test_overflow(tmp_path):
    fallisce(tmp_path, main("var x = 9_223_372_036_854_775_807\nx += 1"), "esecuzione", "overflow")


def test_divisione_per_zero(tmp_path):
    fallisce(tmp_path, main("let zero = 0\nprint(1 / zero)"), "esecuzione", "divisione per zero")


def test_divisione_tronca_verso_zero(tmp_path):
    assert esegui(tmp_path, main("print(-7 / 2)\nprint(-7 % 2)")) == ["-3", "-1"]


def test_interi_e_decimali_non_si_mescolano(tmp_path):
    e = fallisce(tmp_path, main("print(1 + 2.0)"), "tipo", "non si mescolano")
    assert "to_f64" in e.suggerimento


def test_stringhe_si_compongono_con_interpolazione(tmp_path):
    e = fallisce(tmp_path, main('let a = "x"\nprint(a + "y")'), "tipo", "stringhe")
    assert "interpolazione" in e.suggerimento


def test_secret_non_si_stampa(tmp_path):
    fallisce(tmp_path, main('let chiave = Secret("123")\nprint("chiave: {chiave}")'), "sicurezza", "Secret")


def test_semantica_dei_valori(tmp_path):
    assert esegui(tmp_path, main("var a = [1, 2]\nlet b = a\na.push(3)\nprint(b)\nprint(a)")) == ["[1, 2]", "[1, 2, 3]"]


def test_edit_modifica_la_variabile_del_chiamante(tmp_path):
    sorgente = main("var n = 1\nraddoppia(edit n)\nprint(n)") + (
        "\nfn raddoppia(edit x: i64)\n  effects: none\ndo\n  x *= 2\nend fn raddoppia\n")
    assert esegui(tmp_path, sorgente) == ["2"]


def test_edit_senza_parola_alla_chiamata(tmp_path):
    sorgente = main("var n = 1\nraddoppia(n)") + (
        "\nfn raddoppia(edit x: i64)\n  effects: none\ndo\n  x *= 2\nend fn raddoppia\n")
    e = fallisce(tmp_path, sorgente, "proprieta", "edit")
    assert "scrivi edit n" in e.suggerimento


def test_uso_dopo_take(tmp_path):
    sorgente = main("var l = [1]\nconsuma(take l)\nprint(l)") + (
        "\nfn consuma(take x: List[i64])\n  effects: none\ndo\n  return\nend fn consuma\n")
    fallisce(tmp_path, sorgente, "proprieta", "take")
    assert any(e.tipo == "proprieta" and "take" in e.messaggio for e in errori_statici(tmp_path, sorgente))


def test_requires_violata(tmp_path):
    sorgente = main("print(radice(-1))") + (
        "\nfn radice(x: i64) -> i64\n  effects: none\n  requires: x >= 0\ndo\n  return x\nend fn radice\n")
    fallisce(tmp_path, sorgente, "contratto", "requires violata: x >= 0")


def test_ensures_violata(tmp_path):
    sorgente = main("print(sbagliata(3))") + (
        "\nfn sbagliata(x: i64) -> i64\n  effects: none\n  ensures: result > x\ndo\n  return x - 1\nend fn sbagliata\n")
    fallisce(tmp_path, sorgente, "contratto", "ensures violata")


def test_tipo_del_parametro(tmp_path):
    sorgente = main('print(doppio("3"))') + (
        "\nfn doppio(x: i64) -> i64\n  effects: none\ndo\n  return x * 2\nend fn doppio\n")
    fallisce(tmp_path, sorgente, "tipo", "atteso i64")


def test_result_ignorato(tmp_path):
    fallisce(tmp_path, main('"12".to_int()'), "tipo", "ignorato")


def test_effetto_non_dichiarato(tmp_path):
    sorgente = main("saluta()") + "\nfn saluta()\n  effects: none\ndo\n  print(\"ciao\")\nend fn saluta\n"
    statici = errori_statici(tmp_path, sorgente)
    assert any(e.tipo == "effetti" and "console" in e.messaggio for e in statici)
    fallisce(tmp_path, sorgente, "effetti", "console")


def test_funzione_anonima_non_acquista_effetti(tmp_path):
    sorgente = main("let f = crea()\nf(1)") + (
        "\nfn crea() -> fn(i64) -> i64\n  effects: none\ndo\n  return fn(x) => stampa_e_restituisci(x)\nend fn crea\n"
        "\nfn stampa_e_restituisci(x: i64) -> i64\n  effects: console\ndo\n  print(x)\n  return x\n"
        "end fn stampa_e_restituisci\n")
    fallisce(tmp_path, sorgente, "effetti", "console")


def test_lettura_fuori_dai_permessi(tmp_path):
    (tmp_path / "segreto.txt").write_text("no", encoding="utf-8")
    sorgente = ('module prova\n\nprocess main\n  effects: console, fs\n  grants: fs.read("pubblico")\ndo\n'
                '  match read_text("segreto.txt") do\n    case Ok(t):\n      print(t)\n    case Err(e):\n'
                '      print(e)\n  end match\nend process main\n')
    fallisce(tmp_path, sorgente, "sicurezza", "nessun permesso")


def test_sentinella_rifiuta_requisiti_non_verificabili(tmp_path):
    sorgente = "module prova\n\nprocess main\n  effects: console\n  platform: scudo_quantistico\ndo\n  print(1)\nend process main\n"
    fallisce(tmp_path, sorgente, "sicurezza", "non sa verificare")


def test_match_non_esaustivo(tmp_path):
    sorgente = ("module prova\n\ntype Colore do\n  case Rosso\n  case Verde\n  case Blu\nend type Colore\n\n"
                "fn nome(c: Colore) -> Str\n  effects: none\ndo\n  match c do\n    case Rosso:\n      return \"r\"\n"
                "    case Verde:\n      return \"v\"\n  end match\n  return \"?\"\nend fn nome\n")
    errori = errori_statici(tmp_path, sorgente)
    assert any("non esaustivo: manca Blu" in e.messaggio for e in errori)


def test_assegnazione_a_let(tmp_path):
    errori = errori_statici(tmp_path, main("let x = 1\nx = 2"))
    assert any(e.tipo == "proprieta" and "dichiarata con let" in e.messaggio for e in errori)


def test_punto_interrogativo_fuori_posto(tmp_path):
    errori = errori_statici(tmp_path, main('let n = "4".to_int()?'))
    assert any("? si usa solo" in e.messaggio for e in errori)


def test_nome_non_definito_con_suggerimento(tmp_path):
    errori = errori_statici(tmp_path, main("let totale = 1\nprint(totlae)"))
    assert any(e.tipo == "nome" and "totlae" in e.messaggio for e in errori)


def test_unsafe_fuori_da_kernel(tmp_path):
    fallisce(tmp_path, main("unsafe do\n  print(1)\nend unsafe"), "sicurezza", "kernel")


# ---------- compilatore ----------

@pytest.fixture(scope="module")
def numeri():
    risultato = compila_modulo(analizza_file(ESEMPI / "numbers.tsr"))
    return risultato, Esecutore(risultato), Interprete(Programma(ESEMPI / "numbers.tsr"), eco=False)


def test_compila_tutto_numeri(numeri):
    risultato, _, _ = numeri
    assert risultato.saltate == {}
    assert len(risultato.compilate) == 10


def test_salta_con_motivo():
    risultato = compila_modulo(analizza_file(ESEMPI / "prices.tsr"))
    assert risultato.compilate == []
    assert "Str" in risultato.saltate["parse_price"]


def esito(chiamata):
    try:
        return ("valore", chiamata())
    except ErroreTessera as e:
        return ("errore", e.tipo if e.tipo == "contratto" else "esecuzione")


GENERATORI = {
    "gcd": lambda r: (r.randint(-5, 10**6), r.randint(-5, 10**6)),
    "factorial": lambda r: (r.randint(-2, 25),),
    "fibonacci": lambda r: (r.randint(-1, 95),),
    "is_prime": lambda r: (r.randint(-10, 10**5),),
    "collatz_steps": lambda r: (r.randint(-3, 10**4),),
    "power": lambda r: (r.randint(-20, 20), r.randint(-1, 70)),
    "clamp": lambda r: (r.randint(-100, 100), r.randint(-50, 50), r.randint(-50, 50)),
    "add_small": lambda r: (r.choice([r.randint(-1000, 1000), 2**31 - 1, -(2**31)]), r.randint(-2, 2)),
    "mean": lambda r: (r.uniform(-1e6, 1e6), r.uniform(-1e6, 1e6)),
    "hypotenuse_squared": lambda r: (r.uniform(-1e3, 1e3), r.uniform(-1e3, 1e3)),
}


@pytest.mark.parametrize("funzione", sorted(GENERATORI))
def test_compilatore_e_interprete_coincidono(numeri, funzione):
    """Prova differenziale: stessi argomenti, stesso risultato o stesso tipo di errore."""
    _, wasm, interprete = numeri
    r = random.Random(funzione)
    for _ in range(150):
        argomenti = GENERATORI[funzione](r)
        atteso = esito(lambda: interprete.chiama_per_nome(funzione, list(argomenti)))
        ottenuto = esito(lambda: wasm.chiama(funzione, argomenti))
        if funzione == "add_small" and atteso[0] == "errore":
            # L'interprete scopre l'overflow i32 sul tipo di ritorno, il compilatore sull'operazione: entrambi falliscono.
            assert ottenuto[0] == "errore", argomenti
            continue
        assert ottenuto == atteso, (funzione, argomenti)


# ---------- esperimento della fase 1 ----------

def test_esperimento_soluzioni_di_riferimento():
    """Ogni esercizio deve avere soluzioni di riferimento che superano tutti i test, nei due linguaggi."""
    from experiment.__main__ import main as esperimento
    assert esperimento(["check"]) == 0


def test_esperimento_distingue_difetti_silenziosi():
    """Una somma senza controlli: in Python da' un risultato sbagliato, in Tessera ferma il programma."""
    from experiment import sandbox
    from experiment.__main__ import carica_compiti
    task = {t["id"]: t for t in carica_compiti()}["checked_sum"]
    python = "class Overflow(Exception):\n    pass\n\ndef checked_sum(values):\n    return sum(values)\n"
    tessera = ("module solution\n\npub type SumError do\n  case Overflow\nend type SumError\n\n"
               "pub fn checked_sum(values: List[i64]) -> Result[i64, SumError]\n  effects: none\ndo\n"
               "  var total = 0\n  for v in values do\n    total += v\n  end for\n  return Ok(total)\n"
               "end fn checked_sum\n")
    esiti_py = [r["outcome"] for r in sandbox.esegui("python", python, task, task["hidden"])["results"]]
    esiti_tsr = [r["outcome"] for r in sandbox.esegui("tessera", tessera, task, task["hidden"])["results"]]
    assert esiti_py.count("wrong") == 2 and "error" not in esiti_py
    assert esiti_tsr.count("error") == 2 and "wrong" not in esiti_tsr


def test_esperimento_codice_che_stampa():
    """Un candidato che stampa non deve rompere la lettura dei risultati (bug trovato con qwen2.5:3b)."""
    from experiment import sandbox
    from experiment.__main__ import carica_compiti
    task = {t["id"]: t for t in carica_compiti()}["word_count"]
    codice = 'print("debug")\ndef word_count(text):\n    print(text)\n    return len([p for p in text.split(" ") if p])\n'
    esito = sandbox.esegui("python", codice, task, task["visible"])
    assert [r["outcome"] for r in esito["results"]] == ["pass", "pass"]


# ---------- suggerimenti per gli errori tipici dei modelli (02/11/2026) ----------

ERRORI_TIPICI = [
    ("let mut x = 0", "var name = value"),
    ("if x > 0 then", "if condition do"),
    ("let m = i64::MAX", "no `::` paths"),
    ("for i in 1..=n do", "`1..n + 1`"),
    ("if a && b do", "`and`, `or`, `not`"),
    ("let y = x;", "No semicolons"),
    ("else do", "`else` alone"),
]


@pytest.mark.parametrize("riga, frammento", ERRORI_TIPICI)
def test_suggerimento_per_errore_tipico(riga, frammento):
    from tessera.parser import analizza
    sorgente = f"module prova\n\nfn f(x: i64, n: i64, a: bool, b: bool) -> i64\n  effects: none\ndo\n  {riga}\n  return x\nend fn f\n"
    with pytest.raises(ErroreTessera) as info:
        analizza(sorgente)
    assert info.value.suggerimento and frammento in info.value.suggerimento, info.value.suggerimento


def test_suggerimento_do_sulla_riga_della_firma():
    from tessera.parser import analizza
    with pytest.raises(ErroreTessera) as info:
        analizza("module prova\n\npub fn f(x: i64) -> i64 do\n  return x\nend fn f\n")
    assert "effects: none" in info.value.suggerimento


def test_result_e_un_nome_libero(tmp_path):
    sorgente = main("print(conta(\"abc\"))") + (
        "\nfn conta(text: Str) -> i64\n  effects: none\n  ensures: result >= 0\ndo\n  var result = 0\n"
        "  for c in text.chars() do\n    result += 1\n  end for\n  return result\nend fn conta\n")
    assert esegui(tmp_path, sorgente) == ["3"]
