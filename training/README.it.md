# Addestrare i modelli piccoli su Tessera

*[English](README.md) · Italiano*

Creato da **Stefano Stegani - Airgrid Network - [www.airgrid.it](https://www.airgrid.it)**

L'esperimento della fase 1 ha mostrato che un modello da 3-4 miliardi di parametri non impara Tessera solo da un manuale nel prompt. Questa cartella glielo insegna con **dati di addestramento verificati dal compilatore**: ogni esempio è un programma Tessera che il compilatore accetta e che supera tutti i test del suo esercizio. Un esempio sbagliato non può entrare.

Tutto gira in locale: un modello locale più grande fa da insegnante, e il modello piccolo si addestra sulla tua scheda video (bastano 8 GB).

## Come nascono i dati

1. **Esercizi nuovi** (`python -m training tasks`). L'insegnante propone un esercizio: descrizione, tipi dei parametri, una soluzione Python di riferimento e gli input da provare. I risultati attesi **non** li scrive il modello: li calcola la soluzione di riferimento, eseguita nella sandbox. Le firme in Tessera e in Python si costruiscono dai tipi, quindi sono sempre coerenti. Gli esercizi con lo stesso nome di uno dei 20 dell'esperimento, o con una descrizione troppo simile, vengono scartati: così l'esperimento continua a misurare qualcosa di vero.
2. **Soluzioni verificate** (`python -m training solve`). L'insegnante scrive la soluzione in Tessera con lo stesso ciclo dell'esperimento: errori con suggerimento, poi un nuovo tentativo. Restano solo le soluzioni che compilano e superano **tutti** i test. Un esercizio la cui descrizione non corrisponde alla soluzione di riferimento si ferma qui, quindi questo passo filtra anche gli esercizi fatti male.
3. **Esempi** (`python -m training dataset`). Ogni soluzione verificata dà:
   - un esempio *diretto*: richiesta → codice giusto;
   - un esempio *di correzione* per ogni tentativo fallito: richiesta → codice sbagliato → errore del compilatore con suggerimento → codice giusto. Il codice sbagliato resta nella conversazione ma non si impara (`"train": false`).

   Addestramento e validazione sono divisi per esercizio, non per esempio.

Gli esempi usano lo stesso prompt di sistema dell'esperimento (il manuale), così il modello addestrato si misura esattamente nelle stesse condizioni di prima.

## Comandi

Dalla cartella del progetto, con l'ambiente solito (`.venv`):

```bash
python -m training tasks --teacher ollama:qwen3.8 --n 300
```

```bash
python -m training solve --teacher ollama:qwen3.8
```

```bash
python -m training dataset
```

```bash
python -m training check
```

Ogni comando riprende da dove si era fermato. L'insegnante può essere qualsiasi modello locale (`ollama:`, `lmstudio:`); quelli commerciali (`compat:`, `claude-...`) sono facoltativi e chiedono `--yes`. I dati finiscono in `training/data/` (esclusa da git).

## Addestramento

L'addestramento usa un ambiente separato, `.venv-train`, con PyTorch per CUDA ([requirements-train.txt](../requirements-train.txt)), così l'ambiente del prototipo resta leggero.

```bash
.venv-train/Scripts/python training/train_lora.py --base unsloth/gemma-3-4b-it --out training/runs/gemma3-4b
```

È un addestramento **QLoRA**: il modello di partenza resta fermo e compresso a 4 bit, e si addestrano solo piccole matrici aggiuntive (LoRA) sui livelli lineari del modello linguistico. Con `--dry-run` conta solo gli esempi e la loro lunghezza in token.

Poi l'adattatore si unisce al modello e si registra in Ollama, con il template e la licenza del modello originale:

```bash
.venv-train/Scripts/python training/export_ollama.py --run training/runs/gemma3-4b --base unsloth/gemma-3-4b-it --ollama-base gemma3:4b --name tessera-gemma3:4b
```

Infine, lo stesso esperimento di prima, per il confronto con il modello di partenza:

```bash
python -m experiment run --model ollama:tessera-gemma3:4b --langs tessera
```

## Scelte e limiti

- **Modello di partenza**: gemma3:4b, perché l'esperimento ha già la sua misura "prima" (0 esercizi su 60 risolti in Tessera) e le condizioni di Gemma permettono di condividere il modello addestrato, purché le condizioni lo accompagnino. Va bene qualsiasi modello simile su Hugging Face.
- **Insegnante**: qwen3.8, il modello locale che è già riuscito a scrivere Tessera. Su una scheda da 8 GB è lento (in parte gira sul processore), quindi la generazione dei dati conviene lanciarla di notte.
- **Versione del linguaggio**: i dati e i modelli addestrati appartengono a una versione di Tessera. Se la sintassi cambia, i dati si rigenerano e si ricontrollano con `python -m training check`.
