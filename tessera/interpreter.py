# Copyright 2026 Stefano Stegani - Airgrid Network - www.airgrid.it
# SPDX-License-Identifier: Apache-2.0
"""Interprete ad albero di Tessera (prototipo, fase 1).

Controlla durante l'esecuzione cio' che il compilatore definitivo dovra' garantire prima:
effetti, contratti, tipi dei parametri, proprieta' (edit/take), overflow, permessi sui file.
"""
import difflib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import ast as A
from . import values as V
from .errors import ErroreTessera
from .library import GLOBALI, METODI, METODI_MUTANTI, specie_metodo
from .parser import analizza_file
from .printer import mostra, mostra_schema, mostra_tipo


def errore(tipo, messaggio, nodo=None, suggerimento=None):
    return ErroreTessera(tipo, messaggio, riga=getattr(nodo, "riga", None) or None, suggerimento=suggerimento)


def forse(nome, candidati):
    simili = difflib.get_close_matches(nome, list(candidati), n=1)
    return f"forse intendevi '{simili[0]}'" if simili else None


# ---------- ambiente ----------

class Cella:
    __slots__ = ("valore", "mutabile", "spostata_alla_riga")

    def __init__(self, valore, mutabile):
        self.valore = valore
        self.mutabile = mutabile
        self.spostata_alla_riga = None


class Ambiente:
    def __init__(self, genitore=None):
        self.nomi = {}
        self.genitore = genitore

    def cerca(self, nome):
        amb = self
        while amb is not None:
            if nome in amb.nomi:
                return amb.nomi[nome]
            amb = amb.genitore
        return None

    def definisci(self, nome, valore, mutabile=False):
        self.nomi[nome] = Cella(valore, mutabile)

    def figlio(self):
        return Ambiente(self)


class SegnaleRitorno(Exception):
    def __init__(self, valore):
        self.valore = valore


class SegnaleInterrompi(Exception):
    pass


class SegnaleContinua(Exception):
    pass


@dataclass
class ArgValutato:
    nome: object
    modo: object
    valore: object
    cella: object
    nodo: object


@dataclass
class Contesto:
    """Cosa puo' fare il codice in esecuzione in questo momento."""
    effetti: frozenset
    modulo: object
    descrizione: str
    funzione: object = None
    permessi_fs: list = field(default_factory=list)


# ---------- tipi e costruttori ----------

class InfoNuovoTipo:
    def __init__(self, decl, modulo):
        self.decl, self.nome, self.modulo = decl, decl.nome, modulo

    def chiama(self, interp, args, nodo):
        if len(args) != 1 or args[0].nome or args[0].modo:
            raise errore("tipo", f"{self.nome}(...) vuole un solo valore", nodo)
        valore = args[0].valore
        interp.controlla_tipo(valore, self.decl.tipo, [], nodo, f"valore di {self.nome}", self.modulo)
        return V.NuovoTipo(self.nome, V.copia(valore))


class InfoStruttura:
    def __init__(self, decl, modulo):
        self.decl, self.nome, self.modulo = decl, decl.nome, modulo
        self.campi = decl.campi

    def chiama(self, interp, args, nodo):
        valori = interp.associa_campi(self.nome, self.campi, args, nodo)
        struttura = V.Struttura(self.nome, valori)
        for campo, tipo in self.campi:
            interp.controlla_tipo(valori[campo], tipo, self.decl.generici, nodo, f"campo {self.nome}.{campo}", self.modulo)
        interp.controlla_invarianti(self, struttura, nodo)
        return struttura


class InfoSomma:
    def __init__(self, decl, modulo):
        self.decl, self.nome, self.modulo = decl, decl.nome, modulo
        self.varianti = {v.nome: v for v in decl.varianti}

    def variante(self, nome, nodo):
        if nome not in self.varianti:
            raise errore("nome", f"il tipo {self.nome} non ha la variante {nome}", nodo, forse(nome, self.varianti))
        v = self.varianti[nome]
        return CostruttoreVariante(self, v) if v.campi else V.ValoreVariante(self.nome, v.nome, [])


class CostruttoreVariante:
    def __init__(self, info, decl):
        self.info, self.decl = info, decl

    def chiama(self, interp, args, nodo):
        valori = interp.associa_campi(self.decl.nome, self.decl.campi, args, nodo)
        for campo, tipo in self.decl.campi:
            interp.controlla_tipo(valori[campo], tipo, self.info.decl.generici, nodo,
                                  f"campo {self.decl.nome}.{campo}", self.info.modulo)
        nomi = [c for c, _ in self.decl.campi]
        return V.ValoreVariante(self.info.nome, self.decl.nome, [valori[c] for c in nomi], nomi)


class CostruttoreIncorporato:
    """Ok, Err, Some, Secret, Untrusted."""

    def __init__(self, nome):
        self.nome = nome

    def chiama(self, interp, args, nodo):
        if len(args) != 1 or args[0].nome or args[0].modo:
            raise errore("tipo", f"{self.nome}(...) vuole un solo valore", nodo)
        v = V.copia(args[0].valore)
        if self.nome == "Secret":
            return V.Segreto(v)
        if self.nome == "Untrusted":
            return V.NonFidato(v)
        return V.ValoreVariante("Option" if self.nome == "Some" else "Result", self.nome, [v])


INCORPORATI = {n: CostruttoreIncorporato(n) for n in ("Ok", "Err", "Some", "Secret", "Untrusted")}


class FunzioneUtente:
    def __init__(self, decl, modulo):
        self.decl, self.nome, self.modulo = decl, decl.nome, modulo

    def chiama(self, interp, args, nodo):
        return interp.chiama_funzione(self, args, nodo)


class Chiusura:
    def __init__(self, nodo, ambiente, contesto):
        self.nodo, self.ambiente, self.contesto = nodo, ambiente, contesto

    def chiama(self, interp, args, nodo):
        if any(a.nome or a.modo for a in args):
            raise errore("tipo", "una funzione anonima accetta solo argomenti semplici", nodo)
        if len(args) != len(self.nodo.parametri):
            raise errore("tipo", f"la funzione anonima vuole {len(self.nodo.parametri)} argomenti, "
                                 f"ne ha ricevuti {len(args)}", nodo)
        amb = self.ambiente.figlio()
        for (nome, tipo), a in zip(self.nodo.parametri, args):
            interp.controlla_tipo(a.valore, tipo, [], nodo, f"parametro {nome}", self.contesto.modulo)
            amb.definisci(nome, a.valore)
        # Una funzione anonima non acquista effetti: ha al piu' quelli del punto in cui e' stata scritta.
        effetti = self.contesto.effetti & interp.contesto.effetti
        contesto = Contesto(effetti, self.contesto.modulo, "funzione anonima", None, interp.contesto.permessi_fs)
        with interp.in_contesto(contesto):
            return interp.valuta(self.nodo.corpo, amb)


