# Tessera — stato del progetto

*[English](STATUS.md) · Italiano* · ultimo aggiornamento: 1 novembre 2026

## A che punto siamo

| Area | Stato |
|---|---|
| Paper di progetto | fatto, 16 sezioni ([docs/paper.md](docs/paper.md)) |
| Sintassi e grammatica formale | fatte, LALR(1) senza conflitti ([spec/syntax.md](spec/syntax.md), [spec/tessera.lark](spec/tessera.lark)) |
| Interprete e controlli statici | prototipo 0.1: nucleo completo, effetti, contratti, `edit`/`take`, permessi sui file, sentinella hardware |
| Compilatore WebAssembly | prototipo 0.1: funzioni pure su `i32`, `i64`, `f64`, `bool`, confrontato con l'interprete su 1 500 chiamate casuali |
| Esperimento della fase 1 | pronto; prime corse con modelli locali in corso ([experiment/](experiment/)) |
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

## Esperimento: prime osservazioni

L'esperimento sta girando con modelli locali (qwen2.5:3b, gemma3:4b, poi qwen3.8). I risultati verranno pubblicati qui a fine corsa. Finora:

- **qwen3.8** (27 miliardi di parametri, locale) ha risolto un esercizio di validazione dell'input in Tessera al secondo tentativo e in Python al primo, superando in entrambi i linguaggi tutti i 10 test nascosti, senza aver mai visto Tessera prima.
- I modelli molto piccoli (3-4 miliardi) faticano con un linguaggio mai visto: è proprio il caso in cui un manuale compatto, la generazione vincolata dalla grammatica e l'addestramento dovrebbero aiutare di più.
- Il banco di prova ha scoperto da solo un problema reale: il codice generato che stampa rompeva la lettura dei risultati. Corretto e coperto da un test.

## Prossimi passi

1. Completare le corse locali e pubblicare il confronto tra modelli di dimensioni diverse.
2. Lanciare qwen3.8 di notte (circa 7 ore).
3. Manuale "tascabile" (circa 700 token) ed errori brevi e strutturati in inglese, basati sugli errori che i modelli fanno davvero.
4. Generazione vincolata dalla grammatica tramite llama.cpp.
5. Dati di addestramento generati e verificati dal compilatore, per un adattamento LoRA di un modello piccolo.
6. Controllo statico dei tipi e compilatore WebAssembly più completo.
