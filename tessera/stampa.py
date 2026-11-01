"""Ristampa espressioni e tipi come codice Tessera, per i messaggi d'errore."""
from . import ast as A


def mostra_tipo(t):
    if t is None:
        return "()"
    if isinstance(t, A.TipoTupla):
        return "(" + ", ".join(mostra_tipo(x) for x in t.elementi) + ")"
    if isinstance(t, A.TipoFunzione):
        return "fn(" + ", ".join(mostra_tipo(x) for x in t.parametri) + ") -> " + mostra_tipo(t.ritorno)
    if t.argomenti:
        return t.nome + "[" + ", ".join(mostra_tipo(a) if isinstance(a, A.Nodo) else str(a) for a in t.argomenti) + "]"
    return t.nome


def mostra_schema(s):
    if isinstance(s, A.SchemaNome):
        return s.nome
    if isinstance(s, A.SchemaJolly):
        return "_"
    if isinstance(s, A.SchemaLetterale):
        return mostra(s.valore)
    if isinstance(s, A.SchemaTupla):
        return "(" + ", ".join(mostra_schema(x) for x in s.elementi) + ")"
    nome = f"{s.tipo}.{s.nome}" if s.tipo else s.nome
    return nome + ("(" + ", ".join(mostra_schema(x) for x in s.argomenti) + ")" if s.argomenti else "")


def mostra(e):
    if isinstance(e, A.Letterale):
        if e.tipo == "bool":
            return "true" if e.valore else "false"
        return repr(e.valore) if e.tipo == "float" else str(e.valore)
    if isinstance(e, A.Testo):
        return '"' + "".join(p if isinstance(p, str) else "{" + mostra(p) + "}" for p in e.parti) + '"'
    if isinstance(e, (A.Nome, A.NomeTipo)):
        return e.nome
    if isinstance(e, A.Risultato):
        return "result"
    if isinstance(e, (A.Binaria, A.Confronto)):
        return f"{mostra(e.sinistra)} {e.op} {mostra(e.destra)}"
    if isinstance(e, A.Logica):
        return f" {e.op} ".join(_tra_parentesi(x) for x in e.operandi)
    if isinstance(e, A.Non):
        return f"not {mostra(e.espressione)}"
    if isinstance(e, A.Implica):
        return f"{mostra(e.premessa)} implies {mostra(e.conseguenza)}"
    if isinstance(e, A.Negativo):
        return f"-{mostra(e.espressione)}"
    if isinstance(e, A.Intervallo):
        return f"{mostra(e.inizio)}..{mostra(e.fine)}"
    if isinstance(e, A.Chiamata):
        return mostra(e.funzione) + "(" + ", ".join(_argomento(a) for a in e.argomenti) + ")"
    if isinstance(e, A.Indice):
        return f"{mostra(e.oggetto)}[{mostra(e.indice)}]"
    if isinstance(e, (A.Campo, A.Variante)):
        return f"{mostra(e.oggetto)}.{e.nome}"
    if isinstance(e, A.Propaga):
        return mostra(e.espressione) + "?"
    if isinstance(e, A.Tupla):
        return "(" + ", ".join(mostra(x) for x in e.elementi) + ")"
    if isinstance(e, A.Lista):
        return "[" + ", ".join(mostra(x) for x in e.elementi) + "]"
    if isinstance(e, A.Lambda):
        return "fn(" + ", ".join(n for n, _ in e.parametri) + ") => " + mostra(e.corpo)
    if isinstance(e, A.ProvaSchema):
        return f"{mostra(e.espressione)} is {mostra_schema(e.schema)}"
    return "<espressione>"


def _tra_parentesi(e):
    testo = mostra(e)
    return f"({testo})" if isinstance(e, (A.Logica, A.Implica)) else testo


def _argomento(a):
    testo = mostra(a.valore)
    if a.modo:
        testo = f"{a.modo} {testo}"
    if a.nome:
        testo = f"{a.nome}: {testo}"
    return testo
