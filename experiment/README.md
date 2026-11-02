# Phase 1 experiment: Tessera versus Python

*English · [Italiano](README.it.md)*

Created by **Stefano Stegani - Airgrid Network - [www.airgrid.it](https://www.airgrid.it)**

The experiment tests the thesis of the paper (section 13): **does a language model write more correct and more secure code in Tessera than in Python, even though it has never seen Tessera before?**

## How it works

1. The same model gets the same 20 tasks in Tessera and in Python, with the same description and the same examples. For Tessera the system prompt also contains the [language manual](tessera_reference.md), about 1 060 tokens, because the model does not know the language.
2. The code runs on the **visible tests**, the examples in the prompt. If it fails, the model gets the error (from the compiler or from the tests) and tries again, up to 3 attempts.
3. The final solution runs on the **hidden tests**, which the model never sees: edge cases such as empty input, overflow, paths with `..`, non-ASCII characters.
4. Everything is repeated 3 times per task, because a model's answers vary.

Half of the tasks are about security: input validation, overflow, paths that escape a folder, HTML escaping, rate limiting.

## What is measured

| Metric | Meaning |
|---|---|
| Solved at the first attempt | the code passes the examples without corrections |
| Solved within the limit | the examples pass within 3 attempts |
| Average attempts | how many rounds it takes, using the compiler's errors |
| Hidden tests passed | robustness on edge cases, among the solved tasks |
| **Silent defects** | hidden tests with a wrong result **and no error at all**: these are the real vulnerabilities |
| Defects that stop the program | hidden tests where the program stopped with an error (overflow, contract, index) |
| Tokens and cost | input and output tokens per task, and estimated cost |

The difference between silent defects and defects that stop the program is the heart of the thesis. For example, an unchecked sum in Python gives a wrong number; the same sum in Tessera stops with an overflow error.

## How to run it

From the project folder, with the environment active:

```bash
python -m experiment check
```

Checks that the 40 reference solutions (20 tasks in 2 languages) pass all 156 tests of each language.

```bash
python -m experiment run --model reference --reps 1
```

Runs the whole loop **at no cost**, using the reference solutions instead of a model. With `--model reference-broken` the first attempt is deliberately wrong, so the correction loop is tested too.

### With a local model (recommended)

Tessera is designed above all for local AI, so the experiment starts there: no costs, no accounts, and the data stays on your computer.

With [Ollama](https://ollama.com), the default:

```bash
python -m experiment run --model ollama:qwen3.8
```

With [LM Studio](https://lmstudio.ai): load the model, start the local server (port 1234) and use the model name shown by LM Studio.

```bash
python -m experiment run --model lmstudio:MODEL_NAME
```

The name after `ollama:` is the one shown by `ollama list`. For Ollama the test bench asks for a 16 384-token context; in LM Studio the context length is set when the model is loaded: at least 8 192 tokens. Local models are slower than commercial services, but the comparison stays fair: with the same model, only the language changes.

### With a commercial model (optional)

Anyone who wants can also compare commercial models. The calls cost money, so the command only starts with `--yes`; without it, it shows how many calls it would make.

Any service with an OpenAI-compatible interface (OpenAI, Mistral, OpenRouter and others): the key is read from an environment variable, and you pass only its name.

```bash
python -m experiment run --model compat:MODEL_NAME --base-url https://api.openai.com/v1 --api-key-env OPENAI_API_KEY --yes
```

Claude, with Anthropic's official SDK: set `ANTHROPIC_API_KEY` or sign in with `ant auth login`.

```bash
python -m experiment run --model claude-opus-5-5 --yes
```

Useful options: `--reps 1`, `--effort medium` (Claude only), `--tasks parse_int_safe,checked_sum`. If the experiment stops, running it again with the same `--out` resumes where it left off.

Results go to `experiment/results/` (excluded from git): a `.jsonl` file with every attempt and a `.md` report with the tables. To regenerate the report:

```bash
python -m experiment report experiment/results/FILE.jsonl
```

## Cost and time

With a local model the experiment costs nothing, but it takes time. On a PC with an RTX 4060 (8 GB), a 3-4 billion parameter model fits entirely on the graphics card and is fast. qwen3.8 runs partly on the processor, at about 5 tokens per second: one full repetition takes about 7 hours, best run overnight.

With Claude Opus 5.5 (20 tasks × 2 languages × 3 repetitions, 120 to 360 calls) the estimated cost is around 10-20 dollars. The final report gives the cost computed on the actual tokens for Claude models.

## Fairness and limits

- **Fairness**: same model, same description, same examples, same number of attempts. The two languages alternate task by task.
- **Isolated execution**: the code runs in a separate process with a 10-second limit. Generated Python also has these rules:
  - only harmless modules are allowed (`math`, `re`, `collections`…);
  - files, network, `eval` and introspection are forbidden.

  It is not a complete sandbox: for large-scale runs, use a container. Tessera code does not need this filter, because the language itself rejects undeclared effects.
- **Fallback**: if the model refuses a request, the server-side fallback repeats it on another model. Every attempt records which model actually answered, and the report counts how many answers come from a fallback. To exclude it, use `--no-fallback`.
- **Known imbalances**:
  - Tessera's syntax errors are in English with a hint, but some other error messages are still in Italian, while Python's are in English;
  - the Tessera prompt is longer, because of the manual;
  - Python has years of training data behind it, Tessera none.

  These are disadvantages for Tessera: if it wins anyway, the result is stronger.
- **Size**: 20 tasks are enough to see a trend, not for a strong statistical conclusion. The paper plans 30 to 50 tasks: add more in [tasks.json](tasks.json), with the reference solution in [references.py](references.py).
- **Prompt version**: every result records a short fingerprint of the system prompt (`prompt_version`), so runs made with different manuals are never mixed up.
