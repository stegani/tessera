# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Compilatore da Tessera a WebAssembly (testo WAT), versione 0.1.

Compila le funzioni pure (effects: none) su i32, i64, f64 e bool: variabili, if, while, for su intervalli,
chiamate, contratti. Ogni operazione intera controlla l'overflow; requires ed ensures diventano controlli
a runtime. Il resto del linguaggio non e' ancora supportato: la funzione viene saltata con il motivo.
"""
from dataclasses import dataclass, field

from . import ast as A
from .errors import ErroreTessera
from .printer import mostra

TIPI = {"i32": "i32", "i64": "i64", "f64": "f64", "bool": "i32"}

# Codici passati a env.fallisci prima di fermare l'esecuzione.
CODICI = {
    1: ("esecuzione", "overflow: il risultato non sta nel tipo intero"),
    2: ("contratto", "requires violata"),
    3: ("contratto", "ensures violata"),
    4: ("esecuzione", "divisione per zero"),
    5: ("tipo", "la funzione termina senza return"),
    6: ("esecuzione", "conversione da decimale a intero impossibile"),
}

AIUTANTI = """
  (func $add_i64 (param $a i64) (param $b i64) (result i64) (local $r i64)
    (local.set $r (i64.add (local.get $a) (local.get $b)))
    (if (i64.lt_s (i64.and (i64.xor (local.get $a) (local.get $r)) (i64.xor (local.get $b) (local.get $r))) (i64.const 0))
      (then (call $fallisci (i32.const 1)) (unreachable)))
    (local.get $r))
  (func $sub_i64 (param $a i64) (param $b i64) (result i64) (local $r i64)
    (local.set $r (i64.sub (local.get $a) (local.get $b)))
    (if (i64.lt_s (i64.and (i64.xor (local.get $a) (local.get $b)) (i64.xor (local.get $a) (local.get $r))) (i64.const 0))
      (then (call $fallisci (i32.const 1)) (unreachable)))
    (local.get $r))
  (func $mul_i64 (param $a i64) (param $b i64) (result i64) (local $r i64)
    (if (i64.eqz (local.get $a)) (then (return (i64.const 0))))
    (if (i32.or
          (i32.and (i64.eq (local.get $a) (i64.const -1)) (i64.eq (local.get $b) (i64.const -9223372036854775808)))
          (i32.and (i64.eq (local.get $b) (i64.const -1)) (i64.eq (local.get $a) (i64.const -9223372036854775808))))
      (then (call $fallisci (i32.const 1)) (unreachable)))
    (local.set $r (i64.mul (local.get $a) (local.get $b)))
    (if (i64.ne (i64.div_s (local.get $r) (local.get $a)) (local.get $b))
      (then (call $fallisci (i32.const 1)) (unreachable)))
    (local.get $r))
  (func $div_i64 (param $a i64) (param $b i64) (result i64)
    (if (i64.eqz (local.get $b)) (then (call $fallisci (i32.const 4)) (unreachable)))
    (if (i32.and (i64.eq (local.get $a) (i64.const -9223372036854775808)) (i64.eq (local.get $b) (i64.const -1)))
      (then (call $fallisci (i32.const 1)) (unreachable)))
    (i64.div_s (local.get $a) (local.get $b)))
  (func $rem_i64 (param $a i64) (param $b i64) (result i64)
    (if (i64.eqz (local.get $b)) (then (call $fallisci (i32.const 4)) (unreachable)))
    (i64.rem_s (local.get $a) (local.get $b)))
  (func $in_i32 (param $r i64) (result i32)
    (if (i32.or (i64.lt_s (local.get $r) (i64.const -2147483648)) (i64.gt_s (local.get $r) (i64.const 2147483647)))
      (then (call $fallisci (i32.const 1)) (unreachable)))
    (i32.wrap_i64 (local.get $r)))
  (func $div_f64 (param $a f64) (param $b f64) (result f64)
    (if (f64.eq (local.get $b) (f64.const 0)) (then (call $fallisci (i32.const 4)) (unreachable)))
    (f64.div (local.get $a) (local.get $b)))
  (func $abs_i64 (param $a i64) (result i64)
    (if (i64.eq (local.get $a) (i64.const -9223372036854775808)) (then (call $fallisci (i32.const 1)) (unreachable)))
    (if (result i64) (i64.lt_s (local.get $a) (i64.const 0))
      (then (i64.sub (i64.const 0) (local.get $a))) (else (local.get $a))))
  (func $f64_in_i64 (param $a f64) (result i64)
    (if (i32.or (f64.ne (local.get $a) (local.get $a))
                (i32.or (f64.ge (local.get $a) (f64.const 9223372036854775807))
                        (f64.lt (local.get $a) (f64.const -9223372036854775808))))
      (then (call $fallisci (i32.const 6)) (unreachable)))
    (i64.trunc_f64_s (local.get $a)))
