# Tessera language reference (prototype 0.1)

Tessera is a statically structured, explicit programming language. Everything a function can do is declared in its signature, and whatever is not declared is rejected. This reference describes exactly what the current prototype supports: do not use anything that is not described here.

## File structure

```
module solution

pub type Shape do
  case Circle(radius: f64)
  case Square(side: f64)
end type Shape

pub fn area(shape: Shape) -> f64
  effects: none
  example: area(Square(side: 2.0)) == 4.0
do
  match shape do
    case Circle(r):
      return 3.14159 * r * r
    case Square(s):
      return s * s
  end match
end fn area
```

- The first line is `module <name>`. Comments start with `--`.
- Statements end at the end of the line. There are no semicolons and no braces.
- Blocks open with `do` and close with `end` plus the keyword that opened them: `end if`, `end for`, `end while`, `end match`, `end fn <name>`, `end type <Name>`.
- Indentation is not significant, but use two spaces per level.
- Type names are PascalCase (`ParseError`); everything else is snake_case (`parse_int`, `total`).

## Functions

```
pub fn name(a: i64, b: Str) -> Result[i64, MyError]
  doc: "Optional one-line description."
  effects: none
  requires: a >= 0
  ensures: result is Ok(v) implies v >= 0
  example: name(1, "x") == Ok(1)
do
  ...
end fn name
```

- Clauses come in this exact order: `doc` (optional), `effects` (mandatory), `requires`, `ensures`, `example` (each optional, repeatable).
- `effects: none` declares a pure function. A function that prints needs `effects: console`.
- `requires` is checked when the function is called, `ensures` when it returns (`result` is the returned value). A violation stops the program.
- `pub` makes the function visible outside the module. Omit `-> Type` for functions that return nothing.
- `return` is always explicit; a function with a return type must end every path with `return`.
- Parameters are read-only. `edit p: T` lets the function modify the caller's variable (call it as `f(edit x)`); `take p: T` consumes it (`f(take x)`).
- Anonymous functions: `fn(x) => x * 2`.

## Types

| Type | Values |
|---|---|
| `i64`, `i32` | integers (`42`, `-7`, `1_000`) |
| `f64` | decimals (`2.5`, `0.0`); always write the decimal point |
| `bool` | `true`, `false` |
| `Str` | `"text"`; a single character is a `Str` of length 1 |
| `List[T]` | `[1, 2, 3]`; an empty list needs a typed variable: `var out: List[i64] = []` |
| `(A, B)` | tuples: `(1, "a")`, unpacked with `let (x, y) = pair` |
| `Option[T]` | `Some(x)` or `None` |
| `Result[T, E]` | `Ok(x)` or `Err(e)` |

User types:

```
pub type Point do          -- struct
  x: f64
  y: f64
end type Point

pub type ParseError do     -- sum type: one `case` per variant
  case Empty
  case TooLong(limit: i64)
end type ParseError

pub type Cents = i64       -- a distinct type wrapping i64: Cents(1250)
```

- Construct with `Point(x: 1.0, y: 2.0)`, `ParseError.Empty`, `ParseError.TooLong(limit: 5)`. Variants can also be written without the type name: `Empty`.
- Read fields with `p.x`.

## Statements

```
let x = 10                 -- immutable
var total = 0              -- mutable
total += x                 -- also -=, *=, /=
if x > 5 do
  ...
else if x > 2 do
  ...
else
  ...
end if
for i in 0..n do           -- i = 0, 1, ..., n - 1
  ...
end for
for item in items do       -- also iterates the characters of a Str
  ...
end for
while i < n do
  ...
end while
match value do
  case Ok(n) if n > 0:
    ...
  case Ok(n):
    ...
  case Err(_):
    ...
end match
```

- `break` and `continue` work in loops.
- In `match`, each `case pattern:` is followed by its statements on the next lines. Patterns: a name (binds the value), `_`, a literal (`"I"`, `3`), a variant with sub-patterns (`Some(x)`, `Err(ParseError.Empty)`), a tuple. A match must cover every variant or end with `case _:`.
- `value is Pattern` tests a pattern in an expression: `if r is Ok(v) do ... end if`.

## Expressions and rules

- Arithmetic: `+ - * / %`. Integers and decimals never mix: convert with `x.to_f64()` or `f.to_int()`.
- Integer `/` truncates toward zero (`-7 / 2` is `-3`); `%` has the sign of the dividend (`-7 % 2` is `-1`).
- Integer overflow and division by zero are runtime errors: they stop the program.
- Comparisons: `== != < <= > >=`, and `in` (`x in list`, `"ab" in text`, `i in 0..10`). Only one comparison per expression: write `0 <= x and x < n`, never `0 <= x < n`.
- Logic: `and`, `or`, `not`, `implies`. `and` and `or` cannot be mixed without parentheses: `(a and b) or c`.
- Strings: double quotes only. Escapes: `\"`, `\\`, `\n`, `\t`, `\{`, `\}`. Interpolation: `"total: {x + 1}"`. Strings cannot be joined with `+`: use interpolation or `join`.
- `expr?` on a `Result` returns the `Err` from the current function (which must return a `Result`); on an `Option` returns `None`.
- A `Result` must never be ignored: handle it with `?`, `match` or `unwrap_or`.
- Indexing `list[i]` stops the program if `i` is out of range; `list.get(i)` returns an `Option`.
- Values are copied on assignment: changing a copy never changes the original.

## Built-in functions

`min(a, b)`, `max(a, b)`, `abs(x)`, `from_code(n)` (character with Unicode code `n`), `print(x)` (needs `effects: console`). Nothing needs to be imported.

## Methods

| On | Methods |
|---|---|
| `Str` | `len()`, `is_empty()`, `upper()`, `lower()`, `trim()`, `contains(s)`, `starts_with(s)`, `ends_with(s)`, `replace(old, new)`, `split(sep)` -> `List[Str]`, `split_once(sep)` -> `(Str, Str)` (second part empty if `sep` is absent), `chars()` -> `List[Str]`, `slice(start, end)` (characters `start` to `end - 1`), `code()` (Unicode code of a one-character `Str`), `is_digits()` (non-empty and only ASCII `0`-`9`), `to_int()` -> `Result[i64, Str]` (trims spaces, accepts a sign), `to_float()` -> `Result[f64, Str]`, `to_str()` |
| `List` | `len()`, `is_empty()`, `get(i)` -> `Option`, `first()`, `last()`, `contains(x)`, `map(f)`, `filter(f)`, `sum()`, `reversed()`, `sorted()`, `slice(start, end)`, `join(sep)` (list of `Str`), `to_str()`; on `var` lists only: `push(x)`, `pop()` -> `Option`, `clear()` |
| integers | `to_f64()`, `to_str()`, `abs()` |
| `f64` | `to_int()`, `to_str()`, `abs()`, `floor()`, `round()`, `sqrt()` |
| `Option`, `Result` | `is_some()`, `is_none()`, `is_ok()`, `is_err()`, `unwrap_or(default)` |

## Not available

No classes, inheritance, exceptions, `null`, dictionaries or sets, `unwrap()`, `elif`, ternary operator, `++`, braces, semicolons, single-quoted strings, string concatenation with `+`, implicit return, chained comparisons, or imports of standard modules.
