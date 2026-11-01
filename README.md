# Tessera

**Un linguaggio di programmazione scritto dalle IA e blindato contro le IA.**
Effetti dichiarati, contratti verificati, vulnerabilità che non compilano.

> *A programming language written by AI, hardened against AI.*

Le IA scrivono sempre più codice, e le stesse capacità servono a trovarne le falle su scala enorme. Tessera sposta la sicurezza dal programmatore al compilatore: ciò che un'IA può sbagliare o sfruttare deve diventare un errore di compilazione.

```
fn parse_price(text: Str) -> Result[Cents, ParseError]
  effects: none
  requires: text.len() > 0
  ensures: result is Ok(c) implies c >= Cents(0)
  example: parse_price("12.50") == Ok(Cents(1250))
  example: parse_price("abc") == Err(ParseError.NotANumber)
do
  -- ...
end fn parse_price
```

Chi usa `parse_price` sa dalla firma cosa riceve, cosa può fallire, quali condizioni valgono e che la funzione non tocca rete, file o stato.

## Stato

**Fase di progetto.** Esistono il paper, la grammatica formale e programmi di esempio; non esiste ancora un interprete né un compilatore.

| Fase | Cosa | Stato |
|---|---|---|
| 0 | Paper e sintassi | fatto |
| 1 | Esperimento: interprete minimo, Tessera contro Python con un modello linguistico | da fare |
| 2 | Nucleo: compilatore verso WebAssembly, effetti, capability | da fare |
| 3 | Addestramento di IA: tensori, derivazione, provenienza dei dati | da fare |
| 4 | Verifica e domini: compilatore verificato, database, web, kernel | da fare |

## Contenuto

| Percorso | Cosa contiene |
|---|---|
| [docs/paper.md](docs/paper.md) | Il paper: motivazioni, architettura, modello di sicurezza, valutazione |
| [spec/sintassi.md](spec/sintassi.md) | Le decisioni di sintassi, con motivazioni e misure in token |
| [spec/tessera.lark](spec/tessera.lark) | La grammatica formale (LALR(1)) |
| [esempi/](esempi/) | Programmi `.tsr` di esempio: prezzi, un servizio di rete, addestramento, interoperabilità |
| [strumenti/controlla_grammatica.py](strumenti/controlla_grammatica.py) | Verifica la grammatica sugli esempi e su 14 errori tipici che deve rifiutare |

## Provare la grammatica

```bash
pip install -r requirements.txt
python strumenti/controlla_grammatica.py
```

## Licenza

[Apache 2.0](LICENSE).
