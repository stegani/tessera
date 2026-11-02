# Copyright 2026 Stefano Stegani - Airgrid Network - www.airgrid.it
# SPDX-License-Identifier: Apache-2.0
"""Suggerimenti per gli errori di sintassi: dicono esattamente cosa scrivere.

Ogni regola nasce da un errore reale dei modelli locali nell'esperimento del 01/11/2026: quasi sempre
un'abitudine presa da un altro linguaggio (Rust, Python, Lua, C). I testi sono in inglese, perche' li
legge soprattutto un modello che deve correggersi.
"""
import re

# (condizione sulla riga o sul simbolo trovato, suggerimento). La prima regola che corrisponde vince.
REGOLE = [
    (lambda riga, tok, attesi: re.search(r"^\s*end\s+\w+", riga) and attesi and tok not in attesi,
     "Blocks must be closed in reverse order: the innermost open block is still waiting for its `end`. "
     "Close it first (for example `end if` before `end for`)."),
    (lambda riga, tok, attesi: re.search(r"\blet\s+mut\b", riga),
     "Tessera has no `let mut`: write `var name = value` for a variable you will change, `let name = value` otherwise."),
    (lambda riga, tok, attesi: re.search(r"^\s*(pub\s+)?(critical\s+)?fn\b.*\)\s*(->\s*.+?)?\s+do\s*$", riga),
     "After the signature, put each clause on its own line: first `effects: none` (mandatory), then `do` alone on "
     "the next line."),
    (lambda riga, tok, attesi: tok == "then" or re.search(r"\bthen\b", riga),
     "There is no `then` and no if-expression: write `if condition do`, then the statements, then `end if`. "
     "To choose a value, declare a `var` and assign it in each branch."),
    (lambda riga, tok, attesi: "::" in riga,
     "Tessera has no `::` paths: there is no `i64::MAX`, write the number itself (9223372036854775807); "
     "variants are written `Type.Variant`."),
    (lambda riga, tok, attesi: re.search(r"\|\s*\w+(\s*,\s*\w+)*\s*\|", riga),
     "Anonymous functions are written `fn(x) => expression`, not `|x| ...`."),
    (lambda riga, tok, attesi: "..=" in riga,
     "Ranges are written `a..b` and do not include b: for 1 to n inclusive write `1..n + 1`."),
    (lambda riga, tok, attesi: "&&" in riga or "||" in riga,
     "Use the words `and`, `or`, `not` instead of `&&`, `||`, `!`."),
    (lambda riga, tok, attesi: tok == "!" or re.search(r"![A-Za-z_(]", riga),
     "Use `not` instead of `!`: write `not condition`."),
    (lambda riga, tok, attesi: tok == ";" or riga.rstrip().endswith(";"),
     "No semicolons: write one statement per line."),
    (lambda riga, tok, attesi: tok in ("{", "}"),
     "No braces: blocks open with `do` and close with `end` plus the keyword (`end if`, `end for`, `end while`, "
     "`end match`, `end fn name`)."),
    (lambda riga, tok, attesi: tok == "elif" or re.search(r"^\s*elif\b", riga),
     "Write `else if condition do`, not `elif`."),
    (lambda riga, tok, attesi: re.search(r"^\s*(def|function|func)\s", riga),
     "Functions are declared with `fn name(param: Type) -> Type`, then `effects: none` and `do` on their own lines."),
    (lambda riga, tok, attesi: re.search(r"^\s*(if|for|while|else)\b.*:\s*$", riga) and not re.search(r"^\s*case\b", riga),
     "Blocks open with `do`, not with `:`: write `if x > 0 do`, `for x in items do`, `else` alone on its line."),
    (lambda riga, tok, attesi: re.search(r"^\s*case\b.*=>", riga),
     "In `match`, write `case Pattern:` and put the statements on the following lines; there is no `=>`."),
    (lambda riga, tok, attesi: re.search(r"^\s*end\s*$", riga),
     "Close each block with `end` plus its keyword: `end if`, `end for`, `end while`, `end match`, `end fn name`."),
    (lambda riga, tok, attesi: re.search(r"\b(Vec|Option|Result|List|HashMap)\s*<", riga),
     "Generic types use square brackets: `List[i64]`, `Option[Str]`, `Result[i64, MyError]`."),
    (lambda riga, tok, attesi: re.search(r":\s*(str|string|String|int|float|usize|isize|u32)\b", riga),
     "Types are `Str`, `i64`, `i32`, `f64`, `bool`, `List[T]`."),
    (lambda riga, tok, attesi: tok == "#" or re.search(r"^\s*#", riga),
     "Comments start with `--`."),
    (lambda riga, tok, attesi: tok == "'" or re.search(r"'[^']*'", riga),
     "Strings use double quotes: \"text\"."),
    (lambda riga, tok, attesi: "++" in riga,
     "Write `x += 1`; there is no `++`."),
    (lambda riga, tok, attesi: re.search(r"^\s*(let|var)\b.*=\s*if\b", riga),
     "There is no if-expression: declare `var x = default` and assign it inside `if ... do ... end if`."),
    (lambda riga, tok, attesi: re.search(r"^\s*(pub\s+)?fn\b", riga) and tok == "->",
     "Write the return type after the parameters: `fn name(a: i64) -> i64`."),
]


def suggerimento(testo_riga, trovato, attesi=()):
    """Restituisce il suggerimento piu' adatto, oppure None."""
    for condizione, consiglio in REGOLE:
        try:
            if condizione(testo_riga or "", trovato or "", set(attesi)):
                return consiglio
        except re.error:
            continue
    return None
