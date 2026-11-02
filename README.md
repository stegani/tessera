<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/tessera-logo-dark.png">
    <img src="docs/brand/tessera-logo.png" alt="Tessera: written by AI, hardened against AI" width="560">
  </picture>
</p>

*English · [Italiano](README.it.md)*

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23855820.svg)](https://doi.org/10.5281/zenodo.23855820)

**A programming language written by AI, hardened against AI.**
Declared effects, verified contracts, vulnerabilities that don't compile.

AI systems write more and more code, and the same abilities can find its flaws at enormous scale. Tessera moves security from the programmer to the compiler: whatever an AI could get wrong or exploit should become a compile error.

```
fn parse_price(text: Str) -> Result[Cents, ParseError]
  effects: none
  requires: text.len() > 0
  ensures: result is Ok(c) implies c >= Cents(0)
  example: parse_price("12.50") == Ok(Cents(1250))
  example: parse_price("abc") == Err(ParseError.NotANumber)
do
  -- ...
end fn parse_price
```

Anyone calling `parse_price` learns from the signature alone what it takes, how it can fail, which conditions hold, and that it touches no network, files or state.

## Key ideas

- **A special eye for local AI**: Tessera works with large models too, but it is designed above all for small local ones (run with Ollama or LM Studio), which gain the most from a language where the compiler stops mistakes. Grammar-constrained generation and compiler-verified training data are planned.
- **Effects in the signature**: a function declares what it can do besides computing (`console`, `fs`, `net`, `gpu`, `llm`…); calling something with undeclared effects is rejected.
- **Resources as unique permissions**: files, sockets, GPU memory and even a per-process IPv6 identity are linear values, acquired at start and released automatically.
- **Ownership without lifetimes**: parameters are read-only by default; `edit` mutates and `take` consumes, and the word is repeated at the call site.
- **Contracts**: `requires`, `ensures`, `invariant` and `example` clauses, checked at every call.
- **Untrusted AI output**: values produced by a language model are typed `Untrusted[T]` and cannot trigger effects without validation.
- **Hardware sentinel**: a `process` declares the platform guarantees it needs (`platform: ecc, spectre_mitigations`) and does not start where they cannot be verified.

The full design is in the paper (in Italian): [docs/paper.md](docs/paper.md).

## Status

**Prototype 0.2.** A complete interpreter for the language core, static checks, and a WebAssembly compiler for pure numeric functions. It is written in Python to reach the phase 1 experiment quickly; the final compiler will be rewritten once the language is stable.

| Phase | What | Status |
|---|---|---|
| 0 | Paper and syntax | done |
| 1 | Interpreter, static checks, first WebAssembly compiler | done (0.1, syntax hints in 0.2) |
| 1 | Experiment: Tessera vs Python written by a language model | ready; first local runs in progress ([experiment/](experiment/)) |
| 2 | Core: static types, full WebAssembly compiler, network capabilities | to do |
| 3 | AI training: tensors, differentiation, data provenance | to do |
| 4 | Verification and domains: verified compiler, databases, web, kernel | to do |

Full status, the decisions taken so far and the next steps: **[STATUS.md](STATUS.md)**.

## Try it

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

On Linux and macOS the path is `.venv/bin/pip`. Then, with the environment active:

```bash
python -m tessera run examples/checkout.tsr
```

| Command | What it does |
|---|---|
| `python -m tessera run file.tsr` | checks the program and runs its `process` or `fn main()` |
| `python -m tessera check file.tsr` | static checks without running (`--json` for errors a model can read) |
| `python -m tessera test file.tsr` | runs the `example` clauses as tests |
| `python -m tessera build file.tsr -o build` | produces `.wat` and `.wasm` |
| `python -m tessera call file.tsr function arg... [--wasm]` | calls a function, interpreted or compiled |
| `python -m pytest tests` | 61 tests, including differential testing of the interpreter against WebAssembly |

The prototype already enforces: declared effects, contracts, types at function boundaries, `edit` and `take`, integer overflow, division by zero, file permissions granted by the `process`, `Secret` values never printed, `Result` values never ignored, exhaustive `match`, platform requirements. Messages and documentation are currently in Italian; the rules are in [spec/semantics.md](spec/semantics.md).

## Repository layout

| Path | Contents |
|---|---|
| [docs/paper.md](docs/paper.md) | The paper: motivation, architecture, security model, evaluation |
| [spec/syntax.md](spec/syntax.md) | Syntax decisions, with rationale and token measurements |
| [spec/semantics.md](spec/semantics.md) | Execution rules decided while building the prototype |
| [spec/tessera.lark](spec/tessera.lark) | The formal grammar (LALR(1)) |
| [tessera/](tessera/) | The prototype: parser, interpreter, static checks, WebAssembly compiler, sentinel |
| [examples/](examples/) | `.tsr` programs. Runnable: `hello`, `checkout`, `prices`, `warehouse`, `permissions`, `numbers`. Illustrative (they use modules not written yet): `server`, `training`, `interop` |
| [experiment/](experiment/) | Phase 1 experiment: 20 tasks with hidden edge-case tests, run by Claude in Tessera and in Python |
| [tests/](tests/) | Prototype tests |
| [tools/check_grammar.py](tools/check_grammar.py) | Checks the grammar against the examples and 14 typical mistakes it must reject |

## Author and citation

Tessera is an original idea by **Stefano Stegani**, who wrote its design, grammar and paper. The code and texts may be reused, including commercially, under the license terms: **anyone redistributing Tessera or a derivative work must keep the [NOTICE](NOTICE) file, which credits the author**, and may not present it as their own.

To cite the project:

> Stefano Stegani, *Tessera: written by AI, hardened against AI*, 2026. DOI: [10.5281/zenodo.23855820](https://doi.org/10.5281/zenodo.23855820)

The DOI always points to the latest version; version 0.1.0 has its own DOI, [10.5281/zenodo.23855821](https://doi.org/10.5281/zenodo.23855821), archived on Zenodo.

The [CITATION.cff](CITATION.cff) file holds the same data in machine-readable form; GitHub uses it for the "Cite this repository" button.

## License

[Apache 2.0](LICENSE), with the attribution notice in [NOTICE](NOTICE).
