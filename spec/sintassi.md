# Sintassi di Tessera — bozza 0.1

Bozza del 01/11/2026. La grammatica formale è [tessera.lark](tessera.lark) (LALR(1), verificata senza conflitti); gli esempi sono in [esempi/](../esempi/); la verifica si lancia con:

```bash
pip install "lark[interegular]"
python strumenti/controlla_grammatica.py
```

## Il criterio

Ogni scelta deve rispondere a una domanda: **riduce gli errori di un modello, o il codice che deve leggere?** Un token in più si accetta solo se compra una di queste due cose. I costi sono misurati più sotto.

## Le decisioni

| # | Decisione | Esempio | Perché |
|---|---|---|---|
| 1 | Ogni dichiarazione e istruzione comincia con una parola chiave o con un'espressione | `let`, `var`, `if`, `for`, `match`, `return` | Il parser è LALR(1): sa sempre cosa può venire dopo, quindi l'errore dice esattamente cosa manca (`attesi: EFFECTS`) |
| 2 | Blocchi `do … end <parola>`; `fn`, `type` e `process` si chiudono anche con il nome | `end if`, `end fn parse_price` | Niente conteggio di graffe su blocchi lunghi; il compilatore sa *quale* blocco non è chiuso |
| 3 | L'istruzione finisce a fine riga; niente `;`. Dentro parentesi si può andare a capo. L'indentazione non conta per il parser | | Nessun errore di indentazione alla Python; il formattatore impone comunque un'indentazione unica |
| 4 | Tipi in `PascalCase`, tutto il resto in `snake_case`, imposto dalla grammatica | `ParseError`, `parse_price` | Il caso dice cos'è un nome senza cercarne la dichiarazione |
| 5 | Generici con le quadre | `Result[Cents, ParseError]` | Nessuna ambiguità con `<` e `>` |
| 6 | Firma con clausole in **ordine fisso**: `doc`, `effects` (obbligatoria), `requires`, `ensures`, `example`, `budget` | vedi [prezzi.tsr](../esempi/prezzi.tsr) | La firma è tutto ciò che serve per usare la funzione, sempre nello stesso posto |
| 7 | Import espliciti, mai `*` | `from std.net import Request, Response` | Ogni nome usato ha una provenienza visibile nel file |
| 8 | **Proprietà senza simboli e senza lifetime.** I parametri sono in sola lettura; `edit` li modifica, `take` li consuma. La parola si ripete alla chiamata. Nessun riferimento dentro le strutture | `train_step(edit params, batch, 0.001)` | Le annotazioni di durata (*lifetime*) sono la parte di Rust in cui i modelli sbagliano di più. Così non servono: è il modello a "semantica dei valori mutabili" del linguaggio Hylo. Alla chiamata si vede cosa cambia |
| 9 | Solo funzioni libere; `p.norm()` è un altro modo di scrivere `norm(p)` | | Un solo modo di dichiarare comportamento: niente classi, `impl`, ereditarietà |
| 10 | `type` per strutture (campi) e somme (varianti `case`); `type Cents = i64` crea un tipo **distinto**, non un sinonimo | vedi [prezzi.tsr](../esempi/prezzi.tsr) | Centesimi e interi non si mescolano per sbaglio |
| 11 | `return` sempre esplicito | | Il ritorno implicito dell'ultima espressione è una fonte nota di confusione |
| 12 | Errori come valori: `Result`, `Option`, propagazione con `?`; varianti come in Rust | `Ok`, `Err`, `Some`, `None` | Familiare ai modelli; nessuna eccezione invisibile |
| 13 | Logica a parole: `and`, `or`, `not`, `implies`. **`and` e `or` non si mescolano senza parentesi; i confronti non si concatenano** | `(a and b) or c`; `0 <= x and x < n` | Nessuna sorpresa di precedenza. La grammatica lo impone |
| 14 | `match` con `case pattern:` e guardie `if` | vedi [server.tsr](../esempi/server.tsr) | Forma di Python 3.10, controllo di esaustività come Rust |
| 15 | Commenti con `--`; la documentazione sta nella clausola `doc:` | | La documentazione è parte strutturata della firma, non testo libero |
| 16 | Codice solo ASCII (le stringhe possono contenere altro) | `implies`, non `⇒` | I simboli rari costano più token e si sbagliano di più (misure sotto) |
| 17 | Stringhe con interpolazione sempre attiva | `"Rimborso di {amount} avviato"` | Un solo modo; interpolare un `Secret` è un errore di compilazione |
| 18 | Quantità con unità nel lessico | `memory 512MB`, `data.len() < 4GB` | Budget e limiti leggibili senza costanti magiche |
| 20 | Tipo tupla tra parentesi (aggiunto con il prototipo, grammatica 0.2) | `fn split_once(...) -> (Str, Str)` | Serviva per restituire più valori senza definire una struttura |
| 19 | Un processo dichiara la piattaforma che gli serve | `platform: ecc, microcode_current, spectre_mitigations` | La sentinella hardware non lo avvia su una macchina che non la garantisce (paper, sezione 7.5) |