# ---------- moduli ----------

class ContestoModulo:
    def __init__(self, ast_modulo):
        self.ast = ast_modulo
        self.nome = ast_modulo.nome
        self.file = ast_modulo.file
        self.funzioni, self.tipi, self.costanti, self.processi = {}, {}, {}, {}
        self.varianti = {}          # nome variante -> InfoSomma
        self.importati = {}         # nome -> FunzioneUtente, info di tipo o valore costante
        self.pubblici = set()


class Programma:
    """Carica un file .tsr e i moduli che importa (cercati nella stessa cartella e nelle sottocartelle)."""

    def __init__(self, percorso):
        self.radice = Path(percorso).resolve().parent
        self.moduli = {}
        self._indice = None
        self.principale = self.carica_file(Path(percorso).resolve())

    def indice(self):
        if self._indice is None:
            self._indice = {}
            for f in self.radice.rglob("*.tsr"):
                m = re.search(r"^\s*module\s+([a-z_][a-z0-9_.]*)", f.read_text(encoding="utf-8"), re.MULTILINE)
                if m:
                    self._indice.setdefault(m.group(1), f.resolve())
        return self._indice

    def carica_file(self, percorso):
        ast_modulo = analizza_file(percorso)
        if ast_modulo.nome in self.moduli:
            return self.moduli[ast_modulo.nome]
        ctx = ContestoModulo(ast_modulo)
        self.moduli[ctx.nome] = ctx
        self.registra(ctx)
        for imp in ast_modulo.importazioni:
            self.importa(ctx, imp)
        return ctx

    def registra(self, ctx):
        for d in ctx.ast.dichiarazioni:
            nome = d.nome
            if nome in ctx.funzioni or nome in ctx.tipi or nome in ctx.costanti or nome in ctx.processi:
                raise ErroreTessera("nome", f"'{nome}' dichiarato due volte", riga=d.riga, file=ctx.file)
            if isinstance(d, A.Funzione):
                ctx.funzioni[nome] = FunzioneUtente(d, ctx)
                if d.pubblica:
                    ctx.pubblici.add(nome)
            elif isinstance(d, A.TipoAlias):
                ctx.tipi[nome] = InfoNuovoTipo(d, ctx)
            elif isinstance(d, A.TipoComposto):
                info = InfoSomma(d, ctx) if d.varianti else InfoStruttura(d, ctx)
                ctx.tipi[nome] = info
                if isinstance(info, InfoSomma):
                    for v in d.varianti:
                        if v.nome in ctx.varianti or v.nome in INCORPORATI or v.nome == "None":
                            raise ErroreTessera("nome", f"variante '{v.nome}' gia' usata da un altro tipo",
                                                riga=v.riga, file=ctx.file, suggerimento=f"usa {nome}.{v.nome}")
                        ctx.varianti[v.nome] = info
            elif isinstance(d, A.Costante):
                ctx.costanti[nome] = d
            elif isinstance(d, A.Processo):
                ctx.processi[nome] = d
            if getattr(d, "pubblico", False) or getattr(d, "pubblica", False):
                ctx.pubblici.add(nome)

    def importa(self, ctx, imp):
        if imp.modulo.startswith("std."):
            raise ErroreTessera("nome", f"il modulo {imp.modulo} non esiste ancora nel prototipo", riga=imp.riga,
                                file=ctx.file, suggerimento="le funzioni di base (print, read_text, metodi di Str e "
                                                            "List) non vanno importate")
        if imp.modulo not in self.moduli:
            percorso = self.indice().get(imp.modulo)
            if percorso is None:
                raise ErroreTessera("nome", f"modulo {imp.modulo} non trovato sotto {self.radice}", riga=imp.riga,
                                    file=ctx.file, suggerimento=forse(imp.modulo, self.indice()))
            self.carica_file(percorso)
        altro = self.moduli[imp.modulo]
        for nome in imp.nomi:
            oggetto = altro.funzioni.get(nome) or altro.tipi.get(nome) or altro.costanti.get(nome)
            if oggetto is None:
                raise ErroreTessera("nome", f"{imp.modulo} non contiene '{nome}'", riga=imp.riga, file=ctx.file,
                                    suggerimento=forse(nome, list(altro.funzioni) + list(altro.tipi)))
            if nome not in altro.pubblici:
                raise ErroreTessera("nome", f"'{nome}' non e' pubblico in {imp.modulo}", riga=imp.riga, file=ctx.file,
                                    suggerimento=f"dichiaralo con pub in {imp.modulo}")
            ctx.importati[nome] = (altro, oggetto)
            if isinstance(oggetto, InfoSomma):
                for v in oggetto.varianti:
                    ctx.varianti.setdefault(v, oggetto)


# ---------- interprete ----------

