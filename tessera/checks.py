# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Controlli statici, prima dell'esecuzione: restituiscono tutti gli errori trovati, non solo il primo.

- effetti: ogni chiamata diretta usa solo effetti dichiarati dal chiamante;
- nomi: ogni nome usato e' definito;
- proprieta': niente assegnazioni a let o a parametri in sola lettura, niente uso dopo take;
- match: un tipo somma, Option o Result e' coperto in tutte le varianti (o da case _);
- varie: ? solo in funzioni che restituiscono Result o Option, break fuori dai cicli, unsafe fuori da kernel.
"""
from . import ast as A
from .errors import ErroreTessera
from .interpreter import FunzioneUtente, InfoSomma, INCORPORATI
from .library import GLOBALI, METODI_MUTANTI

MUTANTI = {nome for metodi in METODI_MUTANTI.values() for nome in metodi}
VARIANTI_INCORPORATE = {"Some": "Option", "None": "Option", "Ok": "Result", "Err": "Result"}
INSIEMI_INCORPORATI = {"Option": {"Some", "None"}, "Result": {"Ok", "Err"}}


class Ambito:
    def __init__(self, genitore=None, ciclo=False):
        self.nomi = {}                  # nome -> "let", "var", "edit", "take", "lettura"
        self.genitore = genitore
        self.ciclo = ciclo

    def cerca(self, nome):
        a = self
        while a:
            if nome in a.nomi:
                return a, a.nomi[nome]
            a = a.genitore
        return None, None

    def in_ciclo_dopo(self, ambito_dichiarazione):
        """Vero se tra questo ambito e quello della dichiarazione c'e' un ciclo."""
        a = self
        while a and a is not ambito_dichiarazione:
            if a.ciclo:
                return True
            a = a.genitore
        return False


class Controllore:
    def __init__(self, ctx):
        self.ctx = ctx
        self.errori = []
        self.decl = None
        self.effetti = set()
        self.descrizione = ""
        self.spostati = {}              # id(ambito) + nome -> riga del take

    def segnala(self, tipo, messaggio, nodo, suggerimento=None):
        self.errori.append(ErroreTessera(tipo, messaggio, riga=getattr(nodo, "riga", None) or None,
                                         file=self.ctx.file, suggerimento=suggerimento))

    # ---------- dichiarazioni ----------

    def controlla(self):
        for d in self.ctx.ast.dichiarazioni:
            if isinstance(d, A.Funzione) and d.corpo is not None:
                self.funzione(d)
            elif isinstance(d, A.Processo):
                self.processo(d)
        return self.errori

    def funzione(self, d):
        self.decl, self.descrizione = d, f"fn {d.nome}"
        self.effetti = {e.base for e in d.effetti}
        ambito = Ambito()
        for p in d.parametri:
            ambito.nomi[p.nome] = p.modo or "lettura"
        for condizione in d.richiede:
            self.espressione(condizione, Ambito(ambito))
        self.blocco(d.corpo, ambito)
        dopo = Ambito(ambito)
        dopo.nomi["result"] = "let"
        for condizione in d.garantisce:
            self.espressione(condizione, Ambito(dopo))
        for esempio in d.esempi:
            self.espressione(esempio, Ambito())
        if d.ritorno is not None and not self.termina(d.corpo):
            self.segnala("tipo", f"{d.nome} puo' terminare senza return", d, f"aggiungi return alla fine di {d.nome}")

    def processo(self, p):
        self.decl, self.descrizione = None, f"process {p.nome}"
        self.effetti = {e.base for e in p.effetti}
        self.blocco(p.corpo, Ambito())

    def termina(self, blocco):
        """Vero se ogni percorso del blocco finisce con return."""
        if not blocco:
            return False
        ultima = blocco[-1]
        if isinstance(ultima, A.Ritorna):
            return True
        if isinstance(ultima, A.Se):
            return ultima.altrimenti is not None and all(self.termina(b) for _, b in ultima.rami) and \
                self.termina(ultima.altrimenti)
        if isinstance(ultima, A.Scegli):
            return all(self.termina(c.corpo) for c in ultima.casi)
        return False

    # ---------- istruzioni ----------

    def blocco(self, istruzioni, ambito):
        for i in istruzioni:
            self.istruzione(i, ambito)

    def istruzione(self, n, amb):
        if isinstance(n, A.Let):
            self.espressione(n.valore, amb)
            for nome in self.nomi_schema(n.schema):
                amb.nomi[nome] = "let"
                self.spostati.pop((id(amb), nome), None)
        elif isinstance(n, A.Var):
            self.espressione(n.valore, amb)
            amb.nomi[n.nome] = "var"
            self.spostati.pop((id(amb), n.nome), None)
        elif isinstance(n, A.Assegna):
            self.espressione(n.valore, amb)
            if not isinstance(n.bersaglio, A.Nome):
                self.espressione(n.bersaglio, amb)
            self.modificabile(n.bersaglio, amb, n)
            if isinstance(n.bersaglio, A.Nome) and n.op == "=":
                proprietario, _ = amb.cerca(n.bersaglio.nome)
                if proprietario is not None:
                    self.spostati.pop((id(proprietario), n.bersaglio.nome), None)
        elif isinstance(n, A.Espressione):
            self.espressione(n.espressione, amb)
        elif isinstance(n, A.Ritorna):
            if n.valore is not None:
                self.espressione(n.valore, amb)
            if self.decl is not None and self.decl.ritorno is None and n.valore is not None:
                self.segnala("tipo", f"{self.decl.nome} non dichiara un tipo di ritorno ma restituisce un valore", n)
            if self.decl is not None and self.decl.ritorno is not None and n.valore is None:
                self.segnala("tipo", f"{self.decl.nome} deve restituire un valore", n)
        elif isinstance(n, (A.Interrompi, A.Continua)):
            a = amb
            while a and not a.ciclo:
                a = a.genitore
            if a is None:
                self.segnala("sintassi", "break o continue fuori da un ciclo", n)
        elif isinstance(n, A.Se):
            for condizione, blocco in n.rami:
                ramo = Ambito(amb)
                self.espressione(condizione, ramo)
                self.blocco(blocco, ramo)
            if n.altrimenti is not None:
                self.blocco(n.altrimenti, Ambito(amb))
        elif isinstance(n, A.Per):
            self.espressione(n.iterabile, amb)
            corpo = Ambito(amb, ciclo=True)
            for nome in self.nomi_schema(n.schema):
                corpo.nomi[nome] = "let"
            self.blocco(n.corpo, corpo)
        elif isinstance(n, A.Mentre):
            corpo = Ambito(amb, ciclo=True)
            self.espressione(n.condizione, corpo)
            self.blocco(n.corpo, corpo)
        elif isinstance(n, A.Scegli):
            self.espressione(n.soggetto, amb)
            for caso in n.casi:
                ramo = Ambito(amb)
                for nome in self.nomi_schema(caso.schema):
                    ramo.nomi[nome] = "let"
                if caso.guardia is not None:
                    self.espressione(caso.guardia, ramo)
                self.blocco(caso.corpo, ramo)
            self.esaustivo(n)
        elif isinstance(n, A.NonSicuro):
            if self.ctx.ast.profilo != "kernel":
                self.segnala("sicurezza", "unsafe e' ammesso solo nei moduli con profile: kernel", n)
            self.blocco(n.corpo, Ambito(amb))

    def modificabile(self, bersaglio, amb, nodo):
        base = bersaglio
        while isinstance(base, (A.Campo, A.Indice)):
            base = base.oggetto
        if not isinstance(base, A.Nome):
            self.segnala("proprieta", "si puo' modificare solo cio' che parte da una variabile", nodo)
            return
        _, specie = amb.cerca(base.nome)
        if specie is None:
            self.segnala("proprieta", f"'{base.nome}' non e' una variabile locale e non si puo' modificare", nodo)
        elif specie not in ("var", "edit", "take"):
            self.segnala("proprieta", f"'{base.nome}' non e' modificabile ({self.spiega(specie)})", nodo,
                         "dichiarala con var, o ricevila con edit")

    @staticmethod
    def spiega(specie):
        return {"let": "dichiarata con let", "lettura": "parametro in sola lettura"}.get(specie, specie)

    # ---------- espressioni ----------

    def espressione(self, n, amb):
        if isinstance(n, A.Nome):
            self.nome(n, amb)
        elif isinstance(n, A.NomeTipo):
            self.nome_tipo(n)
        elif isinstance(n, A.Testo):
            for p in n.parti:
                if not isinstance(p, str):
                    self.espressione(p, amb)
        elif isinstance(n, A.Chiamata):
            self.chiamata(n, amb)
        elif isinstance(n, A.Lambda):
            interno = Ambito(amb)
            for nome, _ in n.parametri:
                interno.nomi[nome] = "let"
            self.espressione(n.corpo, interno)
        elif isinstance(n, A.ProvaSchema):
            self.espressione(n.espressione, amb)
            for nome in self.nomi_schema(n.schema):
                amb.nomi[nome] = "let"
        elif isinstance(n, A.Propaga):
            self.espressione(n.espressione, amb)
            ritorno = getattr(getattr(self.decl, "ritorno", None), "nome", None)
            if ritorno not in ("Result", "Option"):
                self.segnala("tipo", f"? si usa solo in una funzione che restituisce Result o Option "
                                     f"({self.descrizione} restituisce {ritorno or 'niente'})", n,
                             "gestisci il valore con match")
        elif isinstance(n, A.Variante):
            self.espressione(n.oggetto, amb)
        elif isinstance(n, A.Nodo):
            for figlio in vars(n).values():
                for x in (figlio if isinstance(figlio, list) else [figlio]):
                    if isinstance(x, A.Nodo) and not isinstance(x, (A.TipoNominato, A.TipoTupla, A.TipoFunzione)):
                        self.espressione(x, amb)

    def nome(self, n, amb):
        proprietario, specie = amb.cerca(n.nome)
        if specie is not None:
            riga = self.spostati.get((id(proprietario), n.nome))
            if riga:
                self.segnala("proprieta", f"'{n.nome}' e' stato consumato con take alla riga {riga}", n,
                             "non usare piu' il valore dopo take")
            return
        m = self.ctx
        if n.nome in m.costanti or n.nome in m.funzioni or n.nome in m.importati or n.nome in GLOBALI:
            return
        self.segnala("nome", f"'{n.nome}' non e' definito", n)

    def nome_tipo(self, n):
        m = self.ctx
        if n.nome in m.tipi or n.nome in m.importati or n.nome in m.varianti or n.nome in INCORPORATI or n.nome == "None":
            return
        self.segnala("nome", f"tipo o variante '{n.nome}' non definito", n)

    def funzione_chiamata(self, nome):
        m = self.ctx
        if nome in m.funzioni:
            return m.funzioni[nome].decl
        oggetto = m.importati.get(nome, (None, None))[1]
        return oggetto.decl if isinstance(oggetto, FunzioneUtente) else None

    def chiamata(self, n, amb):
        bersaglio = None
        if isinstance(n.funzione, A.Nome):
            proprietario, _ = amb.cerca(n.funzione.nome)
            if proprietario is None:
                bersaglio = n.funzione.nome
            self.espressione(n.funzione, amb)
        elif isinstance(n.funzione, A.Campo):
            self.espressione(n.funzione.oggetto, amb)
            bersaglio = n.funzione.nome
            if bersaglio in MUTANTI and self.funzione_chiamata(bersaglio) is None:
                self.modificabile(n.funzione.oggetto, amb, n)
        else:
            self.espressione(n.funzione, amb)
        for a in n.argomenti:
            self.espressione(a.valore, amb)
            if a.modo == "edit":
                self.modificabile(a.valore, amb, a)
        for a in n.argomenti:
            if a.modo == "take" and isinstance(a.valore, A.Nome):
                proprietario, _ = amb.cerca(a.valore.nome)
                if proprietario is not None:
                    if amb.in_ciclo_dopo(proprietario):
                        self.segnala("proprieta", f"take di '{a.valore.nome}' dentro un ciclo: al giro successivo "
                                                  f"il valore non c'e' piu'", a)
                    self.spostati[(id(proprietario), a.valore.nome)] = a.riga
        if bersaglio is None:
            return
        decl = self.funzione_chiamata(bersaglio)
        if decl is not None:
            for e in decl.effetti:
                self.richiedi(e.base, n, f"la chiamata a {decl.nome}")
        elif bersaglio in GLOBALI and GLOBALI[bersaglio].effetto and isinstance(n.funzione, A.Nome):
            self.richiedi(GLOBALI[bersaglio].effetto, n, bersaglio)

    def richiedi(self, effetto, nodo, chi):
        if effetto not in self.effetti:
            dichiarati = ", ".join(sorted(self.effetti)) or "none"
            self.segnala("effetti", f"{chi} richiede l'effetto '{effetto}', ma {self.descrizione} dichiara "
                                    f"effects: {dichiarati}", nodo, f"aggiungi {effetto} a effects di {self.descrizione}")

    # ---------- schemi e match ----------

    def nomi_schema(self, s):
        if isinstance(s, A.SchemaNome):
            return [s.nome]
        if isinstance(s, A.SchemaTupla):
            return [n for x in s.elementi for n in self.nomi_schema(x)]
        if isinstance(s, A.SchemaVariante):
            return [n for x in s.argomenti for n in self.nomi_schema(x)]
        return []

    def insieme_varianti(self, nome):
        if nome in VARIANTI_INCORPORATE:
            tipo = VARIANTI_INCORPORATE[nome]
            return tipo, INSIEMI_INCORPORATI[tipo]
        info = self.ctx.varianti.get(nome)
        if isinstance(info, InfoSomma):
            return info.nome, set(info.varianti)
        return None, None

    def esaustivo(self, n):
        coperte, tipo, insieme = set(), None, None
        for caso in n.casi:
            s = caso.schema
            if isinstance(s, (A.SchemaJolly, A.SchemaNome)) and caso.guardia is None:
                return
            if not isinstance(s, A.SchemaVariante):
                continue
            t, varianti = self.insieme_varianti(s.nome)
            if t is None:
                return
            tipo, insieme = t, varianti
            # Una variante e' coperta se il caso non ha guardia e non restringe i campi.
            if caso.guardia is None and all(isinstance(x, (A.SchemaNome, A.SchemaJolly)) or
                                            self.copre_tutto(x) for x in s.argomenti):
                coperte.add(s.nome)
        if tipo is None:
            if not any(isinstance(c.schema, (A.SchemaJolly, A.SchemaNome)) for c in n.casi):
                self.segnala("tipo", "match senza case _: i valori non elencati fermano il programma", n,
                             "aggiungi case _ alla fine")
            return
        mancanti = sorted(insieme - coperte)
        if mancanti:
            self.segnala("tipo", f"match su {tipo} non esaustivo: manca {', '.join(mancanti)}", n,
                         f"aggiungi case {mancanti[0]} o case _")

    def copre_tutto(self, s):
        return isinstance(s, (A.SchemaNome, A.SchemaJolly))


def controlla_programma(programma):
    errori = []
    for ctx in programma.moduli.values():
        errori.extend(Controllore(ctx).controlla())
    return errori
