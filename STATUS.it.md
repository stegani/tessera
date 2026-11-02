# Tessera — stato del progetto

*[English](STATUS.md) · Italiano* · ultimo aggiornamento: 2 novembre 2026

## A che punto siamo

| Area | Stato |
|---|---|
| Paper di progetto | fatto, 16 sezioni ([docs/paper.md](docs/paper.md)) |
| Sintassi e grammatica formale | fatte, LALR(1) senza conflitti ([spec/syntax.md](spec/syntax.md), [spec/tessera.lark](spec/tessera.lark)) |
| Interprete e controlli statici | prototipo 0.2: nucleo completo, effetti, contratti, `edit`/`take`, permessi sui file, sentinella hardware |
| Compilatore WebAssembly | prototipo 0.2: funzioni pure su `i32`, `i64`, `f64`, `bool`, confrontato con l'interprete su 1 500 chiamate casuali |
| Esperimento della fase 1 | pronto; primi risultati con modelli locali (vedi sotto) ([experiment/](experiment/)) |
| Addestramento dei modelli piccoli | avviato: dati verificati dal compilatore, addestramento QLoRA ed esportazione in Ollama ([training/](training/)) |
| Test | 76, tutti superati |
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

## Esperimento: risultati finora (1-2 novembre 2026)

Solo modelli locali, tramite Ollama, 20 esercizi × 3 ripetizioni per linguaggio. "v1" è la versione 0.1.0 (1° novembre); "v2" è la versione 0.2.0, che aggiunge errori di sintassi con suggerimenti precisi, `result` non più riservato e un manuale più corto (circa 1 060 token invece di 1 700) con una tabella "sbagliato → giusto" costruita sugli errori reali dei modelli.

| Modello | Versione | Tessera risolti | Python risolti | Difetti silenziosi in Python | Tentativi Tessera con errore di sintassi |
|---|---|---|---|---|---|
| gemma3:4b | v1 | 1 / 60 | 44 / 60 | **30** | 135 / 180 |
| gemma3:4b | v2 | 0 / 60 | 43 / 60 | **29** | 169 / 180 |
| qwen2.5:3b | v1 | 0 / 60 | 44 / 60 | **37** | 180 / 180 |
| qwen2.5:3b | v2 | 0 / 60 | 48 / 60 | **30** | 178 / 180 |
| qwen3.8 (1 solo esercizio) | v1 | 1 / 1, al 2° tentativo | 1 / 1 | 0 | 1 / 2 |

*Difetti silenziosi*: test nascosti in cui il programma ha restituito un risultato sbagliato senza nessun errore.

**Cosa dicono, onestamente:**

- **I modelli molto piccoli (3-4 miliardi) non imparano Tessera da un manuale nel prompt**, nemmeno migliorato. Un modello locale più grande (qwen3.8, 27 miliardi) ha scritto Tessera corretto dopo un solo errore del compilatore.
- **Gli interventi mirati funzionano sull'abitudine che colpiscono**: `let mut` (da Rust) è passato da 34 e 68 casi a 0 e 1; `then`, `::` e le chiusure `|x|` sono calati molto. Ma ogni programma contiene diverse abitudini *diverse* (`!x`, `.unwrap()`, `as i64`, metodi inventati), il parser si ferma al primo errore, e tre tentativi non bastano a superarle tutte.
- Alcune regole un modello da 3 miliardi non le assorbe affatto: qwen2.5:3b ha omesso `effects:` in 122 tentativi su 180, nonostante manuale, tabella e suggerimenti.
- In Python i modelli piccoli risolvono la maggior parte degli esercizi, ma lasciano **30-37 difetti silenziosi** per corsa, soprattutto negli esercizi di sicurezza: proprio il problema che Tessera vuole risolvere.
- **Rumore**: il prompt di Python non è cambiato tra v1 e v2, eppure qwen2.5:3b è passato da 44 a 48 esercizi risolti. Differenze di pochi esercizi sono variazione casuale, non un effetto.
- **Correzione**: i 9 errori attribuiti il 1° novembre alla parola riservata `result` erano in realtà tutti `let mut result`. Liberare `result` resta giusto: nelle espressioni veniva interpretato in silenzio come il valore restituito.

## Prossimi passi

1. **Segnalare tutti gli errori di sintassi insieme**, non solo il primo, così un modello piccolo può correggere più abitudini a ogni tentativo.
2. **Generazione vincolata dalla grammatica** (llama.cpp): renderebbe impossibili questi errori di sintassi, e per i modelli da 3-4 miliardi è probabilmente indispensabile.
3. Lanciare **qwen3.8** di notte sulla v2 (circa 7 ore): la misura decisiva su un modello abbastanza grande da scrivere Tessera.
4. **Addestramento di un modello piccolo (avviato)**: il sistema è in [training/](training/). Prossimo passo: generare circa 300 esercizi nuovi e le loro soluzioni con qwen3.8 di notte, addestrare gemma3:4b con QLoRA e rifare lo stesso esperimento, per il confronto con lo 0/60 di partenza.
5. Messaggi in inglese anche per gli altri errori (tipi, effetti, contratti); controllo statico dei tipi; compilatore WebAssembly più completo.
