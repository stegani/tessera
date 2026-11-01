# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Funzioni e metodi di base del prototipo.

Ogni funzione con un effetto lo dichiara: l'interprete lo controlla prima di eseguirla.
"""
import math

from . import values as V
from .errors import ErroreTessera


def errore(tipo, messaggio, nodo, suggerimento=None):
    return ErroreTessera(tipo, messaggio, riga=getattr(nodo, "riga", None), suggerimento=suggerimento)


class Nativa:
    """Funzione globale scritta in Python."""

    def __init__(self, nome, impl, effetto=None, arieta=None):
        self.nome = nome
        self.impl = impl
        self.effetto = effetto
        self.arieta = arieta

    def chiama(self, interprete, argomenti, nodo):
        if self.effetto:
            interprete.richiedi_effetto(self.effetto, nodo, self.nome)
        if self.arieta is not None and len(argomenti) != self.arieta:
            raise errore("tipo", f"{self.nome} vuole {self.arieta} argomenti, ne ha ricevuti {len(argomenti)}", nodo)
        return self.impl(interprete, *argomenti, nodo=nodo)


def stringa(v, nodo, chi):
    if not isinstance(v, str):
        raise errore("tipo", f"{chi} vuole Str, ha ricevuto {V.nome_tipo(v)}", nodo)
    return v


# ---------- funzioni globali ----------

def _print(interprete, valore, nodo):
    interprete.uscita(V.formatta(valore, nodo=nodo))
    return None


def _read_text(interprete, percorso, nodo):
    stringa(percorso, nodo, "read_text")
    interprete.controlla_permesso_file(percorso, nodo)
    try:
        with open(interprete.percorso(percorso), encoding="utf-8") as f:
            return V.ok(f.read())
    except OSError as e:
        return V.err(str(e.strerror or e))


def _confrontabili(a, b, nodo, chi):
    if not V.stessa_specie(a, b) or not isinstance(a, (int, float, str, V.NuovoTipo)) or isinstance(a, bool):
        raise errore("tipo", f"{chi} su {V.nome_tipo(a)} e {V.nome_tipo(b)}", nodo)
    return (a.valore, b.valore) if isinstance(a, V.NuovoTipo) else (a, b)


def _min(interprete, a, b, nodo):
    x, y = _confrontabili(a, b, nodo, "min")
    return a if x <= y else b


def _max(interprete, a, b, nodo):
    x, y = _confrontabili(a, b, nodo, "max")
    return a if x >= y else b


def _abs(interprete, a, nodo):
    if isinstance(a, bool) or not isinstance(a, (int, float)):
        raise errore("tipo", f"abs su {V.nome_tipo(a)}", nodo)
    return interprete.controlla_intero(abs(a), nodo) if isinstance(a, int) else abs(a)


def _from_code(interprete, n, nodo):
    if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= 0x10FFFF:
        raise errore("esecuzione", f"from_code vuole un codice di carattere tra 0 e 1114111, non {V.formatta(n, True)}", nodo)
    return chr(n)


GLOBALI = {
    "print": Nativa("print", _print, effetto="console", arieta=1),
    "from_code": Nativa("from_code", _from_code, arieta=1),
    "read_text": Nativa("read_text", _read_text, effetto="fs", arieta=1),
    "min": Nativa("min", _min, arieta=2),
    "max": Nativa("max", _max, arieta=2),
    "abs": Nativa("abs", _abs, arieta=1),
}


# ---------- metodi ----------
# Firma: (interprete, ricevente, argomenti, nodo). I metodi "mutanti" modificano il ricevente.

def _to_int_da_str(i, s, a, n):
    t = s.strip()
    if t.isascii() and (t.isdigit() or (t[:1] in ("+", "-") and t[1:].isdigit())):
        valore = int(t)
        if not V.MIN_I64 <= valore <= V.MAX_I64:
            return V.err(f"'{s}' non sta in un intero a 64 bit")
        return V.ok(valore)
    return V.err(f"'{s}' non e' un intero")


def _to_float_da_str(i, s, a, n):
    try:
        return V.ok(float(s))
    except ValueError:
        return V.err(f"'{s}' non e' un decimale")


def _split_once(i, s, a, n):
    separatore = stringa(a[0], n, "split_once")
    prima, _, dopo = s.partition(separatore)
    return (prima, dopo)


def _join(i, lista, a, n):
    separatore = stringa(a[0], n, "join")
    for x in lista:
        stringa(x, n, "join")
    return separatore.join(lista)


def _sum(i, lista, a, n):
    if not lista:
        raise errore("esecuzione", "sum() su una lista vuota: il tipo del risultato non e' noto", n,
                     suggerimento="controlla is_empty() prima")
    totale = lista[0]
    for x in lista[1:]:
        totale = i.aritmetica("+", totale, x, n)
    return totale


def _get(i, lista, a, n):
    k = a[0]
    if isinstance(k, bool) or not isinstance(k, int):
        raise errore("tipo", f"l'indice deve essere intero, non {V.nome_tipo(k)}", n)
    return V.qualcosa(lista[k]) if 0 <= k < len(lista) else V.nessuno()


def _ordinata(i, lista, a, n):
    for x, y in zip(lista, lista[1:]):
        _confrontabili(x, y, n, "sorted")
    return sorted(lista, key=lambda v: v.valore if isinstance(v, V.NuovoTipo) else v)


def _validate(i, nf, a, n):
    esito = i.chiama_valore(a[0], [nf.valore], n)
    if not isinstance(esito, bool):
        raise errore("tipo", "il predicato di validate deve restituire bool", n)
    return V.ok(nf.valore) if esito else V.err("validazione fallita")


def _unwrap_or(i, v, a, n):
    if v.nome in ("Some", "Ok"):
        return v.valori[0]
    return a[0]


def _intervallo(i, valori, a, n, chi):
    inizio, fine = a
    for x in (inizio, fine):
        if isinstance(x, bool) or not isinstance(x, int):
            raise errore("tipo", f"{chi} vuole indici interi, non {V.nome_tipo(x)}", n)
    if not 0 <= inizio <= fine <= len(valori):
        raise errore("esecuzione", f"{chi}({inizio}, {fine}) fuori dai limiti (lunghezza {len(valori)})", n)
    return valori[inizio:fine]


def _codice(i, s, a, n):
    if len(s) != 1:
        raise errore("esecuzione", f"code() vuole un solo carattere, non {len(s)}", n)
    return ord(s)


def _radice(x, n):
    if x < 0:
        raise errore("esecuzione", "radice quadrata di un numero negativo", n)
    return math.sqrt(x)


def _to_int_da_float(i, x, a, n):
    if math.isnan(x) or math.isinf(x):
        raise errore("esecuzione", f"{x} non si converte in intero", n)
    return i.controlla_intero(int(x), n)


METODI = {
    "Str": {
        "len": (0, lambda i, s, a, n: len(s)),
        "upper": (0, lambda i, s, a, n: s.upper()),
        "lower": (0, lambda i, s, a, n: s.lower()),
        "trim": (0, lambda i, s, a, n: s.strip()),
        "is_empty": (0, lambda i, s, a, n: len(s) == 0),
        "is_digits": (0, lambda i, s, a, n: len(s) > 0 and s.isascii() and s.isdigit()),
        "contains": (1, lambda i, s, a, n: stringa(a[0], n, "contains") in s),
        "starts_with": (1, lambda i, s, a, n: s.startswith(stringa(a[0], n, "starts_with"))),
        "ends_with": (1, lambda i, s, a, n: s.endswith(stringa(a[0], n, "ends_with"))),
        "replace": (2, lambda i, s, a, n: s.replace(stringa(a[0], n, "replace"), stringa(a[1], n, "replace"))),
        "split": (1, lambda i, s, a, n: s.split(stringa(a[0], n, "split"))),
        "split_once": (1, _split_once),
        "chars": (0, lambda i, s, a, n: list(s)),
        "slice": (2, lambda i, s, a, n: _intervallo(i, s, a, n, "slice")),
        "code": (0, _codice),
        "to_int": (0, _to_int_da_str),
        "to_float": (0, _to_float_da_str),
        "to_str": (0, lambda i, s, a, n: s),
    },
    "List": {
        "len": (0, lambda i, l, a, n: len(l)),
        "is_empty": (0, lambda i, l, a, n: len(l) == 0),
        "get": (1, _get),
        "first": (0, lambda i, l, a, n: V.qualcosa(l[0]) if l else V.nessuno()),
        "last": (0, lambda i, l, a, n: V.qualcosa(l[-1]) if l else V.nessuno()),
        "contains": (1, lambda i, l, a, n: any(V.uguali(x, a[0], n) for x in l)),
        "map": (1, lambda i, l, a, n: [i.chiama_valore(a[0], [x], n) for x in l]),
        "filter": (1, lambda i, l, a, n: [x for x in l if i.chiama_valore(a[0], [x], n) is True]),
        "sum": (0, _sum),
        "reversed": (0, lambda i, l, a, n: list(reversed(l))),
        "slice": (2, lambda i, l, a, n: [V.copia(x) for x in _intervallo(i, l, a, n, "slice")]),
        "sorted": (0, _ordinata),
        "join": (1, _join),
        "to_str": (0, lambda i, l, a, n: V.formatta(l, nodo=n)),
    },
    "intero": {
        "to_f64": (0, lambda i, x, a, n: float(x)),
        "to_str": (0, lambda i, x, a, n: str(x)),
        "abs": (0, lambda i, x, a, n: i.controlla_intero(abs(x), n)),
    },
    "f64": {
        "to_int": (0, _to_int_da_float),
        "to_str": (0, lambda i, x, a, n: repr(x)),
        "abs": (0, lambda i, x, a, n: abs(x)),
        "floor": (0, lambda i, x, a, n: float(math.floor(x))),
        "round": (0, lambda i, x, a, n: float(round(x))),
        "sqrt": (0, lambda i, x, a, n: _radice(x, n)),
    },
    "bool": {"to_str": (0, lambda i, x, a, n: "true" if x else "false")},
    "Option": {
        "is_some": (0, lambda i, v, a, n: v.nome == "Some"),
        "is_none": (0, lambda i, v, a, n: v.nome == "None"),
        "unwrap_or": (1, _unwrap_or),
    },
    "Result": {
        "is_ok": (0, lambda i, v, a, n: v.nome == "Ok"),
        "is_err": (0, lambda i, v, a, n: v.nome == "Err"),
        "unwrap_or": (1, _unwrap_or),
    },
    "Untrusted": {"validate": (1, _validate)},
}

# Metodi che modificano il ricevente: richiedono una variabile modificabile (var o edit).
METODI_MUTANTI = {
    "List": {
        "push": (1, lambda i, l, a, n: l.append(V.copia(a[0]))),
        "pop": (0, lambda i, l, a, n: V.qualcosa(l.pop()) if l else V.nessuno()),
        "clear": (0, lambda i, l, a, n: l.clear()),
    },
}


def specie_metodo(v):
    nome = V.nome_tipo(v)
    if isinstance(v, V.ValoreVariante) and v.tipo in ("Option", "Result"):
        return v.tipo
    return nome
