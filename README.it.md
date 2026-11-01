# Tessera

*[English](README.md) · Italiano*

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

**Prototipo 0.1.** Esistono un interprete completo per il nucleo del linguaggio, i controlli statici e un compilatore verso WebAssembly per le funzioni numeriche pure. È scritto in Python per arrivare in fretta all'esperimento della fase 1; il compilatore definitivo verrà riscritto quando il linguaggio sarà stabile.

| Fase | Cosa | Stato |
|---|---|---|
| 0 | Paper e sintassi | fatto |
| 1 | Interprete, controlli statici, primo compilatore WebAssembly | fatto (0.1) |
| 1 | Esperimento: Tessera contro Python con un modello linguistico | da fare |
| 2 | Nucleo: tipi statici, compilatore WebAssembly completo, capability di rete | da fare |
| 3 | Addestramento di IA: tensori, derivazione, provenienza dei dati | da fare |
| 4 | Verifica e domini: compilatore verificato, database, web, kernel | da fare |

## Provare

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

Su Linux e macOS il percorso è `.venv/bin/pip`. Poi, con l'ambiente attivo:

```bash
python -m tessera esegui esempi/cassa.tsr
```

| Comando | Cosa fa |
|---|---|
| `python -m tessera esegui file.tsr` | controlla il programma ed esegue il `process` o `fn main()` |
| `python -m tessera verifica file.tsr` | controlli statici senza eseguire (`--json` per errori leggibili da un modello) |
| `python -m tessera prova file.tsr` | esegue le clausole `example` come test |
| `python -m tessera compila file.tsr -o build` | produce `.wat` e `.wasm` |
| `python -m tessera chiama file.tsr funzione arg... [--wasm]` | chiama una funzione, interpretata o compilata |
| `python -m pytest tests` | 49 test, compresa la prova differenziale interprete contro WebAssembly |

Cosa controlla già il prototipo: effetti dichiarati, contratti, tipi ai confini delle funzioni, `edit` e `take`, overflow, divisione per zero, permessi sui file del `process`, `Secret` mai stampati, `Result` mai ignorati, `match` esaustivi, requisiti di piattaforma. Le regole sono in [spec/semantica.md](spec/semantica.md).

## Contenuto

| Percorso | Cosa contiene |
|---|---|
| [docs/paper.md](docs/paper.md) | Il paper: motivazioni, architettura, modello di sicurezza, valutazione |
| [spec/sintassi.md](spec/sintassi.md) | Le decisioni di sintassi, con motivazioni e misure in token |
| [spec/semantica.md](spec/semantica.md) | Le regole di esecuzione decise con il prototipo |
| [spec/tessera.lark](spec/tessera.lark) | La grammatica formale (LALR(1)) |
| [tessera/](tessera/) | Il prototipo: analizzatore, interprete, controlli statici, compilatore WebAssembly, sentinella |
| [esempi/](esempi/) | Programmi `.tsr`. Eseguibili: `ciao`, `cassa`, `prezzi`, `magazzino`, `permessi`, `numeri`. Illustrativi (usano moduli non ancora scritti): `server`, `addestramento`, `interop` |
| [tests/](tests/) | Test del prototipo |
| [strumenti/controlla_grammatica.py](strumenti/controlla_grammatica.py) | Verifica la grammatica sugli esempi e su 14 errori tipici che deve rifiutare |

## Autore e citazione

Tessera è un'idea originale di **Stefano Stegani**, che ne ha scritto il progetto, la grammatica e il paper. Il codice e i testi si possono riusare, anche in progetti commerciali, alle condizioni della licenza: **chi redistribuisce Tessera o un'opera derivata deve conservare il file [NOTICE](NOTICE), che attribuisce l'opera all'autore**, e non può presentarla come propria.

Per citare il progetto:

> Stefano Stegani, *Tessera: scritto dalle IA, blindato contro le IA*, 2026. https://github.com/stegani/tessera

Il file [CITATION.cff](CITATION.cff) contiene gli stessi dati in forma leggibile dalle macchine: GitHub lo usa per il pulsante "Cite this repository".

## Licenza

[Apache 2.0](LICENSE), con l'avviso di attribuzione in [NOTICE](NOTICE).
