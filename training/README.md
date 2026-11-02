# Training small models on Tessera

*English · [Italiano](README.it.md)*

The phase 1 experiment showed that a 3-4 billion parameter model cannot learn Tessera from a manual in the prompt alone. This folder teaches it with **training data verified by the compiler**: every example is a Tessera program that the compiler accepts and that passes every test of its task. A wrong example cannot get in.

Everything runs locally: a larger local model acts as the teacher, and the small model is trained on your own graphics card (an 8 GB card is enough).

## How the data is made

1. **New tasks** (`python -m training tasks`). The teacher proposes a task: a description, the parameter types, a Python reference solution and the inputs to try. The expected results are **not** written by the model: they are computed by running the reference solution in the sandbox. The Tessera and Python signatures are built from the types, so they always agree. Tasks with the same name as, or a description too similar to, one of the 20 experiment tasks are discarded, so the experiment still measures something real.
2. **Verified solutions** (`python -m training solve`). The teacher writes the solution in Tessera with the same loop as the experiment: errors with hints, then a new attempt. Only solutions that compile and pass **all** the tests are kept. A task whose description does not match its reference solution fails here, so this step also filters out bad tasks.
3. **Examples** (`python -m training dataset`). Each verified solution gives:
   - a *direct* example: request → correct code;
   - a *repair* example for each failed attempt: request → wrong code → compiler error with hint → correct code. The wrong code stays in the conversation but is not learned (`"train": false`).

   Training and validation are split by task, not by example.

The examples use the same system prompt as the experiment (the manual), so the trained model is measured under exactly the same conditions as before.

## Commands

From the project folder, with the usual environment (`.venv`):

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

Every command resumes where it stopped. The teacher can be any local model (`ollama:`, `lmstudio:`); commercial ones (`compat:`, `claude-...`) are optional and need `--yes`. The data goes to `training/data/` (excluded from git).

## Training

Training uses a separate environment, `.venv-train`, with PyTorch for CUDA ([requirements-train.txt](../requirements-train.txt)), so the prototype environment stays light.

```bash
.venv-train/Scripts/python training/train_lora.py --base unsloth/gemma-3-4b-it --out training/runs/gemma3-4b
```

It is **QLoRA** training: the starting model stays frozen and compressed to 4 bits, and only small extra matrices (LoRA) are trained on the linear layers of the language model. `--dry-run` only counts the examples and their length in tokens.

Then the adapter is merged into the model and registered in Ollama, with the template and license of the original model:

```bash
.venv-train/Scripts/python training/export_ollama.py --run training/runs/gemma3-4b --base unsloth/gemma-3-4b-it --ollama-base gemma3:4b --name tessera-gemma3:4b
```

Finally, the same experiment as before, to compare with the starting model:

```bash
python -m experiment run --model ollama:tessera-gemma3:4b --langs tessera
```

## Choices and limits

- **Starting model**: gemma3:4b, because the experiment already has its "before" measurement (0 of 60 tasks solved in Tessera) and Gemma's terms allow sharing the trained model, as long as the terms go with it. Any similar Hugging Face model works.
- **Teacher**: qwen3.8, the local model that already managed to write Tessera. It is slow on an 8 GB card (part of it runs on the processor), so data generation is best run overnight.
- **Language version**: the data and the trained models belong to one version of Tessera. If the syntax changes, the data can be regenerated and checked again with `python -m training check`.
