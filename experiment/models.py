# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Chi scrive il codice: un modello Claude oppure le soluzioni di riferimento (per le prove a costo zero)."""
from dataclasses import dataclass, field

from . import references

MODELLO_PREDEFINITO = "claude-opus-5-5"

# Prezzi in dollari per milione di token: ingresso, uscita, lettura e scrittura della cache.
PREZZI = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-fable-5-1": (10.00, 50.00, 0.25, 12.50),
}


@dataclass
class Risposta:
    testo: str
    contenuto: object = None            # blocchi della risposta, da rimandare tali e quali nella conversazione
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0
    modello: str = ""
    rifiutata: bool = False
    fallback: bool = False
    note: list = field(default_factory=list)


class ModelloClaude:
    def __init__(self, modello=MODELLO_PREDEFINITO, sforzo="high", fallback=True, max_tokens=16000):
        import anthropic
        self.anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.modello = modello
        self.sforzo = sforzo
        # Claude Haiku 5.5 non ha fallback lato server.
        self.fallback = fallback and not modello.startswith("claude-haiku")
        self.max_tokens = max_tokens

    def rispondi(self, sistema, messaggi, **_):
        parametri = dict(
            model=self.modello,
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
            messages=messaggi,
            output_config={"effort": self.sforzo},
        )
        if self.fallback:
            risposta = self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                        fallbacks="default", **parametri)
        else:
            risposta = self.client.messages.create(**parametri)
        uso = risposta.usage
        iterazioni = getattr(uso, "iterations", None) or []
        esito = Risposta(
            testo="",
            contenuto=risposta.content,
            input_tokens=uso.input_tokens or 0,
            output_tokens=uso.output_tokens or 0,
            cache_read=getattr(uso, "cache_read_input_tokens", 0) or 0,
            cache_write=getattr(uso, "cache_creation_input_tokens", 0) or 0,
            modello=risposta.model,
            fallback=any(getattr(i, "type", "") == "fallback_message" for i in iterazioni),
        )
        if risposta.stop_reason == "refusal":
            esito.rifiutata = True
            dettagli = getattr(risposta, "stop_details", None)
            esito.note.append(f"refusal: {getattr(dettagli, 'category', None)}")
            return esito
        if risposta.stop_reason == "max_tokens":
            esito.note.append("max_tokens reached")
        esito.testo = "".join(b.text for b in risposta.content if b.type == "text")
        return esito


class ModelloRiferimento:
    """Restituisce le soluzioni di riferimento. Con sbaglia_prima=True il primo tentativo contiene un errore
    di sintassi, per provare anche il ciclo di correzione."""

    def __init__(self, sbaglia_prima=False):
        self.modello = "reference-broken" if sbaglia_prima else "reference"
        self.sbaglia_prima = sbaglia_prima

    def rispondi(self, sistema, messaggi, task=None, lingua=None, tentativo=1):
        codice = (references.TESSERA if lingua == "tessera" else references.PYTHON)[task["id"]]
        if self.sbaglia_prima and tentativo == 1:
            codice = codice.replace("end fn", "end fun", 1) if lingua == "tessera" else codice + "\ndef broken(:\n"
        blocco = "tessera" if lingua == "tessera" else "python"
        testo = f"```{blocco}\n{codice.strip()}\n```"
        return Risposta(testo=testo, contenuto=testo, modello=self.modello)


def costo(modello, input_tokens, output_tokens, cache_read, cache_write):
    prezzi = PREZZI.get(modello)
    if prezzi is None:
        return None
    ingresso, uscita, lettura, scrittura = prezzi
    return (input_tokens * ingresso + output_tokens * uscita + cache_read * lettura + cache_write * scrittura) / 1e6
