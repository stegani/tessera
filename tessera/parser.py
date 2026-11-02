# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Dal testo .tsr all'AST: parser LALR(1) generato da spec/tessera.lark."""
from functools import lru_cache
from pathlib import Path

from lark import Lark, Token, Transformer, v_args
from lark.exceptions import UnexpectedInput, VisitError

from . import ast as A
from .errors import ErroreTessera
from .hints import suggerimento

GRAMMATICA = Path(__file__).resolve().parent.parent / "spec" / "tessera.lark"

# Nomi leggibili per i simboli che il parser si aspettava. In inglese: li legge soprattutto un modello.
SIMBOLI = {
    "_NL": "end of line", "LPAR": "(", "RPAR": ")", "LSQB": "[", "RSQB": "]", "COLON": ":",
    "COMMA": ",", "DOT": ".", "EQUAL": "=", "MINUS": "-", "QMARK": "?", "AT": "@",
    "NAME": "name", "TYPE_NAME": "type name", "INT": "integer", "FLOAT": "decimal",
    "STRING": "string", "QUANTITY": "quantity", "ADD_OP": "+ or -", "MUL_OP": "* / % @",
    "COMP_OP": "comparison", "ASSIGN_OP": "assignment", "MODE": "edit or take",
    "PRIMITIVE": "primitive type", "PUB": "pub", "CRITICAL": "critical", "NONE": "none",
}
ESCAPE = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "{": "{", "}": "}"}


@lru_cache(maxsize=1)
def parser():
    return Lark(
        GRAMMATICA.read_text(encoding="utf-8"),
        parser="lalr",
        lexer="contextual",
        propagate_positions=True,
        maybe_placeholders=True,
        start=["start", "expr_only"],
    )


def simbolo(nome):
    return SIMBOLI.get(nome, nome.lower())


def errore_di_sintassi(err, file, testo=""):
    trovato = getattr(err, "token", None)
    if trovato is None and getattr(err, "char", None):
        trovato_testo = err.char                        # errore del lessico: un carattere che Tessera non usa
    else:
        trovato_testo = str(trovato) if trovato is not None else "?"
    attesi = sorted({simbolo(n) for n in (getattr(err, "expected", None) or getattr(err, "allowed", None) or [])})
    fine_riga = trovato is not None and getattr(trovato, "type", "") == "_NL"
    righe = testo.splitlines()
    testo_riga = righe[err.line - 1] if testo and 0 < (err.line or 0) <= len(righe) else ""
    return ErroreTessera(
        "sintassi",
        f"unexpected {'end of line' if fine_riga else repr(trovato_testo)}, expected one of: {', '.join(attesi[:10])}",
        riga=err.line, colonna=err.column, file=file,
        suggerimento=suggerimento(testo_riga, "" if fine_riga else trovato_testo, attesi),
    )


def analizza(testo, file=None):
    """Restituisce un ast.Modulo o solleva ErroreTessera."""
    if not testo.endswith("\n"):
        testo += "\n"
    try:
        albero = parser().parse(testo, start="start")
    except UnexpectedInput as err:
        raise errore_di_sintassi(err, file, testo) from None
    try:
        modulo = CostruisciAST(file).transform(albero)
    except VisitError as err:
        if isinstance(err.orig_exc, ErroreTessera):
            err.orig_exc.file = err.orig_exc.file or file
            raise err.orig_exc from None
        raise
    modulo.file = file
    return modulo


def analizza_file(percorso):
    percorso = Path(percorso)
    return analizza(percorso.read_text(encoding="utf-8"), file=str(percorso))


def riga(meta):
    return getattr(meta, "line", 0) or 0


def nome(token):
    return str(token) if token is not None else None