"""


class NonSupportato(Exception):
    def __init__(self, motivo, nodo=None):
        super().__init__(motivo)
        self.motivo = motivo
        self.riga = getattr(nodo, "riga", None)


@dataclass
class Firma:
    nome: str
    parametri: list                 # (nome, tipo Tessera)
    ritorno: object                 # tipo Tessera o None
    decl: object


@dataclass
class Risultato:
    wat: str
    compilate: list                 # nomi delle funzioni compilate
    saltate: dict                   # nome -> motivo
    firme: dict = field(default_factory=dict)


def tipo_semplice(t, nodo):
    if t is None:
        return None
    if isinstance(t, A.TipoNominato) and not t.argomenti and t.nome in TIPI:
        return t.nome
    raise NonSupportato(f"tipo {mostra_tipo_breve(t)} non supportato (solo i32, i64, f64, bool)", nodo)


def mostra_tipo_breve(t):
    from .printer import mostra_tipo
    return mostra_tipo(t)


def firma_di(decl):
    if decl.esterna:
        raise NonSupportato("funzione esterna", decl)
    if decl.effetti:
        raise NonSupportato("ha effetti: per ora si compilano solo le funzioni con effects: none", decl)
    if decl.generici:
        raise NonSupportato("parametri generici non supportati", decl)
    parametri = []
    for p in decl.parametri:
        if p.modo:
            raise NonSupportato(f"parametro {p.modo} non supportato", p)
        parametri.append((p.nome, tipo_semplice(p.tipo, p)))
    return Firma(decl.nome, parametri, tipo_semplice(decl.ritorno, decl), decl)


def compila_modulo(modulo):
    """Compila le funzioni compilabili; le altre finiscono in 'saltate' con il motivo."""
    firme, saltate = {}, {}
    for d in modulo.dichiarazioni:
        if isinstance(d, A.Funzione):
            try:
                firme[d.nome] = firma_di(d)
            except NonSupportato as e:
                saltate[d.nome] = e.motivo
    # Una funzione che chiama una funzione saltata va saltata anche lei: si ripete finche' l'insieme e' stabile.
    while True:
        corpi, nuove = {}, {}
        for nome, firma in firme.items():
            try:
                corpi[nome] = CompilaFunzione(firma, firme).compila()
            except NonSupportato as e:
                nuove[nome] = e.motivo + (f" (riga {e.riga})" if e.riga else "")
        if not nuove:
            break
        for nome, motivo in nuove.items():
            saltate[nome] = motivo
            del firme[nome]
    parti = ["(module", '  (import "env" "fallisci" (func $fallisci (param i32)))', AIUTANTI]
    parti.extend(corpi[n] for n in firme)
    parti.append(")")
    return Risultato("\n".join(parti), list(firme), saltate, firme)


class CompilaFunzione:
    def __init__(self, firma, firme):
        self.firma, self.firme = firma, firme
        self.locali = []            # (nome wasm, tipo wasm)
        self.ambiti = [{}]          # nome Tessera -> (nome wasm, tipo Tessera)
        self.etichette = []         # (tipo, etichetta per break, etichetta per continue)
        self.contatore = 0

    def nuovo_locale(self, base, tipo):
        self.contatore += 1
        nome = f"${base}_{self.contatore}"
        self.locali.append((nome, TIPI[tipo]))
        return nome

    def cerca(self, nome, nodo):
        for ambito in reversed(self.ambiti):
            if nome in ambito:
                return ambito[nome]
        raise NonSupportato(f"'{nome}' non e' una variabile locale (costanti e funzioni come valori non supportate)", nodo)

    def compila(self):
        f = self.firma
        for nome, tipo in f.parametri:
            self.ambiti[0][nome] = (f"${nome}", tipo)
        corpo = []
        for condizione in f.decl.richiede:
            corpo += self.controllo(condizione, 2)
        corpo.append("(block $__fine")
        corpo += self.blocco(f.decl.corpo)
        if f.ritorno is not None:
            corpo += ["(call $fallisci (i32.const 5))", "unreachable"]
        corpo.append(")")
        if f.decl.garantisce:
            self.ambiti.append({"result": ("$__ret", f.ritorno)})
            for condizione in f.decl.garantisce:
                corpo += self.controllo(condizione, 3)
            self.ambiti.pop()
        if f.ritorno is not None:
            corpo.append("(local.get $__ret)")
        export = f' (export "{f.nome}")' if f.decl.pubblica else ""
        intestazione = f"  (func $fn_{f.nome}{export}" + "".join(f" (param ${n} {TIPI[t]})" for n, t in f.parametri)
        if f.ritorno is not None:
            intestazione += f" (result {TIPI[f.ritorno]})"
            self.locali.insert(0, ("$__ret", TIPI[f.ritorno]))
        locali = "".join(f" (local {n} {t})" for n, t in self.locali)
        return intestazione + locali + "\n    " + "\n    ".join(corpo) + ")"

    def controllo(self, condizione, codice):
        codice_cond, _ = self.espressione(condizione, "bool")
        return codice_cond + [f"(if (i32.eqz) (then (call $fallisci (i32.const {codice})) (unreachable)))"]

    # ---------- istruzioni ----------

    def blocco(self, istruzioni):
        self.ambiti.append({})
        codice = []
        for i in istruzioni:
            codice += self.istruzione(i)
        self.ambiti.pop()
        return codice

    def istruzione(self, n):
        if isinstance(n, (A.Let, A.Var)):
            if isinstance(n, A.Let) and not isinstance(n.schema, A.SchemaNome):
                raise NonSupportato("let con schema non supportato", n)
            nome = n.schema.nome if isinstance(n, A.Let) else n.nome
            atteso = tipo_semplice(n.tipo, n) if n.tipo is not None else None
            codice, tipo = self.espressione(n.valore, atteso)
            locale = self.nuovo_locale(nome, tipo)
            self.ambiti[-1][nome] = (locale, tipo)
            return codice + [f"(local.set {locale})"]
        if isinstance(n, A.Assegna):
            if not isinstance(n.bersaglio, A.Nome):
                raise NonSupportato("assegnazione a campi o elementi non supportata", n)
            locale, tipo = self.cerca(n.bersaglio.nome, n)
            if n.op == "=":
                codice, _ = self.espressione(n.valore, tipo)
            else:
                codice, _ = self.binaria(n.op[0], n.bersaglio, n.valore, n, tipo)
            return codice + [f"(local.set {locale})"]
        if isinstance(n, A.Ritorna):
            if n.valore is None:
                return ["(br $__fine)"]
            codice, _ = self.espressione(n.valore, self.firma.ritorno)
            return codice + ["(local.set $__ret)", "(br $__fine)"]
        if isinstance(n, A.Espressione):
            codice, tipo = self.espressione(n.espressione, None)
            return codice + (["drop"] if tipo is not None else [])
        if isinstance(n, A.Se):
            return self.se(n.rami, n.altrimenti)
        if isinstance(n, A.Mentre):
            fuori, giro = self.etichetta("w"), self.etichetta("l")
            self.etichette.append((fuori, giro))
            cond, _ = self.espressione(n.condizione, "bool")
            corpo = self.blocco(n.corpo)
            self.etichette.pop()
            return [f"(block {fuori} (loop {giro}"] + cond + [f"(br_if {fuori} (i32.eqz))"] + corpo + \
                   [f"(br {giro})))"]
        if isinstance(n, A.Per):
            return self.per(n)
        if isinstance(n, A.Interrompi):
            if not self.etichette:
                raise NonSupportato("break fuori da un ciclo", n)
            return [f"(br {self.etichette[-1][0]})"]
        if isinstance(n, A.Continua):
            if not self.etichette:
                raise NonSupportato("continue fuori da un ciclo", n)
            return [f"(br {self.etichette[-1][1]})"]
        raise NonSupportato(f"istruzione {type(n).__name__} non supportata", n)

    def etichetta(self, base):
        self.contatore += 1
        return f"${base}{self.contatore}"

    def se(self, rami, altrimenti):
        (condizione, blocco), resto = rami[0], rami[1:]
        cond, _ = self.espressione(condizione, "bool")
        allora = self.blocco(blocco)
        if resto:
            altro = self.se(resto, altrimenti)
        else:
            altro = self.blocco(altrimenti) if altrimenti is not None else []
        codice = cond + ["(if (then"] + allora + [")"]
        if altro:
            codice += ["(else"] + altro + [")"]
        return codice + [")"]

    def per(self, n):
        if not isinstance(n.iterabile, A.Intervallo):
            raise NonSupportato("for solo su intervalli a..b", n)
        if not isinstance(n.schema, (A.SchemaNome, A.SchemaJolly)):
            raise NonSupportato("for con schema non supportato", n)
        tipo = self.tipo_comune(n.iterabile.inizio, n.iterabile.fine, n) or "i64"
        if tipo not in ("i32", "i64"):
            raise NonSupportato("un intervallo vuole interi", n)
        inizio, _ = self.espressione(n.iterabile.inizio, tipo)
        fine_codice, _ = self.espressione(n.iterabile.fine, tipo)
        contatore, fine = self.nuovo_locale("i", tipo), self.nuovo_locale("fine", tipo)
        fuori, giro, prossimo = self.etichetta("f"), self.etichetta("g"), self.etichetta("c")
        self.etichette.append((fuori, prossimo))
        self.ambiti.append({})
        legame = []
        if isinstance(n.schema, A.SchemaNome):
            variabile = self.nuovo_locale(n.schema.nome, tipo)
            self.ambiti[-1][n.schema.nome] = (variabile, tipo)
            legame = [f"(local.set {variabile} (local.get {contatore}))"]
        corpo = self.blocco(n.corpo)
        self.ambiti.pop()
        self.etichette.pop()
        t = TIPI[tipo]
        return inizio + [f"(local.set {contatore})"] + fine_codice + [f"(local.set {fine})",
                f"(block {fuori} (loop {giro}",
                f"(br_if {fuori} ({t}.ge_s (local.get {contatore}) (local.get {fine})))"] + legame + \
               [f"(block {prossimo}"] + corpo + [")",
                f"(local.set {contatore} ({t}.add (local.get {contatore}) ({t}.const 1)))",
                f"(br {giro})))"]

    # ---------- espressioni ----------

    def inferisci(self, e):
        """Tipo Tessera di un'espressione; None per un intero letterale, che prende il tipo dal contesto."""
        if isinstance(e, A.Letterale):
            if e.tipo == "int":
                return None
            if e.tipo == "float":
                return "f64"
            if e.tipo == "bool":
                return "bool"
            raise NonSupportato("quantita' con unita' non supportate", e)
        if isinstance(e, A.Nome):
            return self.cerca(e.nome, e)[1]
        if isinstance(e, A.Risultato):
            return self.cerca("result", e)[1]
        if isinstance(e, A.Binaria):
            return self.tipo_comune(e.sinistra, e.destra, e)
        if isinstance(e, A.Negativo):
            return self.inferisci(e.espressione)
        if isinstance(e, (A.Confronto, A.Logica, A.Non, A.Implica)):
            return "bool"
        if isinstance(e, A.Chiamata):
            if isinstance(e.funzione, A.Nome) and e.funzione.nome in self.firme:
                return self.firme[e.funzione.nome].ritorno
            if isinstance(e.funzione, A.Campo):
                return {"to_f64": "f64", "to_int": "i64", "abs": self.inferisci(e.funzione.oggetto)}.get(e.funzione.nome)
        raise NonSupportato(f"espressione {mostra(e)} non supportata", e)

    def tipo_comune(self, a, b, nodo):
        ta, tb = self.inferisci(a), self.inferisci(b)
        if ta and tb and ta != tb:
            raise ErroreTessera("tipo", f"{mostra(nodo)}: {ta} e {tb} non si mescolano", riga=nodo.riga)
        return ta or tb

    def espressione(self, e, atteso):
        """Restituisce (istruzioni WAT, tipo Tessera del valore)."""
        if isinstance(e, A.Letterale):
            if e.tipo == "bool":
                return [f"(i32.const {1 if e.valore else 0})"], "bool"
            if e.tipo == "float":
                return [f"(f64.const {e.valore!r})"], "f64"
            tipo = atteso if atteso in ("i32", "i64") else "i64"
            if atteso in ("f64", "bool"):
                raise ErroreTessera("tipo", f"l'intero {e.valore} non e' un {atteso}", riga=e.riga,
                                    suggerimento="scrivi il numero con il punto decimale" if atteso == "f64" else None)
            limite = 2**31 if tipo == "i32" else 2**63
            if not -limite <= e.valore < limite:
                raise ErroreTessera("tipo", f"{e.valore} non sta in {tipo}", riga=e.riga)
            return [f"({TIPI[tipo]}.const {e.valore})"], tipo
        if isinstance(e, (A.Nome, A.Risultato)):
            locale, tipo = self.cerca(e.nome if isinstance(e, A.Nome) else "result", e)
            return [f"(local.get {locale})"], tipo
        if isinstance(e, A.Binaria):
            return self.binaria(e.op, e.sinistra, e.destra, e, atteso)
        if isinstance(e, A.Negativo):
            if isinstance(e.espressione, A.Letterale) and e.espressione.tipo in ("int", "float"):
                return self.espressione(A.Letterale(-e.espressione.valore, e.espressione.tipo, riga=e.riga), atteso)
            return self.binaria("-", A.Letterale(0, "int", riga=e.riga) if self.inferisci(e.espressione) != "f64"
                                else A.Letterale(0.0, "float", riga=e.riga), e.espressione, e, atteso)
        if isinstance(e, A.Confronto):
            return self.confronto(e)
        if isinstance(e, A.Logica):
            codice, _ = self.espressione(e.operandi[0], "bool")
            for operando in e.operandi[1:]:
                altro, _ = self.espressione(operando, "bool")
                if e.op == "and":
                    codice = codice + ["(if (result i32) (then"] + altro + [") (else (i32.const 0)))"]
                else:
                    codice = codice + ["(if (result i32) (then (i32.const 1)) (else"] + altro + ["))"]
            return codice, "bool"
        if isinstance(e, A.Non):
            codice, _ = self.espressione(e.espressione, "bool")
            return codice + ["(i32.eqz)"], "bool"
        if isinstance(e, A.Implica):
            premessa, _ = self.espressione(e.premessa, "bool")
            conseguenza, _ = self.espressione(e.conseguenza, "bool")
            return premessa + ["(if (result i32) (then"] + conseguenza + [") (else (i32.const 1)))"], "bool"
        if isinstance(e, A.Chiamata):
            return self.chiamata(e)
        raise NonSupportato(f"espressione {mostra(e)} non supportata", e)

    def binaria(self, op, sinistra, destra, nodo, atteso):
        tipo = self.tipo_comune(sinistra, destra, nodo) or (atteso if atteso in ("i32", "i64") else "i64")
        if tipo == "bool":
            raise ErroreTessera("tipo", f"l'operatore {op} non si applica a bool", riga=nodo.riga)
        a, _ = self.espressione(sinistra, tipo)
        b, _ = self.espressione(destra, tipo)
        if tipo == "f64":
            if op == "%":
                raise NonSupportato("% sui decimali non supportato", nodo)
            istruzione = {"+": "(f64.add)", "-": "(f64.sub)", "*": "(f64.mul)", "/": "(call $div_f64)"}.get(op)
            if istruzione is None:
                raise NonSupportato(f"operatore {op} non supportato", nodo)
            return a + b + [istruzione], "f64"
        aiutante = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "rem"}.get(op)
        if aiutante is None:
            raise NonSupportato(f"operatore {op} non supportato", nodo)
        if tipo == "i64":
            return a + b + [f"(call ${aiutante}_i64)"], "i64"
        # i32: si calcola in i64 (nessun overflow possibile) e si controlla che il risultato stia in i32.
        return a + ["(i64.extend_i32_s)"] + b + ["(i64.extend_i32_s)", f"(call ${aiutante}_i64)",
                                                    "(call $in_i32)"], "i32"

    def confronto(self, e):
        if e.op == "in":
            raise NonSupportato("operatore in non supportato", e)
        tipo = self.tipo_comune(e.sinistra, e.destra, e) or "i64"
        a, _ = self.espressione(e.sinistra, tipo)
        b, _ = self.espressione(e.destra, tipo)
        t = TIPI[tipo]
        if tipo == "bool" and e.op not in ("==", "!="):
            raise ErroreTessera("tipo", f"{e.op} non si applica a bool", riga=e.riga)
        segno = "" if tipo == "f64" else "_s"
        istruzione = {"==": "eq", "!=": "ne", "<": f"lt{segno}", "<=": f"le{segno}", ">": f"gt{segno}",
                      ">=": f"ge{segno}"}[e.op]
        return a + b + [f"({t}.{istruzione})"], "bool"

    def chiamata(self, e):
        if isinstance(e.funzione, A.Campo):
            metodo, oggetto = e.funzione.nome, e.funzione.oggetto
            if e.argomenti:
                raise NonSupportato(f"metodo {metodo} con argomenti non supportato", e)
            codice, tipo = self.espressione(oggetto, None)
            if metodo == "to_f64" and tipo in ("i32", "i64"):
                return codice + [f"(f64.convert_{TIPI[tipo]}_s)"], "f64"
            if metodo == "to_int" and tipo == "f64":
                return codice + ["(call $f64_in_i64)"], "i64"
            if metodo == "abs" and tipo == "i64":
                return codice + ["(call $abs_i64)"], "i64"
            if metodo == "abs" and tipo == "f64":
                return codice + ["(f64.abs)"], "f64"
            raise NonSupportato(f"metodo {metodo} su {tipo} non supportato", e)
        if not isinstance(e.funzione, A.Nome) or e.funzione.nome not in self.firme:
            raise NonSupportato(f"chiamata a {mostra(e.funzione)}: non e' una funzione compilata", e)
        firma = self.firme[e.funzione.nome]
        if len(e.argomenti) != len(firma.parametri) or any(a.nome or a.modo for a in e.argomenti):
            raise NonSupportato(f"chiamata a {firma.nome}: solo argomenti posizionali, tutti presenti", e)
        codice = []
        for a, (_, tipo) in zip(e.argomenti, firma.parametri):
            parte, _ = self.espressione(a.valore, tipo)
            codice += parte
        return codice + [f"(call $fn_{firma.nome})"], firma.ritorno


