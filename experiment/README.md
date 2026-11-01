# Esperimento della fase 1: Tessera contro Python

L'esperimento misura la tesi del paper (sezione 12): **un modello linguistico scrive codice Tessera più corretto e più sicuro che in Python, pur non avendo mai visto Tessera prima?**

## Come funziona

1. Lo stesso modello riceve gli stessi 20 esercizi in Tessera e in Python, con la stessa descrizione e gli stessi esempi. Per Tessera il prompt di sistema contiene anche il [manuale del linguaggio](tessera_reference.md), circa 1 700 token, perché il modello non lo conosce.
2. Il codice viene eseguito sui **test visibili**, gli esempi del prompt. Se fallisce, il modello riceve l'errore (del compilatore o dei test) e riprova, fino a 3 tentativi.
3. La soluzione finale viene eseguita sui **test nascosti**, che il modello non vede mai: casi limite come input vuoti, overflow, percorsi con `..`, caratteri non ASCII.
4. Si ripete tutto 3 volte per esercizio, perché le risposte di un modello variano.

Metà degli esercizi riguarda la sicurezza: validazione degli input, overflow, percorsi che escono dalla cartella, escape HTML, limitazione delle richieste.

## Cosa si misura

| Metrica | Significato |
|---|---|
| Risolti al primo tentativo | il codice passa gli esempi senza correzioni |
| Risolti entro il limite | passano gli esempi entro 3 tentativi |
| Tentativi medi | quanti giri servono, usando gli errori del compilatore |
| Test nascosti superati | robustezza sui casi limite, tra gli esercizi risolti |
| **Difetti silenziosi** | test nascosti con un risultato sbagliato **senza alcun errore**: sono le vulnerabilità vere |
| Difetti che fermano il programma | test nascosti in cui il programma si è fermato con un errore (overflow, contratto, indice) |
| Token e costo | token di ingresso e uscita per esercizio, e costo stimato |

La distinzione tra difetti silenziosi e difetti che fermano il programma è il cuore della tesi. Per esempio, una somma senza controlli in Python dà un numero sbagliato; la stessa somma in Tessera si ferma con un errore di overflow.

## Come lanciarlo

Dalla cartella del progetto, con l'ambiente attivo:

```bash
python -m experiment check
```

Verifica che le 40 soluzioni di riferimento, 20 esercizi in 2 linguaggi, superino tutti i 156 test di ciascun linguaggio.

```bash
python -m experiment run --model reference --reps 1
```

Prova tutto il ciclo **senza costi**, usando le soluzioni di riferimento al posto del modello. Con `--model reference-broken` il primo tentativo è volutamente sbagliato, così si prova anche il ciclo di correzione.

```bash
python -m experiment run --yes
```

È l'**esperimento vero** con Claude Opus 5.5. Serve una chiave API: imposta la variabile `ANTHROPIC_API_KEY`, oppure accedi con `ant auth login`. Senza `--yes` il comando mostra solo quante chiamate farebbe.

Opzioni utili: `--model claude-sonnet-5-5`, `--effort medium`, `--reps 1`, `--tasks parse_int_safe,checked_sum`. Se l'esperimento si interrompe, rilanciandolo con lo stesso `--out` riprende da dove si era fermato.

I risultati finiscono in `experiment/results/` (esclusa da git): un file `.jsonl` con ogni tentativo e un rapporto `.md` con le tabelle. Per rigenerare il rapporto:

```bash
python -m experiment report experiment/results/FILE.jsonl
```

## Costo

Con le impostazioni predefinite (Claude Opus 5.5, sforzo `high`, 20 esercizi × 2 linguaggi × 3 ripetizioni) si fanno da 120 a 360 chiamate. Il costo stimato è **intorno ai 10-20 dollari**: dipende soprattutto da quanto ragiona il modello. Con `--reps 1` il costo si riduce a circa un terzo. Il rapporto finale riporta il costo calcolato sui token effettivi.

## Correttezza e limiti

- **Equità**: stesso modello, stessa descrizione, stessi esempi, stesso numero di tentativi. I linguaggi sono alternati esercizio per esercizio.
- **Esecuzione isolata**: il codice gira in un processo separato, con un limite di 10 secondi. Per il Python generato valgono in più queste regole:
  - sono consentiti solo moduli innocui (`math`, `re`, `collections`…);
  - sono vietati file, rete, `eval` e introspezione.

  Non è una sandbox completa: per esecuzioni su larga scala conviene usare un container. Il codice Tessera non ha bisogno di questo filtro, perché il linguaggio rifiuta da solo gli effetti non dichiarati.
- **Fallback**: se il modello rifiuta una richiesta, il fallback lato server la ripete su un altro modello. Ogni tentativo registra quale modello ha risposto davvero, e il rapporto conta quante risposte vengono da un fallback. Per escluderlo usa `--no-fallback`.
- **Confronti noti**:
  - i messaggi d'errore di Tessera sono in italiano, mentre quelli di Python sono in inglese;
  - il prompt di Tessera è più lungo, per via del manuale;
  - Python ha alle spalle anni di dati di addestramento, Tessera nessuno.

  Sono svantaggi per Tessera: se vince lo stesso, il risultato è più solido.
- **Dimensione**: 20 esercizi bastano per vedere una tendenza, non per una conclusione statistica forte. Il paper prevede da 30 a 50 esercizi: se ne aggiungono altri in [tasks.json](tasks.json), con la soluzione di riferimento in [references.py](references.py).
