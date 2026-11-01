# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Albero sintattico astratto di Tessera.

Ogni nodo ricorda la riga del sorgente, per gli errori.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Nodo:
    riga: int = field(default=0, kw_only=True)


# ---------- tipi ----------

@dataclass
class TipoNominato(Nodo):
    nome: str                       # "i64", "Str", "Result", "Cents"
    argomenti: list                 # TipoNominato, int (dimensione fissa) o str (dimensione con nome)


@dataclass
class TipoFunzione(Nodo):
    parametri: list
    ritorno: object


@dataclass
class TipoTupla(Nodo):
    elementi: list


# ---------- espressioni ----------

@dataclass
class Letterale(Nodo):
    valore: object
    tipo: str                       # "int", "float", "bool", "quantita"


@dataclass
class Testo(Nodo):
    parti: list                     # str oppure espressioni da interpolare


@dataclass
class Nome(Nodo):
    nome: str


@dataclass
class NomeTipo(Nodo):
    nome: str


@dataclass
class Risultato(Nodo):
    pass


@dataclass
class Binaria(Nodo):
    op: str                         # + - * / % @
    sinistra: object
    destra: object


@dataclass
class Confronto(Nodo):
    op: str                         # == != < <= > >= in
    sinistra: object
    destra: object


@dataclass
class Logica(Nodo):
    op: str                         # and, or
    operandi: list


@dataclass
class Non(Nodo):
    espressione: object


@dataclass
class Implica(Nodo):
    premessa: object
    conseguenza: object


@dataclass
class Negativo(Nodo):
    espressione: object


@dataclass
class Intervallo(Nodo):
    inizio: object
    fine: object


@dataclass
class Argomento(Nodo):
    nome: Optional[str]             # argomento con nome: scope: ula
    modo: Optional[str]             # "edit", "take" o None
    valore: object


@dataclass
class Chiamata(Nodo):
    funzione: object
    argomenti: list


@dataclass
class Indice(Nodo):
    oggetto: object
    indice: object


@dataclass
class Campo(Nodo):
    oggetto: object
    nome: str


@dataclass
class Variante(Nodo):
    oggetto: object                 # ParseError.NotANumber
    nome: str


@dataclass
class Propaga(Nodo):
    espressione: object             # espressione?


@dataclass
class Tupla(Nodo):
    elementi: list


@dataclass
class Lista(Nodo):
    elementi: list


@dataclass
class Lambda(Nodo):
    parametri: list                 # (nome, tipo o None)
    corpo: object


@dataclass
class ProvaSchema(Nodo):
    espressione: object             # espressione is schema
    schema: object


# ---------- schemi (pattern) ----------

@dataclass
class SchemaNome(Nodo):
    nome: str


@dataclass
class SchemaJolly(Nodo):
    pass


@dataclass
class SchemaLetterale(Nodo):
    valore: object                  # Letterale o Testo senza interpolazioni


@dataclass
class SchemaVariante(Nodo):
    tipo: Optional[str]             # ParseError in ParseError.NotANumber
    nome: str
    argomenti: list


@dataclass
class SchemaTupla(Nodo):
    elementi: list


# ---------- istruzioni ----------

@dataclass
class Let(Nodo):
    schema: object
    tipo: object
    valore: object


@dataclass
class Var(Nodo):
    nome: str
    tipo: object
    valore: object


@dataclass
class Assegna(Nodo):
    bersaglio: object
    op: str                         # = += -= *= /=
    valore: object


@dataclass
class Espressione(Nodo):
    espressione: object


@dataclass
class Ritorna(Nodo):
    valore: object


@dataclass
class Interrompi(Nodo):
    pass


@dataclass
class Continua(Nodo):
    pass


@dataclass
class Se(Nodo):
    rami: list                      # (condizione, blocco)
    altrimenti: Optional[list]


@dataclass
class Per(Nodo):
    schema: object
    iterabile: object
    corpo: list


@dataclass
class Mentre(Nodo):
    condizione: object
    corpo: list


@dataclass
class Caso(Nodo):
    schema: object
    guardia: object
    corpo: list


@dataclass
class Scegli(Nodo):
    soggetto: object
    casi: list


@dataclass
class NonSicuro(Nodo):
    corpo: list


# ---------- dichiarazioni ----------

@dataclass
class Effetto(Nodo):
    nome: str                       # "net", "fs.read"
    argomenti: list                 # Argomento

    @property
    def base(self):
        return self.nome.split(".")[0]


@dataclass
class Parametro(Nodo):
    nome: str
    tipo: object
    modo: Optional[str]             # None (sola lettura), "edit", "take"
    partizione: Optional[str]       # batch @ data


@dataclass
class Funzione(Nodo):
    nome: str
    pubblica: bool
    critica: bool
    generici: list
    parametri: list
    ritorno: object
    doc: Optional[str]
    effetti: list                   # vuota = effects: none
    richiede: list
    garantisce: list
    esempi: list
    budget: list
    corpo: Optional[list]           # None per le funzioni esterne
    esterna: Optional[str] = None   # "c", "python", ...


@dataclass
class TipoAlias(Nodo):
    nome: str
    pubblico: bool
    generici: list
    tipo: object


@dataclass
class DichiarazioneVariante(Nodo):
    nome: str
    campi: list                     # (nome, tipo)


@dataclass
class TipoComposto(Nodo):
    nome: str
    pubblico: bool
    generici: list
    invarianti: list
    campi: list                     # (nome, tipo) per una struttura
    varianti: list                  # DichiarazioneVariante per un tipo somma


@dataclass
class Processo(Nodo):
    nome: str
    effetti: list
    permessi: list                  # Effetto
    limiti: list
    piattaforma: list
    corpo: list


@dataclass
class Costante(Nodo):
    nome: str
    pubblica: bool
    tipo: object
    valore: object


@dataclass
class Importa(Nodo):
    modulo: str
    nomi: list


@dataclass
class Modulo(Nodo):
    nome: str
    profilo: Optional[str]
    importazioni: list
    dichiarazioni: list
    file: Optional[str] = None
