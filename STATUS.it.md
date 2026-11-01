# Tessera — stato del progetto

*[English](STATUS.md) · Italiano* · ultimo aggiornamento: 1 novembre 2026

## A che punto siamo

| Area | Stato |
|---|---|
| Paper di progetto | fatto, 16 sezioni ([docs/paper.md](docs/paper.md)) |
| Sintassi e grammatica formale | fatte, LALR(1) senza conflitti ([spec/syntax.md](spec/syntax.md), [spec/tessera.lark](spec/tessera.lark)) |
| Interprete e controlli statici | prototipo 0.1: nucleo completo, effetti, contratti, `edit`/`take`, permessi sui file, sentinella hardware |
| Compilatore WebAssembly | prototipo 0.1: funzioni pure su `i32`, `i64`, `f64`, `bool`, confrontato con l'interprete su 1 500 chiamate casuali |
| Esperimento della fase 1 | pronto; primi risultati con modelli locali (vedi sotto) ([experiment/](experiment/)) |
| Test | 52, tutti superati |
| Pubblicazione | repository pubblica, Apache 2.0, DOI [10.5281/zenodo.23855820](https://doi.org/10.5281/zenodo.23855820) |

## Direzione: un linguaggio per le IA locali

Tessera è pensato anche per i grandi modelli, ma il suo terreno più promettente sono i **modelli locali**: più piccoli, con meno contesto e meno precisi, sono quelli che dovrebbero guadagnare di più da un linguaggio in cui il compilatore ferma gli errori. Due cose si possono fare solo in locale, e sono in programma:

1. **Generazione vincolata dalla grammatica**: al modello locale si impedisce di produrre token che violano la grammatica, quindi il codice che scrive è sintatticamente valido per costruzione.
2. **Insegnare Tessera ai modelli aperti**: programmi generati automaticamente e filtrati dal compilatore di Tessera diventano dati di addestramento per un adattamento leggero (LoRA).

I dettagli sono nella sezione 11 del paper.

## Decisioni prese (1 novembre 2026)

| Tema | Decisione |
|---|---|
| Obiettivo | un linguaggio scritto dalle IA e blindato contro le IA: ciò che un'IA può sbagliare o sfruttare deve diventare un errore di compilazione; l'efficienza per l'IA conta più della leggibilità per le persone |
| Nome | **Tessera** (il contrassegno di riconoscimento latino, la parola d'ordine, il tassello del mosaico); file sorgente `.tsr`. "Vela" era debole; "Arx" è già usato da un altro linguaggio basato su LLVM |
| Ambito | un nucleo piccolo con moduli di dominio (database, web, sistemi operativi, addestramento di IA, quantistico), e soprattutto i modelli locali |
| Sicurezza | effetti nella firma, risorse come permessi unici (un indirizzo IPv6 per processo), output delle IA come `Untrusted`, contratti, sentinella hardware: controlli deterministici a runtime, un'IA d'attacco solo fuori linea |
| Sintassi | chiusure dei blocchi con nome, `effects` obbligatoria, niente lifetime (`edit`/`take`), `and`/`or` mai mescolati, `return` esplicito, solo ASCII |
| Implementazione | prima un prototipo in Python, per arrivare presto all'esperimento; il compilatore definitivo verrà riscritto quando il linguaggio sarà stabile; WebAssembly come primo backend |
| Licenza e paternità | Apache 2.0 con il file NOTICE che attribuisce l'opera all'autore; niente brevetti; archiviato su Zenodo con DOI |
| Repository | pubblica; nomi dei file e README in inglese; contenuto del codice e specifiche in italiano |
| Esperimento | lo stesso modello scrive 20 esercizi in Tessera e in Python; i test nascosti sui casi limite separano i difetti *silenziosi* (risultati sbagliati) da quelli che fermano il programma; gira prima di tutto con modelli locali (Ollama, LM Studio); i modelli commerciali come Claude o quelli di OpenAI sono facoltativi |

## Esperimento: primi risultati (1 novembre 2026)

Solo modelli locali, tramite Ollama. **gemma3:4b**: corsa completa, 20 esercizi × 3 ripetizioni per linguaggio. **qwen2.5:3b**: parziale, 39 risultati su 120. **qwen3.8**: per ora un solo esercizio.

| Modello | Linguaggio | Risolti entro 3 tentativi | Test nascosti superati (esercizi risolti) | Difetti silenziosi |
|---|---|---|---|---|
| gemma3:4b | Tessera | 1 / 60 | 5 / 5 | 0 |
| gemma3:4b | Python | 44 / 60 | 222 / 252 | **30** (20 negli esercizi di sicurezza) |
| qwen2.5:3b (parziale) | Tessera | 0 / 20 | – | 0 |
| qwen2.5:3b (parziale) | Python | 14 / 19 | – | **13** |
| qwen3.8 (1 esercizio) | Tessera | 1 / 1, al 2° tentativo | 10 / 10 | 0 |
| qwen3.8 (1 esercizio) | Python | 1 / 1 | 10 / 10 | 0 |

**Cosa dicono, onestamente:**

- Con il solo manuale nel prompt, **i modelli molto piccoli (3-4 miliardi) non riescono quasi mai a scrivere Tessera**. In Python risolvono la maggior parte degli esercizi, ma lasciano molti difetti *silenziosi*: risultati sbagliati senza nessun errore, soprattutto negli esercizi di sicurezza. È proprio il problema che Tessera vuole risolvere, a patto che il modello riesca a scriverlo.
- Un modello locale più grande (qwen3.8, 27 miliardi) ha scritto Tessera corretto dopo un solo errore del compilatore.
- Gli errori in Tessera non sono casuali. Nascono da **abitudini prese da altri linguaggi**:

  | Errore | Quante volte (gemma3:4b) |
  |---|---|
  | `do` sulla riga della firma, saltando `effects:` | 35 |
  | `let mut` invece di `var` (Rust) | 34 tentativi |
  | `i64::MAX`, chiusure `\|c\|`, intervalli `1..=n` (Rust) | 44 |
  | `if ... then` invece di `if ... do` | 17 |
  | `&&` / `\|\|` invece di `and` / `or` | 14 tentativi |
  | `result` usato come nome di variabile, ma è riservato | 9 |

- Il banco di prova ha scoperto da solo un bug reale: il codice generato che stampa rompeva la lettura dei risultati. Corretto e coperto da un test.

## Prossimi passi (dal 2 novembre 2026)

1. **Errori che dicono esattamente cosa scrivere**: per esempio "scrivi `effects: none` su una riga, poi `do`" oppure "usa `var` invece di `let mut`", in inglese. Oggi il parser dice solo "atteso uno tra: do".
2. **Togliere le trappole inutili**: `result` riservato solo dentro `ensures`; riconoscere forme diffuse come `1..=n`, `let mut`, `then`, `&&` per dare il suggerimento giusto.
3. **Manuale "tascabile"** (circa 700 token) con una sezione "non così, ma così" costruita sugli errori reali qui sopra.
4. Riprendere qwen2.5:3b (riparte dai risultati salvati), poi ripetere i modelli piccoli con i miglioramenti per misurare il guadagno.
5. Lanciare qwen3.8 di notte (circa 7 ore).
6. Generazione vincolata dalla grammatica tramite llama.cpp; dati di addestramento verificati dal compilatore per un adattamento LoRA.
7. Controllo statico dei tipi e compilatore WebAssembly più completo.
