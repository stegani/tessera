# Semantica di Tessera — prototipo 0.2

Le regole che il prototipo applica durante l'esecuzione, decise mentre si scrivevano l'interprete ([tessera/interpreter.py](../tessera/interpreter.py)) e il compilatore ([tessera/wasm_compiler.py](../tessera/wasm_compiler.py)). Le decisioni di sintassi sono in [syntax.md](syntax.md).

## Numeri

| Regola | Esempio |
|---|---|
| Gli interi sono a 64 bit; ogni operazione che esce dall'intervallo è un errore, mai un numero che ricomincia dal fondo | `9_223_372_036_854_775_807 + 1` → errore di overflow |
| `/` tra interi tronca verso zero; `%` ha il segno del dividendo (come Rust e C) | `-7 / 2` = `-3`, `-7 % 2` = `-1` |
| Divisione per zero: errore, anche tra decimali | `1.0 / 0.0` → errore |
| Interi e decimali non si mescolano: si converte con `to_f64()` o `to_int()` | `1 + 2.0` → errore di tipo |
| I tipi più stretti (`i32`, `u8`…) si controllano dove il tipo è dichiarato: parametri, ritorno, `let` e `var` con tipo | |
| Le quantità usano multipli binari: `1KB` = 1024 byte, `1MB` = 1024² | |

## Valori e proprietà

- **Semantica dei valori**: assegnare o passare una lista o una struttura ne crea una copia indipendente. `let b = a` seguito da `a.push(3)` lascia `b` com'era.
- **Parametri**: in sola lettura per default; `edit` lavora sulla variabile del chiamante; `take` la consuma e dopo non si può più usare.
- Un **valore temporaneo** (una lista scritta sul momento, il risultato di una chiamata) si passa a un parametro `take` senza scrivere `take`, perché non ha altri proprietari. `take` è obbligatorio solo per consumare una variabile con un nome.
- La stessa variabile non può comparire due volte in una chiamata se una delle due è `edit` o `take`.
- `take` di una variabile esterna dentro un ciclo è un errore statico: al giro successivo il valore non c'è più.

## Funzioni e chiamate

- `x.f(a)` è un altro modo di scrivere `f(x, a)` quando `f` è una funzione dell'utente; se il primo parametro di `f` è `edit` o `take` la forma con il punto non è ammessa, perché nasconderebbe la modifica.
- I costruttori di strutture e varianti accettano argomenti per posizione o per nome: `Item(name: "viti", quantity: 1)`.
- Un `Result` non si può ignorare: un'istruzione che produce un `Result` senza usarlo è un errore. Si gestisce con `?`, `match` o `unwrap_or`.
- `?` si usa solo in una funzione che restituisce lo stesso tipo (`Result` o `Option`).
- Una funzione anonima non acquista effetti: può usare al massimo quelli del punto in cui è stata scritta.

## Contratti

- `requires` si controlla all'ingresso, `ensures` all'uscita con `result` legato al valore restituito, `invariant` alla costruzione di una struttura.
- In un contratto, `x is Ok(c) implies c >= 0` lega `c` per la parte a destra di `implies`.
- Le clausole `example` si eseguono con `python -m tessera prova file.tsr`.

## Effetti e permessi

- Ogni funzione che produce un effetto lo dichiara; il controllo avviene prima dell'esecuzione (`verifica`) e di nuovo durante.
- Funzioni di base con effetti: `print` (`console`), `read_text` (`fs`).
- `read_text` legge solo sotto un percorso concesso dal `process` con `grants: fs.read("cartella")`. Fuori da un `process` non ci sono permessi sui file.
- I percorsi relativi partono dalla cartella del file principale, non dalla cartella da cui si lancia il comando.
- La clausola `platform` è controllata dalla sentinella prima dell'avvio: un requisito che non si sa verificare su questa macchina impedisce l'avvio.
- `unsafe` è ammesso solo nei moduli con `profile: kernel`.

## Compilatore WebAssembly 0.1

Compila le funzioni con `effects: none` che usano solo `i32`, `i64`, `f64` e `bool`: variabili, `if`, `while`, `for` su intervalli, chiamate tra funzioni compilate, `to_f64`, `to_int`, `abs`, contratti. Le altre funzioni vengono saltate con il motivo.

| Errore | Come si ferma il codice compilato |
|---|---|
| overflow (anche su `i32`) | `env.fallisci(1)` e trappola |
| `requires` / `ensures` violata | codici 2 e 3 |
| divisione per zero | codice 4 |
| funzione che termina senza `return` | codice 5 |

L'interprete e il compilatore vengono confrontati dai test su argomenti casuali: stesso risultato o stesso tipo di errore. Unica differenza nota: su `i32` l'interprete scopre l'overflow quando controlla il tipo di ritorno, il compilatore sull'operazione stessa; entrambi si fermano.

## Limiti del prototipo

- Nessun controllo statico dei tipi: i tipi si verificano durante l'esecuzione, ai confini delle funzioni.
- Mancano interfacce per i generici, mappe, rete, `llm`, tensori e derivazione, dimostrazioni formali, funzioni esterne.
- I limiti di memoria e CPU (`limits`) e l'identità di rete IPv6 dei processi sono letti ma non applicati.
