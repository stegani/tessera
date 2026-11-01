"""Errori di Tessera in forma strutturata: leggibili da una persona e da un modello."""
import json


class ErroreTessera(Exception):
    """Ogni errore ha un tipo, un messaggio, una posizione e, se possibile, un suggerimento.

    Tipi: sintassi, nome, tipo, effetti, contratto, proprieta, esecuzione, compilatore.
    """

    def __init__(self, tipo, messaggio, riga=None, colonna=None, file=None, suggerimento=None):
        super().__init__(messaggio)
        self.tipo = tipo
        self.messaggio = messaggio
        self.riga = riga
        self.colonna = colonna
        self.file = file
        self.suggerimento = suggerimento

    def in_dizionario(self):
        dati = {"tipo": self.tipo, "messaggio": self.messaggio}
        for chiave in ("file", "riga", "colonna", "suggerimento"):
            valore = getattr(self, chiave)
            if valore is not None:
                dati[chiave] = valore
        return dati

    def in_json(self):
        return json.dumps(self.in_dizionario(), ensure_ascii=False)

    def __str__(self):
        posizione = ""
        if self.file:
            posizione += self.file
        if self.riga:
            posizione += f":{self.riga}"
        testo = f"{posizione}: " if posizione else ""
        testo += f"errore di {self.tipo}: {self.messaggio}"
        if self.suggerimento:
            testo += f" (suggerimento: {self.suggerimento})"
        return testo


def errore(tipo, messaggio, nodo=None, suggerimento=None):
    """Crea un errore prendendo la riga dal nodo, se c'e'."""
    return ErroreTessera(tipo, messaggio, riga=getattr(nodo, "riga", None) or None, suggerimento=suggerimento)
