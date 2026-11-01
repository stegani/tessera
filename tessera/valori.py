"""Valori a runtime dell'interprete, uguaglianza strutturale e stampa."""
from dataclasses import dataclass, field

from .errori import ErroreTessera

MIN_I64, MAX_I64 = -(2**63), 2**63 - 1
LIMITI_INTERI = {
    "i8": (-(2**7), 2**7 - 1), "i16": (-(2**15), 2**15 - 1), "i32": (-(2**31), 2**31 - 1), "i64": (MIN_I64, MAX_I64),
    "u8": (0, 2**8 - 1), "u16": (0, 2**16 - 1), "u32": (0, 2**32 - 1), "u64": (0, 2**64 - 1),
}
DECIMALI = {"f16", "bf16", "f32", "f64", "fp8"}


@dataclass
class Struttura:
    tipo: str
    campi: dict


@dataclass
class ValoreVariante:
    tipo: str                       # "Result", "Option" o un tipo somma dell'utente
    nome: str                       # "Ok", "None", "TooManyDecimals"
    valori: list
    nomi_campi: list = field(default_factory=list)


@dataclass
class NuovoTipo:
    tipo: str                       # type Cents = i64
    valore: object


@dataclass
class Segreto:
    valore: object

    def __repr__(self):
        return "Secret(***)"


@dataclass
class NonFidato:
    valore: object


@dataclass
class Intervallo:
    inizio: int
    fine: int


def nessuno():
    return ValoreVariante("Option", "None", [])


def qualcosa(v):
    return ValoreVariante("Option", "Some", [v])


def ok(v):
    return ValoreVariante("Result", "Ok", [v])


def err(v):
    return ValoreVariante("Result", "Err", [v])


def nome_tipo(v):
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "intero"
    if isinstance(v, float):
        return "f64"
    if isinstance(v, str):
        return "Str"
    if isinstance(v, list):
        return "List"
    if isinstance(v, tuple):
        return "tupla"
    if isinstance(v, (Struttura, ValoreVariante, NuovoTipo)):
        return v.tipo
    if isinstance(v, Segreto):
        return "Secret"
    if isinstance(v, NonFidato):
        return "Untrusted"
    if isinstance(v, Intervallo):
        return "intervallo"
    if callable(getattr(v, "chiama", None)):
        return "funzione"
    return type(v).__name__


def stessa_specie(a, b):
    """Interi e decimali, bool e interi non si mescolano mai."""
    return nome_tipo(a) == nome_tipo(b)


def uguali(a, b, nodo=None):
    if not stessa_specie(a, b):
        raise ErroreTessera("tipo", f"confronto tra {nome_tipo(a)} e {nome_tipo(b)}", riga=getattr(nodo, "riga", None),
                            suggerimento="converti esplicitamente uno dei due valori")
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(uguali(x, y, nodo) for x, y in zip(a, b))
    if isinstance(a, Struttura):
        return a.campi.keys() == b.campi.keys() and all(uguali(a.campi[k], b.campi[k], nodo) for k in a.campi)
    if isinstance(a, ValoreVariante):
        return a.nome == b.nome and len(a.valori) == len(b.valori) and all(
            uguali(x, y, nodo) for x, y in zip(a.valori, b.valori))
    if isinstance(a, (NuovoTipo, Segreto, NonFidato)):
        return uguali(a.valore, b.valore, nodo)
    return a == b


def copia(v):
    """Semantica dei valori: chi riceve una copia non vede le modifiche dell'originale."""
    if isinstance(v, list):
        return [copia(x) for x in v]
    if isinstance(v, tuple):
        return tuple(copia(x) for x in v)
    if isinstance(v, Struttura):
        return Struttura(v.tipo, {k: copia(x) for k, x in v.campi.items()})
    if isinstance(v, ValoreVariante):
        return ValoreVariante(v.tipo, v.nome, [copia(x) for x in v.valori], list(v.nomi_campi))
    if isinstance(v, NuovoTipo):
        return NuovoTipo(v.tipo, copia(v.valore))
    return v


def formatta(v, dentro=False, nodo=None):
    """Testo di un valore. Un Secret non si formatta mai."""
    if isinstance(v, Segreto):
        raise ErroreTessera("sicurezza", "un Secret non si puo' stampare ne' interpolare", riga=getattr(nodo, "riga", None))
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return '"' + v.replace('"', '\\"') + '"' if dentro else v
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(formatta(x, True, nodo) for x in v) + "]"
    if isinstance(v, tuple):
        return "(" + ", ".join(formatta(x, True, nodo) for x in v) + ")"
    if isinstance(v, Struttura):
        return v.tipo + "(" + ", ".join(f"{k}: {formatta(x, True, nodo)}" for k, x in v.campi.items()) + ")"
    if isinstance(v, ValoreVariante):
        if not v.valori:
            return v.nome
        if v.nomi_campi:
            interni = ", ".join(f"{k}: {formatta(x, True, nodo)}" for k, x in zip(v.nomi_campi, v.valori))
        else:
            interni = ", ".join(formatta(x, True, nodo) for x in v.valori)
        return f"{v.nome}({interni})"
    if isinstance(v, NuovoTipo):
        return f"{v.tipo}({formatta(v.valore, True, nodo)})"
    if isinstance(v, NonFidato):
        return f"Untrusted({formatta(v.valore, True, nodo)})"
    if isinstance(v, Intervallo):
        return f"{v.inizio}..{v.fine}"
    if v is None:
        return "()"
    return f"<{nome_tipo(v)}>"
