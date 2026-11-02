# Tessera reference (prototype 0.1)

Tessera looks a little like Rust and Python, but it is **neither**: follow this page exactly, and do not use anything it does not describe.

## A complete example

```
module solution

pub type ParseError do
  case Empty
  case Invalid
end type ParseError

pub fn first_digit(text: Str) -> Result[i64, ParseError]
  effects: none
do
  if text.is_empty() do
    return Err(ParseError.Empty)
  end if
  var position = 0
  for c in text.chars() do
    if c.is_digits() do
      return Ok(position)
    end if
    position += 1
  end for
  return Err(ParseError.Invalid)
end fn first_digit
```

## Common mistakes (wrong → right)

| Wrong | Right |
|---|---|
| `fn f(x: i64) -> i64 do` or `{` | signature, then `effects: none` on its own line, then `do` on its own line |
| `let mut x = 0` | `var x = 0` (`let` is for values that never change) |
| `if x > 0 then` / `if x > 0:` / `if x > 0 {` | `if x > 0 do` … `end if` |
| `else do` / `elif` | `else` alone on its line / `else if x > 0 do` |
| `end` alone, or blocks closed out of order | `end if`, `end for`, `end while`, `end match`, `end fn name`, innermost first |
| `let y = if a then b else c` | `var y = c` then `if a do` / `y = b` / `end if` |
| `&&`, `\|\|`, `!x` | `and`, `or`, `not x` |
| `a and b or c` | `(a and b) or c` |
| `0 <= x < n` | `0 <= x and x < n` |
| `i64::MAX` | `9223372036854775807` |
| `1..=n` | `1..n + 1` (ranges exclude the end) |
| `\|x\| x * 2` | `fn(x) => x * 2` |
| `x++`, `;` at line end | `x += 1`, nothing at line end |
| `"a" + "b"` | `"{a}{b}"` or `parts.join("")` |
| `'c'` | `"c"` (a character is a one-letter `Str`) |
| `str`, `int`, `Vec<i64>`, `String` | `Str`, `i64`, `List[i64]` |
| `case Ok(n) => ...` | `case Ok(n):` then the statements on the next lines |
| `x.len` / `len(x)` | `x.len()` |
| `1 + 2.0` | `1.to_f64() + 2.0` (integers and decimals never mix) |

## Rules

- First line `module solution`. Comments start with `--`. One statement per line.
- Functions: `pub fn name(a: T) -> R`, then the clauses each on its own line, in this order: `effects: none` (mandatory), optional `requires: cond`, `ensures: cond` (`result` is the returned value there). Then `do`, the body, `end fn name`. Every path must `return`.
- Variables: `let x = 1` (fixed), `var y = 0` (changeable), `y += 1`. An empty list needs its type: `var out: List[i64] = []`.
- Control: `if c do … else if d do … else … end if`, `for i in 0..n do … end for`, `for x in items do … end for`, `while c do … end while`, `break`, `continue`.
- `match v do` / `case Some(x):` / `case None:` / `case _:` / `end match`; the statements of each case go on the following lines.
- Types: `i64`, `i32`, `f64` (write `2.0`), `bool`, `Str`, `List[T]`, `Option[T]` (`Some(x)`, `None`), `Result[T, E]` (`Ok(x)`, `Err(e)`), tuples `(A, B)`.
- Sum types: `pub type E do` / `case A` / `case B(field: i64)` / `end type E`; build with `E.A`, `E.B(field: 1)`.
- Integer `/` truncates toward zero, `%` keeps the dividend's sign. Overflow and division by zero stop the program.
- Strings: double quotes, escapes `\"` `\\` `\n` `\t` `\{` `\}`, interpolation `"{x}"`.
- `r?` returns the error early from a function that returns `Result`. Never ignore a `Result`.
- Built-ins: `min(a, b)`, `max(a, b)`, `abs(x)`, `from_code(n)`.

## Methods

- `Str`: `len()`, `is_empty()`, `upper()`, `lower()`, `trim()`, `contains(s)`, `starts_with(s)`, `ends_with(s)`, `replace(a, b)`, `split(sep)`, `chars()`, `slice(start, end)`, `code()`, `is_digits()` (non-empty, ASCII 0-9 only), `to_int()` → `Result[i64, Str]`, `to_str()`.
- `List`: `len()`, `is_empty()`, `get(i)` → `Option`, `first()`, `last()`, `contains(x)`, `map(f)`, `filter(f)`, `sum()`, `reversed()`, `sorted()`, `slice(start, end)`, `join(sep)`; on a `var` list: `push(x)`, `pop()`.
- Numbers: `to_f64()`, `to_int()`, `to_str()`, `abs()`. `Option`/`Result`: `is_some()`, `is_none()`, `is_ok()`, `is_err()`, `unwrap_or(d)`.
- Indexing `list[i]` stops the program if `i` is out of range.
