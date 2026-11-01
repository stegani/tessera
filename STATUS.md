# Tessera — project status

*English · [Italiano](STATUS.it.md)* · last updated: 1 November 2026

## Where the project stands

| Area | Status |
|---|---|
| Design paper | done, 16 sections ([docs/paper.md](docs/paper.md)) |
| Syntax and formal grammar | done, LALR(1) without conflicts ([spec/syntax.md](spec/syntax.md), [spec/tessera.lark](spec/tessera.lark)) |
| Interpreter and static checks | prototype 0.1: full language core, effects, contracts, `edit`/`take`, file permissions, hardware sentinel |
| WebAssembly compiler | prototype 0.1: pure functions on `i32`, `i64`, `f64`, `bool`, checked against the interpreter on 1 500 random calls |
| Phase 1 experiment | ready; first local results in (see below) ([experiment/](experiment/)) |
| Tests | 52, all passing |
| Publication | public repository, Apache 2.0, DOI [10.5281/zenodo.23855820](https://doi.org/10.5281/zenodo.23855820) |

## Direction: built for local AI

Tessera targets large models, but its most promising ground is **local models**: smaller, with less context and less precise, they are the ones that should gain the most from a language where the compiler stops mistakes. Two things are only possible locally and are planned:

1. **Grammar-constrained generation**: the local model is prevented from producing tokens that break the grammar, so the code it writes is syntactically valid by construction.
2. **Teaching Tessera to open models**: programs generated automatically and filtered by the Tessera compiler become training data for a lightweight adaptation (LoRA).

Details in section 11 of the paper.

## Decisions taken (1 November 2026)

| Topic | Decision |
|---|---|
| Goal | a language written by AI and hardened against AI: whatever an AI could get wrong or exploit must become a compile error; efficiency for AI matters more than human readability |
| Name | **Tessera** (the Latin token of recognition, password and mosaic tile); source files `.tsr`. "Vela" was too weak; "Arx" is already taken by another LLVM-based language |
| Scope | one small core plus domain modules (databases, web, operating systems, AI training, quantum), and especially local models |
| Security | effects in the signature, resources as unique permissions (one IPv6 address per process), `Untrusted` AI output, contracts, hardware sentinel: deterministic checks at runtime, an AI red team only offline |
| Syntax | named block endings, mandatory `effects`, no lifetimes (`edit`/`take`), no mixing of `and`/`or`, explicit `return`, ASCII only |
| Implementation | Python prototype first, to reach the experiment quickly; the final compiler will be rewritten once the language is stable; WebAssembly as first backend |
| Licence and credit | Apache 2.0 with a NOTICE file crediting the author; no patents; archived on Zenodo with a DOI |
| Repository | public; file names and README in English; code content and specifications in Italian |
| Experiment | the same model writes 20 tasks in Tessera and in Python; hidden edge-case tests separate *silent* defects (wrong results) from defects that stop the program; runs first of all with local models (Ollama, LM Studio); commercial models such as Claude or OpenAI's are optional |

## Experiment: first results (1 November 2026)

Local models only, via Ollama. **gemma3:4b**: complete run, 20 tasks × 3 repetitions per language. **qwen2.5:3b**: partial, 39 of 120 records. **qwen3.8**: one task so far.

| Model | Language | Solved within 3 attempts | Hidden tests passed (solved tasks) | Silent defects |
|---|---|---|---|---|
| gemma3:4b | Tessera | 1 / 60 | 5 / 5 | 0 |
| gemma3:4b | Python | 44 / 60 | 222 / 252 | **30** (20 in security tasks) |
| qwen2.5:3b (partial) | Tessera | 0 / 20 | – | 0 |
| qwen2.5:3b (partial) | Python | 14 / 19 | – | **13** |
| qwen3.8 (1 task) | Tessera | 1 / 1, at the 2nd attempt | 10 / 10 | 0 |
| qwen3.8 (1 task) | Python | 1 / 1 | 10 / 10 | 0 |

**What this says, honestly:**

- With only the manual in the prompt, **very small models (3-4B) almost never manage to write Tessera**. In Python they solve most tasks, but leave many *silent* defects: wrong results with no error, mostly in security tasks. That is exactly the problem Tessera targets, provided the model can write it.
- A larger local model (qwen3.8, 27B) wrote correct Tessera after one compiler error.
- The errors in Tessera are not random. They come from **habits of other languages**:

  | Mistake | How often (gemma3:4b) |
  |---|---|
  | `do` on the signature line, skipping `effects:` | 35 |
  | `let mut` instead of `var` (Rust) | 34 attempts |
  | `i64::MAX`, closures `\|c\|`, inclusive ranges `1..=n` (Rust) | 44 |
  | `if ... then` instead of `if ... do` | 17 |
  | `&&` / `\|\|` instead of `and` / `or` | 14 attempts |
  | `result` used as a variable name, but it is reserved | 9 |

- The harness found a real bug on its own: generated code that prints was breaking the result reader. Fixed and covered by a test.

## Next steps (from 2 November 2026)

1. **Error messages that say exactly what to write**: for example "write `effects: none` on its own line, then `do`" or "use `var` instead of `let mut`", in English. Today the parser only says "expected one of: do".
2. **Remove needless traps**: `result` reserved only inside `ensures`; recognise common forms such as `1..=n`, `let mut`, `then`, `&&` to give the right hint.
3. **Pocket manual** (about 700 tokens) with a "not like this, like this" section built on the real mistakes above.
4. Resume qwen2.5:3b (it continues from the saved records), then re-run the small models with the improvements to measure the gain.
5. Run qwen3.8 overnight (about 7 hours).
6. Grammar-constrained generation through llama.cpp; training data verified by the compiler for a LoRA adaptation.
7. Static type checker and a fuller WebAssembly compiler.