# ---------- esecuzione con wasmtime ----------

def binario(wat):
    import wasmtime
    return wasmtime.wat2wasm(wat)


class Esecutore:
    """Istanzia il modulo compilato e ne chiama le funzioni esportate."""

    def __init__(self, risultato):
        import wasmtime
        self.wasmtime = wasmtime
        self.risultato = risultato
        motore = wasmtime.Engine()
        self.store = wasmtime.Store(motore)
        self.ultimo_codice = None

        def fallisci(codice):
            self.ultimo_codice = codice

        tipo = wasmtime.FuncType([wasmtime.ValType.i32()], [])
        funzione = wasmtime.Func(self.store, tipo, fallisci)
        modulo = wasmtime.Module(motore, risultato.wat)
        self.istanza = wasmtime.Instance(self.store, modulo, [funzione])

    def chiama(self, nome, argomenti):
        firma = self.risultato.firme.get(nome)
        if firma is None or not firma.decl.pubblica:
            raise ErroreTessera("compilatore", f"{nome} non e' una funzione pubblica compilata")
        valori = []
        for (parametro, tipo), v in zip(firma.parametri, argomenti):
            valori.append(int(v) if tipo == "bool" else v)
        self.ultimo_codice = None
        try:
            r = self.istanza.exports(self.store)[nome](self.store, *valori)
        except self.wasmtime.Trap as trappola:
            tipo, messaggio = CODICI.get(self.ultimo_codice, ("esecuzione", f"esecuzione interrotta: {trappola}"))
            raise ErroreTessera(tipo, f"{nome}: {messaggio}") from None
        return bool(r) if firma.ritorno == "bool" else r
