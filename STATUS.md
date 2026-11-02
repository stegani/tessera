# Tessera — project status

*English · [Italiano](STATUS.it.md)* · last updated: 2 November 2026

Created by **Stefano Stegani - Airgrid Network - [www.airgrid.it](https://www.airgrid.it)**

## Where the project stands

| Area | Status |
|---|---|
| Design paper | done, 16 sections ([docs/paper.md](docs/paper.md)) |
| User manual | for writing Tessera by hand, in English and Italian, also as PDF; every program in it is checked by the tests ([docs/manual.md](docs/manual.md)) |
| Syntax and formal grammar | done, LALR(1) without conflicts ([spec/syntax.md](spec/syntax.md), [spec/tessera.lark](spec/tessera.lark)) |
| Interpreter and static checks | prototype 0.2: full language core, effects, contracts, `edit`/`take`, file permissions, hardware sentinel |
| WebAssembly compiler | prototype 0.2: pure functions on `i32`, `i64`, `f64`, `bool`, checked against the interpreter on 1 500 random calls |
| Phase 1 experiment | ready; first local results in (see below) ([experiment/](experiment/)) |
| Training of small models | started: data verified by the compiler, QLoRA training and export to Ollama ([training/](training/)) |
| Tests | 99, all passing |
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

## Experiment: results so far (1-2 November 2026)

Local models only, via Ollama, 20 tasks × 3 repetitions per language. "v1" is version 0.1.0 (1 November); "v2" is version 0.2.0, which adds syntax errors with precise hints, `result` no longer reserved, and a shorter manual (about 1 060 tokens instead of 1 700) with a "wrong → right" table built on the models' real mistakes.

| Model | Version | Tessera solved | Python solved | Python silent defects | Tessera attempts with a syntax error |
|---|---|---|---|---|---|
| gemma3:4b | v1 | 1 / 60 | 44 / 60 | **30** | 135 / 180 |
| gemma3:4b | v2 | 0 / 60 | 43 / 60 | **29** | 169 / 180 |
| qwen2.5:3b | v1 | 0 / 60 | 44 / 60 | **37** | 180 / 180 |
| qwen2.5:3b | v2 | 0 / 60 | 48 / 60 | **30** | 178 / 180 |
| qwen3.8 (1 task only) | v1 | 1 / 1, 2nd attempt | 1 / 1 | 0 | 1 / 2 |

*Silent defects*: hidden tests where the program returned a wrong result without any error.

**What this says, honestly:**

- **Very small models (3-4B) cannot learn Tessera from a manual in the prompt**, not even an improved one. A larger local model (qwen3.8, 27B) wrote correct Tessera after one compiler error.
- **Targeted fixes work on the habit they target**: `let mut` (from Rust) went from 34 and 68 occurrences to 0 and 1; `then`, `::` and `|x|` closures dropped sharply. But each program contains several *different* habits (`!x`, `.unwrap()`, `as i64`, invented methods), the parser stops at the first error, and three attempts are not enough to get through them all.
- Some rules a 3B model does not absorb at all: qwen2.5:3b left out `effects:` in 122 attempts out of 180 despite the manual, the table and the hints.
- In Python the small models solve most tasks but leave **30-37 silent defects** per run, mostly in the security tasks: exactly the problem Tessera targets.
- **Noise**: the Python prompt did not change between v1 and v2, yet qwen2.5:3b went from 44 to 48 solved tasks. Differences of a few tasks are random variation, not an effect.
- **Correction**: the 9 errors attributed on 1 November to `result` being reserved were in fact all `let mut result`. Freeing `result` is still right: in expressions it was silently taken as the returned value.

## Next steps

1. **Report every syntax error at once** instead of only the first, so a small model can fix several habits per attempt.
2. **Grammar-constrained generation** (llama.cpp): it would make these syntax errors impossible, and is likely essential for 3-4B models.
3. Run **qwen3.8** overnight on v2 (about 7 hours): the decisive measurement on a model large enough to write Tessera.
4. **Training a small model (started)**: the pipeline is in [training/](training/). Next: generate about 300 new tasks and their solutions with qwen3.8 overnight, train gemma3:4b with QLoRA, and run the same experiment again to compare with the 0/60 "before".
5. English messages for the remaining errors (types, effects, contracts); static type checker; fuller WebAssembly compiler.