@v_args(meta=True)
class CostruisciAST(Transformer):
    def __init__(self, file=None):
        super().__init__()
        self.file = file

    # ---------- stringhe ----------

    def stringa_semplice(self, token):
        """Stringa senza interpolazione (doc, extern, schemi)."""
        parti = self.stringa(token, interpola=False)
        return "".join(parti)

    def stringa(self, token, interpola=True):
        corpo, parti, buffer, i = str(token)[1:-1], [], [], 0
        while i < len(corpo):
            c = corpo[i]
            if c == "\\":
                seguente = corpo[i + 1]
                if seguente not in ESCAPE:
                    raise ErroreTessera("sintassi", f"unknown escape sequence: \\{seguente}", riga=token.line, file=self.file)
                buffer.append(ESCAPE[seguente])
                i += 2
            elif c == "{" and interpola:
                fine = corpo.find("}", i)
                if fine < 0:
                    raise ErroreTessera("sintassi", "'{' without '}' in the string", riga=token.line, file=self.file,
                                        suggerimento="for a literal brace write \\{")
                if buffer:
                    parti.append("".join(buffer))
                    buffer = []
                parti.append(self.espressione_interna(corpo[i + 1:fine], token.line))
                i = fine + 1
            elif c == "}" and interpola:
                raise ErroreTessera("sintassi", "'}' without '{' in the string", riga=token.line, file=self.file,
                                    suggerimento="for a literal brace write \\}")
            else:
                buffer.append(c)
                i += 1
        if buffer or not parti:
            parti.append("".join(buffer))
        return parti

    def espressione_interna(self, testo, riga_stringa):
        try:
            albero = parser().parse(testo.strip(), start="expr_only")
        except UnexpectedInput as err:
            e = errore_di_sintassi(err, self.file)
            e.riga = riga_stringa
            e.messaggio = f"in the interpolation {{{testo}}}: {e.messaggio}"
            raise e from None
        espressione = CostruisciAST(self.file).transform(albero)
        _imposta_riga(espressione, riga_stringa)
        return espressione

    # ---------- modulo ----------

    def start(self, meta, c):
        nome_modulo, profilo = c[0]
        importazioni = [x for x in c[1:] if isinstance(x, A.Importa)]
        dichiarazioni = [x for x in c[1:] if not isinstance(x, A.Importa)]
        return A.Modulo(nome_modulo, profilo, importazioni, dichiarazioni, riga=riga(meta))

    def expr_only(self, meta, c):
        return c[0]

    def module_decl(self, meta, c):
        return (c[0], c[1])

    def profile_clause(self, meta, c):
        return str(c[0])

    def path(self, meta, c):
        return ".".join(str(t) for t in c)

    def import_decl(self, meta, c):
        return A.Importa(c[0], c[1], riga=riga(meta))

    def name_list(self, meta, c):
        return [str(t) for t in c]

    def const_decl(self, meta, c):
        pub, n, tipo, valore = c
        return A.Costante(str(n), pub is not None, tipo, valore, riga=riga(meta))

    # ---------- funzioni ----------

    def controlla_chiusura(self, tipo, apertura, chiusura):
        if str(apertura) != str(chiusura):
            raise ErroreTessera("sintassi", f"{tipo} '{apertura}' is closed with 'end {tipo} {chiusura}'",
                                riga=chiusura.line, file=self.file, suggerimento=f"write 'end {tipo} {apertura}'")

    def fn_decl(self, meta, c):
        pub, critica, n, generici, parametri, ritorno, clausole, corpo, chiusura = c
        self.controlla_chiusura("fn", n, chiusura)
        return A.Funzione(
            str(n), pub is not None, critica is not None, generici or [], parametri or [], ritorno,
            clausole.get("doc"), clausole["effects"], clausole.get("requires", []), clausole.get("ensures", []),
            clausole.get("example", []), clausole.get("budget", []), corpo, riga=riga(meta),
        )

    def extern_decl(self, meta, c):
        lingua, n, parametri, ritorno, *clausole = c
        d = self.raccogli_clausole(clausole)
        return A.Funzione(
            str(n), False, False, [], parametri or [], ritorno, None, d["effects"], d.get("requires", []),
            d.get("ensures", []), [], [], None, esterna=self.stringa_semplice(lingua), riga=riga(meta),
        )

    def return_type(self, meta, c):
        return c[0]

    def generic_params(self, meta, c):
        return c

    def generic_param(self, meta, c):
        return str(c[0])

    def params(self, meta, c):
        return [p for p in c if isinstance(p, A.Parametro)]

    def param(self, meta, c):
        modo, n, tipo, partizione = c
        return A.Parametro(str(n), tipo, nome(modo), partizione, riga=riga(meta))

    def shard(self, meta, c):
        return str(c[0])

    @staticmethod
    def raccogli_clausole(clausole):
        dati = {}
        for clausola in clausole:
            if clausola is None:
                continue
            chiave, valore = clausola
            if chiave in ("requires", "ensures", "example", "invariant"):
                dati.setdefault(chiave, []).append(valore)
            else:
                dati[chiave] = valore
        return dati

    def fn_clauses(self, meta, c):
        return self.raccogli_clausole(c)

    def doc_clause(self, meta, c):
        return ("doc", self.stringa_semplice(c[0]))

    def effects_clause(self, meta, c):
        if len(c) == 1 and isinstance(c[0], Token) and c[0].type == "NONE":
            return ("effects", [])
        return ("effects", c)

    def effect(self, meta, c):
        *parti, argomenti = c
        return A.Effetto(".".join(str(t) for t in parti), argomenti or [], riga=riga(meta))

    def requires_clause(self, meta, c):
        return ("requires", c[0])

    def ensures_clause(self, meta, c):
        return ("ensures", c[0])

    def example_clause(self, meta, c):
        return ("example", c[0])

    def budget_clause(self, meta, c):
        return ("budget", c)

    def quantity(self, meta, c):
        valore = self.letterale_numerico(c[1])
        return (str(c[0]), valore, str(c[2]) if len(c) > 2 else None)

    # ---------- tipi ----------

    def named_type(self, meta, c):
        argomenti = []
        for a in c[1] or []:
            if isinstance(a, Token):
                argomenti.append(int(str(a).replace("_", "")) if a.type == "INT" else str(a))
            else:
                argomenti.append(a)
        return A.TipoNominato(str(c[0]), argomenti, riga=riga(meta))

    def type_args(self, meta, c):
        return c

    def fn_type(self, meta, c):
        return A.TipoFunzione(c[:-1], c[-1], riga=riga(meta))

    def tuple_type(self, meta, c):
        return A.TipoTupla(c, riga=riga(meta))

    def type_alias(self, meta, c):
        pub, n, generici, tipo = c
        return A.TipoAlias(str(n), pub is not None, generici or [], tipo, riga=riga(meta))

    def type_decl(self, meta, c):
        pub, n, generici, *resto, chiusura = c
        self.controlla_chiusura("type", n, chiusura)
        invarianti = [v for k, v in (x for x in resto if x[0] == "invariant")]
        campi = [(x[1], x[2]) for x in resto if x[0] == "campo"]
        varianti = [x[1] for x in resto if x[0] == "variante"]
        if campi and varianti:
            raise ErroreTessera("sintassi", f"type {n} mixes fields and variants", riga=riga(meta), file=self.file,
                                suggerimento="a struct has only fields, a sum type only 'case' variants")
        return A.TipoComposto(str(n), pub is not None, generici or [], invarianti, campi, varianti, riga=riga(meta))

    def invariant_clause(self, meta, c):
        return ("invariant", c[0])

    def field_decl(self, meta, c):
        return ("campo", str(c[0]), c[1])

    def variant_decl(self, meta, c):
        return ("variante", A.DichiarazioneVariante(str(c[0]), c[1] or [], riga=riga(meta)))

    def fields(self, meta, c):
        return c

    def field(self, meta, c):
        # Usato sia per i campi delle varianti (NAME ":" type) sia per l'accesso (postfix "." NAME).
        if len(c) == 2 and isinstance(c[0], Token) and c[0].type == "NAME" and not isinstance(c[1], Token):
            return (str(c[0]), c[1])
        return A.Campo(c[0], str(c[1]), riga=riga(meta))

    # ---------- processi ----------

    def process_decl(self, meta, c):
        n, (_, effetti), *clausole, corpo, chiusura = c
        self.controlla_chiusura("process", n, chiusura)
        d = dict(x for x in clausole if x is not None)
        return A.Processo(str(n), effetti, d.get("grants", []), d.get("limits", []), d.get("platform", []), corpo,
                          riga=riga(meta))

    def grants_clause(self, meta, c):
        return ("grants", c)

    def grant(self, meta, c):
        *parti, argomenti = c
        return A.Effetto(".".join(str(t) for t in parti), argomenti or [], riga=riga(meta))

    def limits_clause(self, meta, c):
        return ("limits", c)

    def platform_clause(self, meta, c):
        return ("platform", [str(t) for t in c])

    # ---------- istruzioni ----------

    def block(self, meta, c):
        return list(c)

    def let_stmt(self, meta, c):
        return A.Let(c[0], c[1], c[2], riga=riga(meta))

    def var_stmt(self, meta, c):
        return A.Var(str(c[0]), c[1], c[2], riga=riga(meta))

    def return_stmt(self, meta, c):
        return A.Ritorna(c[0], riga=riga(meta))

    def break_stmt(self, meta, c):
        return A.Interrompi(riga=riga(meta))

    def continue_stmt(self, meta, c):
        return A.Continua(riga=riga(meta))

    def simple_stmt(self, meta, c):
        espressione, op, valore = c
        if op is None:
            return A.Espressione(espressione, riga=riga(meta))
        if not isinstance(espressione, (A.Nome, A.Campo, A.Indice)):
            raise ErroreTessera("sintassi", "you can only assign to a variable, a field or a list element",
                                riga=riga(meta), file=self.file)
        return A.Assegna(espressione, str(op), valore, riga=riga(meta))

    def if_stmt(self, meta, c):
        condizione, blocco, *altri = c
        altrimenti = altri.pop() if altri and (altri[-1] is None or altri[-1][0] == "else") else None
        rami = [(condizione, blocco)] + [(x[1], x[2]) for x in altri]
        return A.Se(rami, altrimenti[1] if altrimenti else None, riga=riga(meta))

    def elif_part(self, meta, c):
        return ("elif", c[0], c[1])

    def else_part(self, meta, c):
        return ("else", c[0])

    def for_stmt(self, meta, c):
        return A.Per(c[0], c[1], c[2], riga=riga(meta))

    def while_stmt(self, meta, c):
        return A.Mentre(c[0], c[1], riga=riga(meta))

    def match_stmt(self, meta, c):
        return A.Scegli(c[0], c[1:], riga=riga(meta))

    def case_arm(self, meta, c):
        return A.Caso(c[0], c[1], c[2], riga=riga(meta))

    def unsafe_stmt(self, meta, c):
        return A.NonSicuro(c[0], riga=riga(meta))

    # ---------- schemi ----------

    def bind_pattern(self, meta, c):
        n = str(c[0])
        return A.SchemaJolly(riga=riga(meta)) if n == "_" else A.SchemaNome(n, riga=riga(meta))

    def wildcard_pattern(self, meta, c):
        return A.SchemaJolly(riga=riga(meta))

    def literal_pattern(self, meta, c):
        valore = c[0]
        if isinstance(valore, A.Testo) and any(not isinstance(p, str) for p in valore.parti):
            raise ErroreTessera("sintassi", "a pattern cannot contain interpolations", riga=riga(meta), file=self.file)
        return A.SchemaLetterale(valore, riga=riga(meta))

    def variant_pattern(self, meta, c):
        nomi = [t for t in c if isinstance(t, Token)]
        argomenti = [x for x in c if not isinstance(x, Token)]
        if len(nomi) == 2:
            return A.SchemaVariante(str(nomi[0]), str(nomi[1]), argomenti, riga=riga(meta))
        return A.SchemaVariante(None, str(nomi[0]), argomenti, riga=riga(meta))

    def tuple_pattern(self, meta, c):
        return A.SchemaTupla(c, riga=riga(meta))

    # ---------- espressioni ----------

    def letterale_numerico(self, token):
        testo = str(token).replace("_", "")
        if token.type == "INT":
            return int(testo)
        if token.type == "FLOAT":
            return float(testo)
        for unita, fattore in (("KB", 1024), ("MB", 1024**2), ("GB", 1024**3), ("TB", 1024**4), ("ms", 1), ("s", 1000)):
            if testo.endswith(unita):
                return int(testo[: -len(unita)]) * fattore
        raise ErroreTessera("sintassi", f"invalid quantity: {token}", riga=token.line, file=self.file)

    def literal(self, meta, c):
        token = c[0]
        if token.type == "STRING":
            return A.Testo(self.stringa(token), riga=riga(meta))
        tipo = {"INT": "int", "FLOAT": "float", "QUANTITY": "quantita"}[token.type]
        return A.Letterale(self.letterale_numerico(token), tipo, riga=riga(meta))

    def true(self, meta, c):
        return A.Letterale(True, "bool", riga=riga(meta))

    def false(self, meta, c):
        return A.Letterale(False, "bool", riga=riga(meta))

    def var(self, meta, c):
        return A.Nome(str(c[0]), riga=riga(meta))

    def type_ref(self, meta, c):
        return A.NomeTipo(str(c[0]), riga=riga(meta))

    def result_ref(self, meta, c):
        return A.Risultato(riga=riga(meta))

    def tuple(self, meta, c):
        return A.Tupla(c, riga=riga(meta))

    def list(self, meta, c):
        return A.Lista(c, riga=riga(meta))

    def lambda_(self, meta, c):
        return A.Lambda(c[:-1], c[-1], riga=riga(meta))

    def lambda_param(self, meta, c):
        return (str(c[0]), c[1])

    def implies_expr(self, meta, c):
        return A.Implica(c[0], c[1], riga=riga(meta))

    def and_chain(self, meta, c):
        return self.catena("and", c, meta)

    def or_chain(self, meta, c):
        return self.catena("or", c, meta)

    @staticmethod
    def catena(op, c, meta):
        # La grammatica e' ricorsiva a sinistra: (a and b) and c diventa un'unica catena a, b, c.
        operandi = []
        for x in c:
            if isinstance(x, A.Logica) and x.op == op:
                operandi.extend(x.operandi)
            else:
                operandi.append(x)
        return A.Logica(op, operandi, riga=riga(meta))

    def not_op(self, meta, c):
        return A.Non(c[0], riga=riga(meta))

    def comparison(self, meta, c):
        return A.Confronto(str(c[1]), c[0], c[2], riga=riga(meta))

    def is_test(self, meta, c):
        return A.ProvaSchema(c[0], c[1], riga=riga(meta))

    def range_expr(self, meta, c):
        return A.Intervallo(c[0], c[1], riga=riga(meta))

    def binop(self, meta, c):
        return A.Binaria(str(c[1]), c[0], c[2], riga=riga(meta))

    def neg(self, meta, c):
        return A.Negativo(c[0], riga=riga(meta))

    def call(self, meta, c):
        return A.Chiamata(c[0], c[1], riga=riga(meta))

    def call_args(self, meta, c):
        return [a for a in c if isinstance(a, A.Argomento)]

    def arg(self, meta, c):
        n, modo, valore = c
        return A.Argomento(nome(n), nome(modo), valore, riga=riga(meta))

    def index(self, meta, c):
        return A.Indice(c[0], c[1], riga=riga(meta))

    def variant_ref(self, meta, c):
        return A.Variante(c[0], str(c[1]), riga=riga(meta))

    def try_op(self, meta, c):
        return A.Propaga(c[0], riga=riga(meta))


# Lark chiama il metodo "lambda": e' una parola riservata di Python, quindi lo colleghiamo a mano.
setattr(CostruisciAST, "lambda", CostruisciAST.lambda_)


def _imposta_riga(nodo, valore):
    """Le espressioni interpolate prendono la riga della stringa che le contiene."""
    if isinstance(nodo, A.Nodo):
        nodo.riga = valore
        for figlio in vars(nodo).values():
            if isinstance(figlio, list):
                for x in figlio:
                    _imposta_riga(x, valore)
            else:
                _imposta_riga(figlio, valore)
