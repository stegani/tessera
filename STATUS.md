# Tessera — project status

*English · [Italiano](STATUS.it.md)* · last updated: 1 November 2026

## Where the project stands

| Area | Status |
|---|---|
| Design paper | done, 16 sections ([docs/paper.md](docs/paper.md)) |
| Syntax and formal grammar | done, LALR(1) without conflicts ([spec/syntax.md](spec/syntax.md), [spec/tessera.lark](spec/tessera.lark)) |
| Interpreter and static checks | prototype 0.1: full language core, effects, contracts, `edit`/`take`, file permissions, hardware sentinel |
| WebAssembly compiler | prototype 0.1: pure functions on `i32`, `i64`, `f64`, `bool`, checked against the interpreter on 1 500 random calls |
| Phase 1 experiment | ready; first local runs in progress ([experiment/](experiment/)) |
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

## Experiment: first observations

The experiment is running with local models (qwen2.5:3b, gemma3:4b, then qwen3.8). Results will be published here when complete. So far:

- **qwen3.8** (27B, local) solved an input-validation task in Tessera at the second attempt and in Python at the first, passing all 10 hidden tests in both languages, without ever having seen Tessera before.
- The very small models (3-4B) struggle with a language they have never seen: this is the case where a compact manual, grammar-constrained generation and fine-tuning should help the most.
- The harness found a real issue on its own: generated code that prints was breaking the result reader. Fixed and covered by a test.

## Next steps

1. Complete the local runs and publish the comparison between model sizes.
2. Run qwen3.8 overnight (about 7 hours).
3. Pocket manual (about 700 tokens) and short, structured error messages in English, based on the mistakes the models actually make.
4. Grammar-constrained generation through llama.cpp.
5. Training data generated and verified by the compiler, for a LoRA adaptation of a small model.
6. Static type checker and a fuller WebAssembly compiler.