class Interprete:
    def __init__(self, programma, eco=True):
        self.programma = programma
        self.eco = eco
        self.uscite = []
        self.contesto = Contesto(frozenset(), programma.principale, "modulo")
        # Prima i moduli importati, poi chi li importa: le costanti possono dipendere da quelle importate.
        for ctx in reversed(list(programma.moduli.values())):
            self.inizializza_costanti(ctx)

    # ----- contesto ed effetti -----

    class _Cambio:
        def __init__(self, interp, contesto):
            self.interp, self.nuovo = interp, contesto

        def __enter__(self):
            self.vecchio = self.interp.contesto
            self.interp.contesto = self.nuovo

        def __exit__(self, *exc):
            self.interp.contesto = self.vecchio
            return False

    def in_contesto(self, contesto):
        return Interprete._Cambio(self, contesto)

    def richiedi_effetto(self, effetto, nodo, chi):
        if effetto not in self.contesto.effetti:
            dichiarati = ", ".join(sorted(self.contesto.effetti)) or "none"
            raise errore("effetti", f"{chi} richiede l'effetto '{effetto}', ma {self.contesto.descrizione} "
                                    f"dichiara effects: {dichiarati}", nodo,
                         f"aggiungi {effetto} a effects di {self.contesto.descrizione}")

    def percorso(self, p):
        """I percorsi relativi partono dalla cartella del file principale, non da quella corrente."""
        return os.path.normpath(os.path.join(self.programma.radice, p))

    def controlla_permesso_file(self, percorso, nodo):
        assoluto = os.path.normcase(self.percorso(percorso))
        for prefisso in self.contesto.permessi_fs:
            base = os.path.normcase(self.percorso(prefisso))
            if assoluto == base or assoluto.startswith(base.rstrip(os.sep) + os.sep):
                return
        raise errore("sicurezza", f"nessun permesso per leggere '{percorso}'", nodo,
                     f'aggiungi grants: fs.read("{os.path.dirname(percorso) or percorso}") al process')

    def uscita(self, testo):
        self.uscite.append(testo)
        if self.eco:
            print(testo)

    def controlla_intero(self, valore, nodo):
        if not V.MIN_I64 <= valore <= V.MAX_I64:
            raise errore("esecuzione", "overflow: il risultato non sta in un intero a 64 bit", nodo,
                         "usa un controllo prima dell'operazione o un tipo piu' ampio")
        return valore

    # ----- costanti -----

    def inizializza_costanti(self, ctx):
        contesto = Contesto(frozenset(), ctx, f"modulo {ctx.nome}")
        with self.in_contesto(contesto):
            for nome, decl in list(ctx.costanti.items()):
                if isinstance(decl, A.Costante):
                    valore = self.valuta(decl.valore, Ambiente())
                    self.controlla_tipo(valore, decl.tipo, [], decl, f"costante {nome}", ctx)
                    ctx.costanti[nome] = valore
        for nome, (altro, oggetto) in list(ctx.importati.items()):
            if isinstance(oggetto, A.Costante):
                ctx.importati[nome] = (altro, altro.costanti[nome])

    # ----- ricerca dei nomi -----

    def cerca_nome(self, nome, amb, nodo):
        cella = amb.cerca(nome) if amb else None
        if cella is not None:
            if cella.spostata_alla_riga:
                raise errore("proprieta", f"'{nome}' e' stato consumato con take alla riga {cella.spostata_alla_riga}",
                             nodo, "passa una copia o non usare piu' il valore dopo take")
            return cella.valore
        m = self.contesto.modulo
        if nome in m.costanti:
            return m.costanti[nome]
        if nome in m.funzioni:
            return m.funzioni[nome]
        if nome in m.importati and not self.e_tipo(m.importati[nome][1]):
            return m.importati[nome][1]
        if nome in GLOBALI:
            return GLOBALI[nome]
        candidati = list(m.costanti) + list(m.funzioni) + list(GLOBALI) + (list(self.nomi_locali(amb)) if amb else [])
        raise errore("nome", f"'{nome}' non e' definito", nodo, forse(nome, candidati))

    @staticmethod
    def nomi_locali(amb):
        while amb is not None:
            yield from amb.nomi
            amb = amb.genitore

    @staticmethod
    def e_tipo(oggetto):
        return isinstance(oggetto, (InfoNuovoTipo, InfoStruttura, InfoSomma))

    def cerca_tipo(self, nome, nodo, modulo=None):
        m = modulo or self.contesto.modulo
        if nome in m.tipi:
            return m.tipi[nome]
        if nome in m.importati and self.e_tipo(m.importati[nome][1]):
            return m.importati[nome][1]
        if nome in m.varianti:
            return m.varianti[nome].variante(nome, nodo)
        if nome in INCORPORATI:
            return INCORPORATI[nome]
        if nome == "None":
            return V.nessuno()
        raise errore("nome", f"tipo o variante '{nome}' non definito", nodo,
                     forse(nome, list(m.tipi) + list(m.varianti) + list(INCORPORATI)))

    # ----- controllo dei tipi a runtime -----

    def controlla_tipo(self, v, tipo, generici, nodo, descrizione, modulo=None):
        if tipo is None:
            return
        if not self.ha_tipo(v, tipo, generici, nodo, modulo):
            raise errore("tipo", f"{descrizione}: atteso {mostra_tipo(tipo)}, ricevuto {V.nome_tipo(v)} "
                                 f"({V.formatta(v, True) if not isinstance(v, V.Segreto) else 'Secret'})", nodo)

    def ha_tipo(self, v, tipo, generici, nodo, modulo):
        if isinstance(tipo, A.TipoTupla):
            return isinstance(v, tuple) and len(v) == len(tipo.elementi) and all(
                self.ha_tipo(x, t, generici, nodo, modulo) for x, t in zip(v, tipo.elementi))
        if isinstance(tipo, A.TipoFunzione):
            return callable(getattr(v, "chiama", None))
        n, args = tipo.nome, tipo.argomenti
        sotto = lambda x, i: i >= len(args) or not isinstance(args[i], A.Nodo) or self.ha_tipo(x, args[i], generici, nodo, modulo)
        if n in generici:
            return True
        if n in V.LIMITI_INTERI:
            minimo, massimo = V.LIMITI_INTERI[n]
            return isinstance(v, int) and not isinstance(v, bool) and minimo <= v <= massimo
        if n in V.DECIMALI:
            return isinstance(v, float)
        if n == "bool":
            return isinstance(v, bool)
        if n == "char":
            return isinstance(v, str) and len(v) == 1
        if n == "Str":
            return isinstance(v, str)
        if n == "List":
            return isinstance(v, list) and all(sotto(x, 0) for x in v)
        if n == "Option":
            return isinstance(v, V.ValoreVariante) and v.tipo == "Option" and all(sotto(x, 0) for x in v.valori)
        if n == "Result":
            return isinstance(v, V.ValoreVariante) and v.tipo == "Result" and all(
                sotto(x, 0 if v.nome == "Ok" else 1) for x in v.valori)
        if n == "Secret":
            return isinstance(v, V.Segreto) and sotto(v.valore, 0)
        if n == "Untrusted":
            return isinstance(v, V.NonFidato) and sotto(v.valore, 0)
        info = self.cerca_tipo(n, nodo, modulo)
        if isinstance(info, InfoNuovoTipo):
            return isinstance(v, V.NuovoTipo) and v.tipo == n
        if isinstance(info, InfoStruttura):
            return isinstance(v, V.Struttura) and v.tipo == n
        if isinstance(info, InfoSomma):
            return isinstance(v, V.ValoreVariante) and v.tipo == n
        raise errore("tipo", f"'{n}' non e' un tipo", nodo)

    def controlla_invarianti(self, info, struttura, nodo):
        if not info.decl.invarianti:
            return
        amb = Ambiente()
        for campo, valore in struttura.campi.items():
            amb.definisci(campo, valore)
        contesto = Contesto(frozenset(), info.modulo, f"tipo {info.nome}")
        with self.in_contesto(contesto):
            for inv in info.decl.invarianti:
                if self.valuta(inv, amb.figlio()) is not True:
                    raise errore("contratto", f"{info.nome}: invariant violata: {mostra(inv)}", nodo)

    def associa_campi(self, nome, campi, args, nodo):
        nomi = [c for c, _ in campi]
        valori = {}
        for i, a in enumerate(args):
            if a.modo:
                raise errore("proprieta", f"{nome}(...) non accetta edit o take", nodo)
            chiave = a.nome if a.nome else (nomi[i] if i < len(nomi) else None)
            if chiave is None or chiave not in nomi:
                raise errore("tipo", f"{nome} non ha il campo {chiave or '#' + str(i + 1)}", nodo, forse(str(chiave), nomi))
            if chiave in valori:
                raise errore("tipo", f"campo {chiave} assegnato due volte", nodo)
            valori[chiave] = V.copia(a.valore)
        mancanti = [c for c in nomi if c not in valori]
        if mancanti:
            raise errore("tipo", f"{nome}: mancano i campi {', '.join(mancanti)}", nodo)
        return {c: valori[c] for c in nomi}

    # ----- chiamate -----

    def chiama_valore(self, f, valori, nodo):
        return self.invoca(f, [ArgValutato(None, None, v, None, nodo) for v in valori], nodo)

    def invoca(self, f, args, nodo):
        if not callable(getattr(f, "chiama", None)):
            raise errore("tipo", f"un valore di tipo {V.nome_tipo(f)} non si puo' chiamare", nodo)
        if hasattr(f, "impl"):          # Nativa: solo argomenti semplici
            if any(a.nome or a.modo for a in args):
                raise errore("tipo", f"{f.nome} accetta solo argomenti semplici", nodo)
            return f.chiama(self, [a.valore for a in args], nodo)
        return f.chiama(self, args, nodo)

    def valuta_argomenti(self, argomenti, amb):
        risultato, modificate = [], {}
        for a in argomenti:
            if a.modo:
                if not isinstance(a.valore, A.Nome):
                    raise errore("proprieta", f"{a.modo} vuole il nome di una variabile", a)
                cella = amb.cerca(a.valore.nome)
                if cella is None:
                    raise errore("proprieta", f"{a.modo} {a.valore.nome}: serve una variabile locale", a)
                valore = self.cerca_nome(a.valore.nome, amb, a)
                if a.modo == "edit" and not cella.mutabile:
                    raise errore("proprieta", f"'{a.valore.nome}' non e' modificabile", a,
                                 "dichiarala con var per passarla con edit")
                if id(cella) in modificate:
                    raise errore("proprieta", f"'{a.valore.nome}' passata due volte nella stessa chiamata con edit o take", a)
                modificate[id(cella)] = True
                risultato.append(ArgValutato(a.nome, a.modo, valore, cella, a))
            else:
                risultato.append(ArgValutato(a.nome, None, self.valuta(a.valore, amb), None, a))
        for arg in risultato:
            if arg.modo is None and isinstance(arg.nodo.valore, A.Nome):
                cella = amb.cerca(arg.nodo.valore.nome)
                if cella is not None and id(cella) in modificate:
                    raise errore("proprieta", f"'{arg.nodo.valore.nome}' letta e modificata nella stessa chiamata", arg.nodo)
        for arg in risultato:
            if arg.modo == "take":
                arg.cella.spostata_alla_riga = arg.nodo.riga or "?"
        return risultato

    def chiama_funzione(self, fu, args, nodo):
        decl = fu.decl
        if decl.esterna:
            raise errore("esecuzione", f"{decl.nome} e' una funzione esterna ({decl.esterna}): il prototipo non la "
                                       f"puo' ancora chiamare", nodo)
        parametri = {p.nome: p for p in decl.parametri}
        assegnati = {}
        posizionali = [a for a in args if not a.nome]
        if len(posizionali) > len(decl.parametri):
            raise errore("tipo", f"{decl.nome} vuole {len(decl.parametri)} argomenti, ne ha ricevuti {len(args)}", nodo)
        for p, a in zip(decl.parametri, posizionali):
            assegnati[p.nome] = a
        for a in args:
            if a.nome:
                if a.nome not in parametri:
                    raise errore("tipo", f"{decl.nome} non ha il parametro {a.nome}", nodo, forse(a.nome, parametri))
                if a.nome in assegnati:
                    raise errore("tipo", f"parametro {a.nome} assegnato due volte", nodo)
                assegnati[a.nome] = a
        mancanti = [p for p in parametri if p not in assegnati]
        if mancanti:
            raise errore("tipo", f"{decl.nome}: mancano gli argomenti {', '.join(mancanti)}", nodo)

        for effetto in decl.effetti:
            self.richiedi_effetto(effetto.base, nodo, f"la chiamata a {decl.nome}")

        amb = Ambiente()
        for p in decl.parametri:
            a = assegnati[p.nome]
            # Un valore temporaneo (non una variabile) non ha altri proprietari: si puo' consumare senza take.
            espressione = getattr(a.nodo, "valore", None)
            temporaneo = p.modo == "take" and a.modo is None and not isinstance(espressione, A.Nome)
            if p.modo != a.modo and not temporaneo:
                testo = mostra(espressione) if isinstance(espressione, A.Nodo) else p.nome
                atteso = f"scrivi {p.modo} {testo}" if p.modo else f"togli {a.modo}"
                raise errore("proprieta", f"il parametro {p.nome} di {decl.nome} e' "
                                          f"{p.modo or 'in sola lettura'}", nodo, atteso)
            self.controlla_tipo(a.valore, p.tipo, decl.generici, nodo, f"{decl.nome}, parametro {p.nome}", fu.modulo)
            if p.modo == "edit":
                amb.nomi[p.nome] = a.cella
            else:
                amb.definisci(p.nome, a.valore, mutabile=(p.modo == "take"))

        contesto = Contesto(frozenset(e.base for e in decl.effetti), fu.modulo, f"fn {decl.nome}", decl,
                            self.contesto.permessi_fs)
        with self.in_contesto(contesto):
            for condizione in decl.richiede:
                self.controlla_contratto(condizione, amb.figlio(), "requires", decl, nodo)
            try:
                self.esegui_blocco(decl.corpo, amb)
                if decl.ritorno is not None:
                    raise errore("tipo", f"{decl.nome} termina senza return", decl,
                                 f"aggiungi return alla fine di {decl.nome}")
                risultato = None
            except SegnaleRitorno as s:
                risultato = s.valore
            except (SegnaleInterrompi, SegnaleContinua):
                raise errore("sintassi", "break o continue fuori da un ciclo", decl) from None
            if decl.ritorno is None and risultato is not None:
                raise errore("tipo", f"{decl.nome} non dichiara un tipo di ritorno ma restituisce un valore", decl)
            self.controlla_tipo(risultato, decl.ritorno, decl.generici, nodo, f"valore restituito da {decl.nome}", fu.modulo)
            if decl.garantisce:
                amb_dopo = amb.figlio()
                amb_dopo.definisci("result", risultato)
                for condizione in decl.garantisce:
                    self.controlla_contratto(condizione, amb_dopo.figlio(), "ensures", decl, nodo)
        return risultato

    def controlla_contratto(self, condizione, amb, clausola, decl, nodo):
        esito = self.valuta(condizione, amb)
        if not isinstance(esito, bool):
            raise errore("tipo", f"{clausola} di {decl.nome} deve essere bool", condizione)
        if not esito:
            raise errore("contratto", f"{decl.nome}: {clausola} violata: {mostra(condizione)}", nodo,
                         "chi chiama deve rispettare requires" if clausola == "requires"
                         else f"il corpo di {decl.nome} non rispetta ensures")

    # ----- istruzioni -----

    def esegui_blocco(self, istruzioni, amb):
        for istruzione in istruzioni:
            self.esegui(istruzione, amb)

    def esegui(self, n, amb):
        metodo = getattr(self, "esegui_" + type(n).__name__)
        return metodo(n, amb)

    def esegui_Let(self, n, amb):
        self.lega(n, amb, mutabile=False)

    def esegui_Var(self, n, amb):
        valore = self.valuta(n.valore, amb)
        self.controlla_tipo(valore, n.tipo, self.generici(), n, f"var {n.nome}")
        amb.definisci(n.nome, V.copia(valore), mutabile=True)

    def lega(self, n, amb, mutabile):
        valore = self.valuta(n.valore, amb)
        self.controlla_tipo(valore, n.tipo, self.generici(), n, "let")
        legami = self.confronta_schema(n.schema, valore, n)
        if legami is None:
            raise errore("tipo", f"lo schema {mostra_schema(n.schema)} non corrisponde a {V.formatta(valore, True)}",
                         n, "usa match per i valori che possono avere forme diverse")
        for nome, v in legami.items():
            amb.definisci(nome, V.copia(v), mutabile)

    def generici(self):
        f = self.contesto.funzione
        return f.generici if f is not None else []

    def esegui_Assegna(self, n, amb):
        if n.op == "=":
            nuovo = self.valuta(n.valore, amb)
        else:
            nuovo = self.aritmetica(n.op[0], self.valuta(n.bersaglio, amb), self.valuta(n.valore, amb), n)
        self.assegna(n.bersaglio, V.copia(nuovo), amb, n)

    def radice_modificabile(self, bersaglio, amb, nodo):
        base = bersaglio
        while isinstance(base, (A.Campo, A.Indice)):
            base = base.oggetto
        if not isinstance(base, A.Nome):
            raise errore("proprieta", "si puo' modificare solo cio' che parte da una variabile", nodo)
        cella = amb.cerca(base.nome)
        if cella is None:
            raise errore("proprieta", f"'{base.nome}' non e' una variabile locale e non si puo' modificare", nodo)
        self.cerca_nome(base.nome, amb, nodo)
        if not cella.mutabile:
            raise errore("proprieta", f"'{base.nome}' non e' modificabile", nodo,
                         "dichiarala con var, o ricevila con edit")
        return cella

    def assegna(self, bersaglio, valore, amb, nodo):
        cella = self.radice_modificabile(bersaglio, amb, nodo)
        if isinstance(bersaglio, A.Nome):
            vecchio = cella.valore
            if not V.stessa_specie(vecchio, valore):
                raise errore("tipo", f"'{bersaglio.nome}' contiene {V.nome_tipo(vecchio)}, non {V.nome_tipo(valore)}", nodo)
            cella.valore = valore
        elif isinstance(bersaglio, A.Campo):
            oggetto = self.valuta(bersaglio.oggetto, amb)
            if not isinstance(oggetto, V.Struttura) or bersaglio.nome not in oggetto.campi:
                raise errore("tipo", f"{V.nome_tipo(oggetto)} non ha il campo {bersaglio.nome}", nodo)
            if not V.stessa_specie(oggetto.campi[bersaglio.nome], valore):
                raise errore("tipo", f"il campo {bersaglio.nome} contiene "
                                     f"{V.nome_tipo(oggetto.campi[bersaglio.nome])}, non {V.nome_tipo(valore)}", nodo)
            oggetto.campi[bersaglio.nome] = valore
        else:
            lista = self.valuta(bersaglio.oggetto, amb)
            indice = self.valuta(bersaglio.indice, amb)
            self.controlla_indice(lista, indice, nodo)
            lista[indice] = valore

    def esegui_Espressione(self, n, amb):
        valore = self.valuta(n.espressione, amb)
        if isinstance(valore, V.ValoreVariante) and valore.tipo == "Result":
            raise errore("tipo", f"il Result di {mostra(n.espressione)} viene ignorato", n,
                         "gestiscilo con ?, con match o con unwrap_or")

    def esegui_Ritorna(self, n, amb):
        raise SegnaleRitorno(self.valuta(n.valore, amb) if n.valore is not None else None)

    def esegui_Interrompi(self, n, amb):
        raise SegnaleInterrompi()

    def esegui_Continua(self, n, amb):
        raise SegnaleContinua()

    def condizione(self, espressione, amb, chi):
        valore = self.valuta(espressione, amb)
        if not isinstance(valore, bool):
            raise errore("tipo", f"la condizione di {chi} deve essere bool, non {V.nome_tipo(valore)}", espressione)
        return valore

    def esegui_Se(self, n, amb):
        for condizione, blocco in n.rami:
            ambito = amb.figlio()
            if self.condizione(condizione, ambito, "if"):
                self.esegui_blocco(blocco, ambito)
                return
        if n.altrimenti is not None:
            self.esegui_blocco(n.altrimenti, amb.figlio())

    def elementi(self, iterabile, nodo):
        if isinstance(iterabile, list):
            return [V.copia(x) for x in iterabile]
        if isinstance(iterabile, V.Intervallo):
            return range(iterabile.inizio, iterabile.fine)
        if isinstance(iterabile, str):
            return list(iterabile)
        raise errore("tipo", f"non si puo' scorrere un valore di tipo {V.nome_tipo(iterabile)}", nodo)

    def esegui_Per(self, n, amb):
        for elemento in self.elementi(self.valuta(n.iterabile, amb), n):
            ambito = amb.figlio()
            legami = self.confronta_schema(n.schema, elemento, n)
            if legami is None:
                raise errore("tipo", f"lo schema {mostra_schema(n.schema)} non corrisponde a {V.formatta(elemento, True)}", n)
            for nome, v in legami.items():
                ambito.definisci(nome, v)
            try:
                self.esegui_blocco(n.corpo, ambito)
            except SegnaleContinua:
                continue
            except SegnaleInterrompi:
                break

    def esegui_Mentre(self, n, amb):
        while True:
            ambito = amb.figlio()
            if not self.condizione(n.condizione, ambito, "while"):
                break
            try:
                self.esegui_blocco(n.corpo, ambito)
            except SegnaleContinua:
                continue
            except SegnaleInterrompi:
                break

    def esegui_Scegli(self, n, amb):
        soggetto = self.valuta(n.soggetto, amb)
        for caso in n.casi:
            legami = self.confronta_schema(caso.schema, soggetto, caso)
            if legami is None:
                continue
            ambito = amb.figlio()
            for nome, v in legami.items():
                ambito.definisci(nome, v)
            if caso.guardia is not None and not self.condizione(caso.guardia, ambito, "case ... if"):
                continue
            self.esegui_blocco(caso.corpo, ambito)
            return
        raise errore("esecuzione", f"nessun case corrisponde a {V.formatta(soggetto, True)}", n,
                     "aggiungi un case per questo valore o case _")

    def esegui_NonSicuro(self, n, amb):
        if self.contesto.modulo.ast.profilo != "kernel":
            raise errore("sicurezza", "unsafe e' ammesso solo nei moduli con profile: kernel", n)
        self.esegui_blocco(n.corpo, amb)

    # ----- schemi -----

    def confronta_schema(self, schema, valore, nodo):
        """Restituisce i legami {nome: valore} oppure None se lo schema non corrisponde."""
        if isinstance(schema, A.SchemaNome):
            return {schema.nome: valore}
        if isinstance(schema, A.SchemaJolly):
            return {}
        if isinstance(schema, A.SchemaLetterale):
            atteso = self.valuta(schema.valore, Ambiente())
            return {} if V.stessa_specie(atteso, valore) and V.uguali(atteso, valore, nodo) else None
        if isinstance(schema, A.SchemaTupla):
            if not isinstance(valore, tuple) or len(valore) != len(schema.elementi):
                return None
            return self.confronta_tutti(schema.elementi, valore, nodo)
        # Variante, nuovo tipo o struttura
        if isinstance(valore, V.ValoreVariante):
            if valore.nome != schema.nome or (schema.tipo and schema.tipo != valore.tipo):
                return None
            if not schema.argomenti:
                return {}
            if len(schema.argomenti) != len(valore.valori):
                raise errore("tipo", f"{schema.nome} ha {len(valore.valori)} campi, lo schema ne indica "
                                     f"{len(schema.argomenti)}", nodo)
            return self.confronta_tutti(schema.argomenti, valore.valori, nodo)
        if isinstance(valore, V.NuovoTipo) and valore.tipo == schema.nome and len(schema.argomenti) == 1:
            return self.confronta_schema(schema.argomenti[0], valore.valore, nodo)
        if isinstance(valore, V.Struttura) and valore.tipo == schema.nome:
            return self.confronta_tutti(schema.argomenti, list(valore.campi.values()), nodo) if schema.argomenti else {}
        return None

    def confronta_tutti(self, schemi, valori, nodo):
        legami = {}
        for s, v in zip(schemi, valori):
            parziali = self.confronta_schema(s, v, nodo)
            if parziali is None:
                return None
            legami.update(parziali)
        return legami

    # ----- espressioni -----

    def valuta(self, n, amb):
        return getattr(self, "valuta_" + type(n).__name__)(n, amb)

    def valuta_Letterale(self, n, amb):
        return n.valore

    def valuta_Testo(self, n, amb):
        return "".join(p if isinstance(p, str) else V.formatta(self.valuta(p, amb), nodo=n) for p in n.parti)

    def valuta_Nome(self, n, amb):
        return self.cerca_nome(n.nome, amb, n)

    def valuta_NomeTipo(self, n, amb):
        return self.cerca_tipo(n.nome, n)

    def valuta_Risultato(self, n, amb):
        cella = amb.cerca("result")
        if cella is None:
            raise errore("nome", "result si usa solo dentro ensures", n)
        return cella.valore

    def valuta_Lista(self, n, amb):
        valori = [V.copia(self.valuta(e, amb)) for e in n.elementi]
        for v in valori[1:]:
            if not V.stessa_specie(valori[0], v):
                raise errore("tipo", f"una lista contiene un solo tipo: {V.nome_tipo(valori[0])} e {V.nome_tipo(v)}", n)
        return valori

    def valuta_Tupla(self, n, amb):
        return tuple(V.copia(self.valuta(e, amb)) for e in n.elementi)

    def valuta_Lambda(self, n, amb):
        return Chiusura(n, amb, self.contesto)

    def valuta_Intervallo(self, n, amb):
        inizio, fine = self.valuta(n.inizio, amb), self.valuta(n.fine, amb)
        for x in (inizio, fine):
            if isinstance(x, bool) or not isinstance(x, int):
                raise errore("tipo", f"un intervallo vuole interi, non {V.nome_tipo(x)}", n)
        return V.Intervallo(inizio, fine)

    def valuta_Negativo(self, n, amb):
        v = self.valuta(n.espressione, amb)
        if isinstance(v, bool):
            raise errore("tipo", "il segno meno non si applica a bool", n, "usa not")
        if isinstance(v, int):
            return self.controlla_intero(-v, n)
        if isinstance(v, float):
            return -v
        if isinstance(v, V.NuovoTipo):
            interno = self.controlla_intero(-v.valore, n) if isinstance(v.valore, int) else -v.valore
            return V.NuovoTipo(v.tipo, interno)
        raise errore("tipo", f"il segno meno non si applica a {V.nome_tipo(v)}", n)

    def valuta_Binaria(self, n, amb):
        return self.aritmetica(n.op, self.valuta(n.sinistra, amb), self.valuta(n.destra, amb), n)

    def aritmetica(self, op, a, b, nodo):
        if op == "@":
            raise errore("esecuzione", "l'operatore @ (matrici) non e' ancora supportato dal prototipo", nodo)
        if isinstance(a, str) or isinstance(b, str):
            raise errore("tipo", f"l'operatore {op} non si applica alle stringhe", nodo,
                         'per comporre testo usa l\'interpolazione: "{a}{b}"' if op == "+" else None)
        if isinstance(a, V.NuovoTipo) or isinstance(b, V.NuovoTipo):
            return self.aritmetica_nuovo_tipo(op, a, b, nodo)
        if isinstance(a, bool) or isinstance(b, bool):
            raise errore("tipo", f"l'operatore {op} non si applica a bool", nodo)
        if isinstance(a, int) and isinstance(b, int):
            return self.controlla_intero(self.intera(op, a, b, nodo), nodo)
        if isinstance(a, float) and isinstance(b, float):
            if op in "/%" and b == 0.0:
                raise errore("esecuzione", "divisione per zero", nodo)
            return {"+": a + b, "-": a - b, "*": a * b}.get(op) if op in "+-*" else (a / b if op == "/" else _fmod(a, b))
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            raise errore("tipo", f"{V.nome_tipo(a)} {op} {V.nome_tipo(b)}: interi e decimali non si mescolano", nodo,
                         "converti con to_f64() o to_int()")
        raise errore("tipo", f"l'operatore {op} non si applica a {V.nome_tipo(a)} e {V.nome_tipo(b)}", nodo)

    @staticmethod
    def intera(op, a, b, nodo):
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if b == 0:
            raise errore("esecuzione", "divisione per zero", nodo, "controlla il divisore con requires o con if")
        quoziente = abs(a) // abs(b) * (1 if (a >= 0) == (b >= 0) else -1)   # troncamento verso zero
        return quoziente if op == "/" else a - b * quoziente

    def aritmetica_nuovo_tipo(self, op, a, b, nodo):
        if isinstance(a, V.NuovoTipo) and isinstance(b, V.NuovoTipo):
            if a.tipo != b.tipo:
                raise errore("tipo", f"{a.tipo} {op} {b.tipo}: tipi diversi", nodo)
            if op not in "+-%":
                raise errore("tipo", f"{a.tipo} {op} {b.tipo} non ha senso", nodo, f"moltiplica {a.tipo} per un numero")
            return V.NuovoTipo(a.tipo, self.aritmetica(op, a.valore, b.valore, nodo))
        if isinstance(a, V.NuovoTipo) and op in "*/%":
            return V.NuovoTipo(a.tipo, self.aritmetica(op, a.valore, b, nodo))
        if isinstance(b, V.NuovoTipo) and op == "*":
            return V.NuovoTipo(b.tipo, self.aritmetica(op, a, b.valore, nodo))
        tipo = a.tipo if isinstance(a, V.NuovoTipo) else b.tipo
        raise errore("tipo", f"{V.nome_tipo(a)} {op} {V.nome_tipo(b)}: un {tipo} si somma solo a un altro {tipo}",
                     nodo, f"scrivi {tipo}(...) intorno al numero")

    def valuta_Confronto(self, n, amb):
        a, b = self.valuta(n.sinistra, amb), self.valuta(n.destra, amb)
        if n.op == "==":
            return V.uguali(a, b, n)
        if n.op == "!=":
            return not V.uguali(a, b, n)
        if n.op == "in":
            if isinstance(b, list):
                return any(V.stessa_specie(a, x) and V.uguali(a, x, n) for x in b)
            if isinstance(b, str) and isinstance(a, str):
                return a in b
            if isinstance(b, V.Intervallo) and isinstance(a, int) and not isinstance(a, bool):
                return b.inizio <= a < b.fine
            raise errore("tipo", f"in non si applica a {V.nome_tipo(a)} e {V.nome_tipo(b)}", n)
        if not V.stessa_specie(a, b):
            raise errore("tipo", f"confronto tra {V.nome_tipo(a)} e {V.nome_tipo(b)}", n,
                         "converti esplicitamente uno dei due valori")
        x, y = (a.valore, b.valore) if isinstance(a, V.NuovoTipo) else (a, b)
        if isinstance(x, bool) or not isinstance(x, (int, float, str)):
            raise errore("tipo", f"{n.op} non si applica a {V.nome_tipo(a)}", n)
        return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[n.op]

    def valuta_Logica(self, n, amb):
        for operando in n.operandi:
            v = self.valuta(operando, amb)
            if not isinstance(v, bool):
                raise errore("tipo", f"{n.op} vuole bool, non {V.nome_tipo(v)}", operando)
            if n.op == "and" and not v:
                return False
            if n.op == "or" and v:
                return True
        return n.op == "and"

    def valuta_Non(self, n, amb):
        v = self.valuta(n.espressione, amb)
        if not isinstance(v, bool):
            raise errore("tipo", f"not vuole bool, non {V.nome_tipo(v)}", n)
        return not v

    def valuta_Implica(self, n, amb):
        premessa = self.valuta(n.premessa, amb)
        if not isinstance(premessa, bool):
            raise errore("tipo", "implies vuole bool", n)
        if not premessa:
            return True
        conseguenza = self.valuta(n.conseguenza, amb)
        if not isinstance(conseguenza, bool):
            raise errore("tipo", "implies vuole bool", n)
        return conseguenza

    def valuta_ProvaSchema(self, n, amb):
        legami = self.confronta_schema(n.schema, self.valuta(n.espressione, amb), n)
        if legami is None:
            return False
        for nome, v in legami.items():
            amb.definisci(nome, v)
        return True

    def valuta_Propaga(self, n, amb):
        v = self.valuta(n.espressione, amb)
        if not isinstance(v, V.ValoreVariante) or v.tipo not in ("Result", "Option"):
            raise errore("tipo", f"? si applica a Result o Option, non a {V.nome_tipo(v)}", n)
        funzione = self.contesto.funzione
        ritorno = getattr(getattr(funzione, "ritorno", None), "nome", None)
        if funzione is None or ritorno != v.tipo:
            raise errore("tipo", f"? su un {v.tipo} si usa solo in una funzione che restituisce {v.tipo}", n)
        if v.nome in ("Ok", "Some"):
            return v.valori[0]
        raise SegnaleRitorno(v)

    def valuta_Campo(self, n, amb):
        oggetto = self.valuta(n.oggetto, amb)
        if isinstance(oggetto, V.Struttura) and n.nome in oggetto.campi:
            return oggetto.campi[n.nome]
        if isinstance(oggetto, V.ValoreVariante) and n.nome in oggetto.nomi_campi:
            return oggetto.valori[oggetto.nomi_campi.index(n.nome)]
        if n.nome in METODI.get(specie_metodo(oggetto), {}):
            raise errore("nome", f"{n.nome} e' un metodo", n, f"scrivi {mostra(n)}()")
        raise errore("nome", f"{V.nome_tipo(oggetto)} non ha il campo {n.nome}", n)

    def valuta_Variante(self, n, amb):
        info = self.valuta(n.oggetto, amb)
        if not isinstance(info, InfoSomma):
            raise errore("tipo", f"{mostra(n.oggetto)} non e' un tipo con varianti", n)
        return info.variante(n.nome, n)

    def controlla_indice(self, lista, indice, nodo):
        if not isinstance(lista, (list, tuple)):
            raise errore("tipo", f"non si indicizza un valore di tipo {V.nome_tipo(lista)}", nodo,
                         "per le stringhe usa chars()" if isinstance(lista, str) else None)
        if isinstance(indice, bool) or not isinstance(indice, int):
            raise errore("tipo", f"l'indice deve essere intero, non {V.nome_tipo(indice)}", nodo)
        if not 0 <= indice < len(lista):
            raise errore("esecuzione", f"indice {indice} fuori dai limiti (lunghezza {len(lista)})", nodo,
                         "usa get(i), che restituisce Option")

    def valuta_Indice(self, n, amb):
        lista, indice = self.valuta(n.oggetto, amb), self.valuta(n.indice, amb)
        self.controlla_indice(lista, indice, n)
        return lista[indice]

    def valuta_Chiamata(self, n, amb):
        if isinstance(n.funzione, A.Campo):
            return self.chiama_metodo(n.funzione, n.argomenti, amb, n)
        funzione = self.valuta(n.funzione, amb)
        return self.invoca(funzione, self.valuta_argomenti(n.argomenti, amb), n)

    def funzione_utente(self, nome):
        m = self.contesto.modulo
        if nome in m.funzioni:
            return m.funzioni[nome]
        oggetto = m.importati.get(nome, (None, None))[1]
        return oggetto if isinstance(oggetto, FunzioneUtente) else None

    def chiama_metodo(self, campo, argomenti, amb, nodo):
        nome = campo.nome
        # Chiamata con il punto a una funzione dell'utente: x.f(a) e' f(x, a).
        fu = self.funzione_utente(nome)
        if fu is not None:
            primo = fu.decl.parametri[0] if fu.decl.parametri else None
            if primo is not None and primo.modo:
                raise errore("proprieta", f"il primo parametro di {nome} e' {primo.modo}: la chiamata con il punto "
                                          f"non e' ammessa", nodo, f"scrivi {nome}({primo.modo} {mostra(campo.oggetto)}, ...)")
            ricevente = ArgValutato(None, None, self.valuta(campo.oggetto, amb), None, nodo)
            return fu.chiama(self, [ricevente] + self.valuta_argomenti(argomenti, amb), nodo)
        ricevente = self.valuta(campo.oggetto, amb)
        specie = specie_metodo(ricevente)
        args = self.valuta_argomenti(argomenti, amb)
        if any(a.nome or a.modo for a in args):
            raise errore("tipo", f"il metodo {nome} accetta solo argomenti semplici", nodo)
        valori = [a.valore for a in args]
        if nome in METODI_MUTANTI.get(specie, {}):
            self.radice_modificabile(campo.oggetto, amb, nodo)
            arieta, impl = METODI_MUTANTI[specie][nome]
        elif nome in METODI.get(specie, {}):
            arieta, impl = METODI[specie][nome]
        else:
            tutti = list(METODI.get(specie, {})) + list(METODI_MUTANTI.get(specie, {}))
            raise errore("nome", f"{specie} non ha il metodo {nome}", nodo, forse(nome, tutti))
        if len(valori) != arieta:
            raise errore("tipo", f"{nome} vuole {arieta} argomenti, ne ha ricevuti {len(valori)}", nodo)
        return impl(self, ricevente, valori, nodo)

    # ----- punti d'ingresso -----

    def esegui_programma(self):
        """Esegue il process del modulo principale, oppure fn main()."""
        m = self.programma.principale
        if len(m.processi) > 1:
            raise ErroreTessera("esecuzione", "il modulo ha piu' di un process", file=m.file)
        if m.processi:
            return self.esegui_processo(next(iter(m.processi.values())))
        if "main" in m.funzioni:
            main = m.funzioni["main"]
            effetti = frozenset(e.base for e in main.decl.effetti)
            with self.in_contesto(Contesto(effetti, m, "l'avvio del programma")):
                return main.chiama(self, [], main.decl)
        raise ErroreTessera("esecuzione", "nessun punto d'ingresso", file=m.file,
                            suggerimento="aggiungi un process o una fn main()")

    def esegui_processo(self, proc):
        from .sentinel import controlla_piattaforma
        controlla_piattaforma(proc)
        m = self.programma.principale
        permessi = []
        with self.in_contesto(Contesto(frozenset(), m, f"process {proc.nome}")):
            for permesso in proc.permessi:
                if permesso.nome == "fs.read":
                    if len(permesso.argomenti) != 1:
                        raise errore("tipo", "fs.read vuole un percorso", permesso)
                    permessi.append(self.valuta(permesso.argomenti[0].valore, Ambiente()))
        effetti = frozenset(e.base for e in proc.effetti)
        contesto = Contesto(effetti, m, f"process {proc.nome}", None, permessi)
        with self.in_contesto(contesto):
            try:
                self.esegui_blocco(proc.corpo, Ambiente())
            except SegnaleRitorno:
                pass
        return None

    def chiama_per_nome(self, nome, valori):
        """Chiama una funzione del modulo principale (riga di comando e test)."""
        m = self.programma.principale
        if nome not in m.funzioni:
            raise ErroreTessera("nome", f"{m.nome} non ha la funzione {nome}", file=m.file,
                                suggerimento=forse(nome, m.funzioni))
        fu = m.funzioni[nome]
        effetti = frozenset(e.base for e in fu.decl.effetti)
        with self.in_contesto(Contesto(effetti, m, "la riga di comando")):
            return fu.chiama(self, [ArgValutato(None, None, v, None, fu.decl) for v in valori], fu.decl)

    def esegui_esempi(self, modulo=None):
        """Valuta le clausole example: restituisce (funzione, testo, superato, dettaglio)."""
        m = modulo or self.programma.principale
        esiti = []
        for fu in m.funzioni.values():
            effetti = frozenset(e.base for e in fu.decl.effetti)
            for esempio in fu.decl.esempi:
                contesto = Contesto(effetti, m, f"example di {fu.nome}")
                with self.in_contesto(contesto):
                    esiti.append((fu.nome, mostra(esempio)) + self.prova_esempio(esempio))
        return esiti

    def prova_esempio(self, esempio):
        try:
            if isinstance(esempio, A.Confronto) and esempio.op == "==":
                ottenuto = self.valuta(esempio.sinistra, Ambiente())
                atteso = self.valuta(esempio.destra, Ambiente())
                if V.stessa_specie(ottenuto, atteso) and V.uguali(ottenuto, atteso, esempio):
                    return (True, "")
                return (False, f"ottenuto {V.formatta(ottenuto, True)}, atteso {V.formatta(atteso, True)}")
            esito = self.valuta(esempio, Ambiente())
            return (esito is True, "" if esito is True else f"vale {V.formatta(esito, True)}")
        except ErroreTessera as e:
            return (False, str(e))


def _fmod(a, b):
    import math
    return math.fmod(a, b)