**Assenti di proposito**: classi ed ereditarietà, eccezioni, `null`, macro, `eval`, variabili globali modificabili, `import *`, `++` e `--`, operatore ternario, sovraccarico degli operatori (`@` esiste solo per le matrici).

## La verifica

Il controllo del 01/11/2026 ha dato:

- grammatica LALR(1) senza conflitti in modalità rigorosa;
- 4 esempi accettati: [prezzi.tsr](../esempi/prezzi.tsr), [server.tsr](../esempi/server.tsr), [addestramento.tsr](../esempi/addestramento.tsr), [interop.tsr](../esempi/interop.tsr);
- 14 errori tipici rifiutati. Per esempio, le clausole fuori ordine danno:

```json
{"riga": 4, "colonna": 3, "trovato": "requires", "attesi": ["DOC", "EFFECTS"]}
```

## Quanto costa: le misure

Conteggio con i tokenizer pubblici `o200k_base` e `cl100k_base` (OpenAI), usati come stima: il tokenizer di Claude non è pubblico.

| Scelta | Tessera | token | Alternativa | token |
|---|---|---|---|---|
| chiusura funzione | `end fn parse_price` | 4 | `}` | 1 |
| chiusura if | `end if` | 2 | `}` | 1 |
| apertura blocco | `do` | 2 | `{` | 1 |
| logica | `a and not b or c` | 6 | `a && !b \|\| c` | 6 |
| prestito mutabile | `edit params` | 2 | `&mut params` | 3 |
| operatore | `a xor b` | 3 | `a ⊕ b` | 5 |
| clausola effetti | `effects: none` | 5 | (assente) | 0 |

Per la stessa funzione `parse_price`, con documentazione ed esempi:

| Linguaggio | token (o200k) | Cosa dichiara in più |
|---|---|---|
| Python | 138 | — |
| Rust | 156 | tipi |
| Tessera | 177 | tipi, effetti, postcondizione verificabile, esempi eseguiti come test |

**Lettura onesta**: Tessera costa circa il 13% di token in più di Rust e il 28% in più di Python per scrivere la stessa funzione. Il paper sostiene che questo costo si ripaga in lettura (la firma evita di aprire il corpo) e in errori evitati. È un'ipotesi: la deve confermare l'esperimento della fase 1. Le chiusure con nome sono la voce più cara e la prima da mettere alla prova.

## Domande aperte

1. **Interfacce per i generici** (`fn max[T: Ord]`): la grammatica accetta il vincolo, ma la dichiarazione delle interfacce non è ancora definita.
2. **`end` semplice per `if`, `for`, `while`, `match`**: risparmierebbe un token per blocco. Da decidere con una prova A/B nell'esperimento, misurando gli errori di chiusura.
3. **`effects` obbligatoria anche sulle funzioni private**: costa 5 token per funzione. Alternativa: dedotta per le funzioni non `pub`.
4. **Dimostrazioni**: sintassi dei blocchi `proof` per il livello 3 di garanzia.
5. **Effetti delle funzioni anonime** (`fn(b) => …`): dedotti dal corpo o dichiarati.
6. **Grammatica dell'interpolazione** dentro le stringhe.
7. **Pacchetti**: un file è un modulo; manca la struttura dei pacchetti e delle versioni.

## Allineamento con il paper

Il 01/11/2026 gli esempi di codice del paper sono stati riscritti con questa sintassi e controllati con la grammatica, uno per uno, prima di pubblicarli.
