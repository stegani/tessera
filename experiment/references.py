# Copyright 2026 Stefano Stegani - Airgrid Network - www.airgrid.it
# SPDX-License-Identifier: Apache-2.0
"""Soluzioni di riferimento degli esercizi, in Tessera e in Python.

Servono a tre cose: dimostrare che ogni esercizio e' risolvibile, verificare che i test siano giusti
(`python -m experiment check`) e provare il banco di prova senza chiamare un modello (`--model reference`).
"""

TESSERA = {}
PYTHON = {}

# ---------------------------------------------------------------- parse_int_safe

TESSERA["parse_int_safe"] = '''module solution

pub type ParseError do
  case Empty
  case Invalid
  case OutOfRange
end type ParseError

pub fn parse_int_safe(text: Str) -> Result[i64, ParseError]
  effects: none
do
  if text.is_empty() do
    return Err(ParseError.Empty)
  end if
  var body = text
  if text.starts_with("-") do
    body = text.slice(1, text.len())
  end if
  if not body.is_digits() do
    return Err(ParseError.Invalid)
  end if
  match text.to_int() do
    case Ok(n):
      return Ok(n)
    case Err(_):
      return Err(ParseError.OutOfRange)
  end match
end fn parse_int_safe
'''

PYTHON["parse_int_safe"] = '''
class Empty(Exception):
    pass


class Invalid(Exception):
    pass


class OutOfRange(Exception):
    pass


def parse_int_safe(text: str) -> int:
    if text == "":
        raise Empty()
    body = text[1:] if text.startswith("-") else text
    if not body or not all("0" <= c <= "9" for c in body):
        raise Invalid()
    value = int(text)
    if not -2**63 <= value < 2**63:
        raise OutOfRange()
    return value
'''

# ---------------------------------------------------------------- safe_divide

TESSERA["safe_divide"] = '''module solution

pub type MathError do
  case DivisionByZero
  case Overflow
end type MathError

pub fn safe_divide(a: i64, b: i64) -> Result[i64, MathError]
  effects: none
do
  if b == 0 do
    return Err(MathError.DivisionByZero)
  end if
  if a == -9223372036854775807 - 1 and b == -1 do
    return Err(MathError.Overflow)
  end if
  return Ok(a / b)
end fn safe_divide
'''

PYTHON["safe_divide"] = '''
class DivisionByZero(Exception):
    pass


class Overflow(Exception):
    pass


def safe_divide(a: int, b: int) -> int:
    if b == 0:
        raise DivisionByZero()
    if a == -2**63 and b == -1:
        raise Overflow()
    quotient = abs(a) // abs(b)
    return quotient if (a >= 0) == (b >= 0) else -quotient
'''

# ---------------------------------------------------------------- average

TESSERA["average"] = '''module solution

pub fn average(values: List[i64]) -> Option[f64]
  effects: none
do
  if values.is_empty() do
    return None
  end if
  var total = 0.0
  for v in values do
    total += v.to_f64()
  end for
  return Some(total / values.len().to_f64())
end fn average
'''

PYTHON["average"] = '''
def average(values: list[int]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)
'''

# ---------------------------------------------------------------- word_count

TESSERA["word_count"] = '''module solution

pub fn word_count(text: Str) -> i64
  effects: none
do
  var count = 0
  for part in text.split(" ") do
    if not part.is_empty() do
      count += 1
    end if
  end for
  return count
end fn word_count
'''

PYTHON["word_count"] = '''
def word_count(text: str) -> int:
    return len([part for part in text.split(" ") if part])
'''

# ---------------------------------------------------------------- is_palindrome

TESSERA["is_palindrome"] = '''module solution

pub fn is_palindrome(text: Str) -> bool
  effects: none
do
  let letters = text.lower().replace(" ", "").chars()
  return letters == letters.reversed()
end fn is_palindrome
'''

PYTHON["is_palindrome"] = '''
def is_palindrome(text: str) -> bool:
    letters = text.lower().replace(" ", "")
    return letters == letters[::-1]
'''

# ---------------------------------------------------------------- fizzbuzz

TESSERA["fizzbuzz"] = '''module solution

pub fn fizzbuzz(n: i64) -> List[Str]
  effects: none
  requires: n >= 0
do
  var out: List[Str] = []
  for i in 1..n + 1 do
    if i % 15 == 0 do
      out.push("FizzBuzz")
    else if i % 3 == 0 do
      out.push("Fizz")
    else if i % 5 == 0 do
      out.push("Buzz")
    else
      out.push(i.to_str())
    end if
  end for
  return out
end fn fizzbuzz
'''

PYTHON["fizzbuzz"] = '''
def fizzbuzz(n: int) -> list[str]:
    out = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            out.append("FizzBuzz")
        elif i % 3 == 0:
            out.append("Fizz")
        elif i % 5 == 0:
            out.append("Buzz")
        else:
            out.append(str(i))
    return out
'''

# ---------------------------------------------------------------- max_subarray_sum

TESSERA["max_subarray_sum"] = '''module solution

pub fn max_subarray_sum(values: List[i64]) -> Option[i64]
  effects: none
do
  if values.is_empty() do
    return None
  end if
  var best = values[0]
  var current = values[0]
  for i in 1..values.len() do
    current = max(values[i], current + values[i])
    best = max(best, current)
  end for
  return Some(best)
end fn max_subarray_sum
'''

PYTHON["max_subarray_sum"] = '''
def max_subarray_sum(values: list[int]) -> int | None:
    if not values:
        return None
    best = current = values[0]
    for v in values[1:]:
        current = max(v, current + v)
        best = max(best, current)
    return best
'''

# ---------------------------------------------------------------- merge_sorted

TESSERA["merge_sorted"] = '''module solution

pub fn merge_sorted(a: List[i64], b: List[i64]) -> List[i64]
  effects: none
do
  var out: List[i64] = []
  var i = 0
  var j = 0
  while i < a.len() and j < b.len() do
    if a[i] <= b[j] do
      out.push(a[i])
      i += 1
    else
      out.push(b[j])
      j += 1
    end if
  end while
  while i < a.len() do
    out.push(a[i])
    i += 1
  end while
  while j < b.len() do
    out.push(b[j])
    j += 1
  end while
  return out
end fn merge_sorted
'''

PYTHON["merge_sorted"] = '''
def merge_sorted(a: list[int], b: list[int]) -> list[int]:
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i])
            i += 1
        else:
            out.append(b[j])
            j += 1
    return out + a[i:] + b[j:]
'''

# ---------------------------------------------------------------- dedupe

TESSERA["dedupe"] = '''module solution

pub fn dedupe(values: List[i64]) -> List[i64]
  effects: none
do
  var out: List[i64] = []
  for v in values do
    if not out.contains(v) do
      out.push(v)
    end if
  end for
  return out
end fn dedupe
'''

PYTHON["dedupe"] = '''
def dedupe(values: list[int]) -> list[int]:
    seen, out = set(), []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out
'''

# ---------------------------------------------------------------- caesar

TESSERA["caesar"] = '''module solution

pub fn caesar(text: Str, shift: i64) -> Str
  effects: none
do
  let k = (shift % 26 + 26) % 26
  var out: List[Str] = []
  for c in text.chars() do
    let code = c.code()
    if code >= 97 and code <= 122 do
      out.push(from_code(97 + (code - 97 + k) % 26))
    else if code >= 65 and code <= 90 do
      out.push(from_code(65 + (code - 65 + k) % 26))
    else
      out.push(c)
    end if
  end for
  return out.join("")
end fn caesar
'''

PYTHON["caesar"] = '''
def caesar(text: str, shift: int) -> str:
    k = shift % 26
    out = []
    for c in text:
        if "a" <= c <= "z":
            out.append(chr(97 + (ord(c) - 97 + k) % 26))
        elif "A" <= c <= "Z":
            out.append(chr(65 + (ord(c) - 65 + k) % 26))
        else:
            out.append(c)
    return "".join(out)
'''

# ---------------------------------------------------------------- validate_username

TESSERA["validate_username"] = '''module solution

pub type UsernameError do
  case TooShort
  case TooLong
  case InvalidChar
end type UsernameError

pub fn validate_username(name: Str) -> Result[Str, UsernameError]
  effects: none
do
  if name.len() < 3 do
    return Err(UsernameError.TooShort)
  end if
  if name.len() > 16 do
    return Err(UsernameError.TooLong)
  end if
  for c in name.chars() do
    if not (c in "abcdefghijklmnopqrstuvwxyz0123456789_") do
      return Err(UsernameError.InvalidChar)
    end if
  end for
  return Ok(name)
end fn validate_username
'''

PYTHON["validate_username"] = '''
class TooShort(Exception):
    pass


class TooLong(Exception):
    pass


class InvalidChar(Exception):
    pass


ALLOWED = set("abcdefghijklmnopqrstuvwxyz0123456789_")


def validate_username(name: str) -> str:
    if len(name) < 3:
        raise TooShort()
    if len(name) > 16:
        raise TooLong()
    if any(c not in ALLOWED for c in name):
        raise InvalidChar()
    return name
'''

# ---------------------------------------------------------------- is_safe_relative_path

TESSERA["is_safe_relative_path"] = '''module solution

pub fn is_safe_relative_path(path: Str) -> bool
  effects: none
do
  if path.is_empty() or path.starts_with("/") do
    return false
  end if
  if path.contains("\\\\") or path.contains(":") do
    return false
  end if
  for segment in path.split("/") do
    if segment.is_empty() or segment == "." or segment == ".." do
      return false
    end if
  end for
  return true
end fn is_safe_relative_path
'''

PYTHON["is_safe_relative_path"] = '''
def is_safe_relative_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\\\" in path or ":" in path:
        return False
    return all(segment not in ("", ".", "..") for segment in path.split("/"))
'''

# ---------------------------------------------------------------- escape_html

TESSERA["escape_html"] = '''module solution

pub fn escape_html(text: Str) -> Str
  effects: none
do
  let step1 = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
  return step1.replace("\\"", "&quot;").replace("'", "&#39;")
end fn escape_html
'''

PYTHON["escape_html"] = '''
def escape_html(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))
'''

# ---------------------------------------------------------------- luhn_valid

TESSERA["luhn_valid"] = '''module solution

pub fn luhn_valid(number: Str) -> bool
  effects: none
do
  let digits = number.replace(" ", "")
  if digits.len() < 2 or not digits.is_digits() do
    return false
  end if
  var total = 0
  var double = false
  for c in digits.chars().reversed() do
    var d = c.to_int().unwrap_or(0)
    if double do
      d *= 2
      if d > 9 do
        d -= 9
      end if
    end if
    total += d
    double = not double
  end for
  return total % 10 == 0
end fn luhn_valid
'''

PYTHON["luhn_valid"] = '''
def luhn_valid(number: str) -> bool:
    digits = number.replace(" ", "")
    if len(digits) < 2 or not all("0" <= c <= "9" for c in digits):
        return False
    total = 0
    for i, c in enumerate(reversed(digits)):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0
'''

# ---------------------------------------------------------------- roman_to_int

TESSERA["roman_to_int"] = '''module solution

pub type RomanError do
  case Empty
  case Invalid
end type RomanError

fn value_of(c: Str) -> i64
  effects: none
do
  match c do
    case "I":
      return 1
    case "V":
      return 5
    case "X":
      return 10
    case "L":
      return 50
    case "C":
      return 100
    case "D":
      return 500
    case "M":
      return 1000
    case _:
      return 0
  end match
end fn value_of

fn to_roman(n: i64) -> Str
  effects: none
do
  let values = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
  let symbols = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
  var rest = n
  var out: List[Str] = []
  for i in 0..values.len() do
    while rest >= values[i] do
      out.push(symbols[i])
      rest -= values[i]
    end while
  end for
  return out.join("")
end fn to_roman

pub fn roman_to_int(text: Str) -> Result[i64, RomanError]
  effects: none
do
  if text.is_empty() do
    return Err(RomanError.Empty)
  end if
  let chars = text.chars()
  var total = 0
  for i in 0..chars.len() do
    let v = value_of(chars[i])
    if v == 0 do
      return Err(RomanError.Invalid)
    end if
    if i + 1 < chars.len() and v < value_of(chars[i + 1]) do
      total -= v
    else
      total += v
    end if
  end for
  if total < 1 or total > 3999 or to_roman(total) != text do
    return Err(RomanError.Invalid)
  end if
  return Ok(total)
end fn roman_to_int
'''

PYTHON["roman_to_int"] = '''
class Empty(Exception):
    pass


class Invalid(Exception):
    pass


VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
TABLE = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"),
         (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def to_roman(n: int) -> str:
    out = []
    for value, symbol in TABLE:
        while n >= value:
            out.append(symbol)
            n -= value
    return "".join(out)


def roman_to_int(text: str) -> int:
    if text == "":
        raise Empty()
    if any(c not in VALUES for c in text):
        raise Invalid()
    total = 0
    for i, c in enumerate(text):
        v = VALUES[c]
        if i + 1 < len(text) and v < VALUES[text[i + 1]]:
            total -= v
        else:
            total += v
    if not 1 <= total <= 3999 or to_roman(total) != text:
        raise Invalid()
    return total
'''

# ---------------------------------------------------------------- binary_search

TESSERA["binary_search"] = '''module solution

pub fn binary_search(values: List[i64], target: i64) -> Option[i64]
  effects: none
do
  var low = 0
  var high = values.len()
  while low < high do
    let mid = low + (high - low) / 2
    if values[mid] < target do
      low = mid + 1
    else
      high = mid
    end if
  end while
  if low < values.len() and values[low] == target do
    return Some(low)
  end if
  return None
end fn binary_search
'''

PYTHON["binary_search"] = '''
def binary_search(values: list[int], target: int) -> int | None:
    low, high = 0, len(values)
    while low < high:
        mid = (low + high) // 2
        if values[mid] < target:
            low = mid + 1
        else:
            high = mid
    if low < len(values) and values[low] == target:
        return low
    return None
'''

# ---------------------------------------------------------------- allowed_requests

TESSERA["allowed_requests"] = '''module solution

pub fn allowed_requests(times: List[i64], window: i64, limit: i64) -> List[bool]
  effects: none
  requires: window > 0 and limit >= 0
do
  var accepted: List[i64] = []
  var out: List[bool] = []
  for t in times do
    var recent = 0
    for a in accepted do
      if a > t - window do
        recent += 1
      end if
    end for
    if recent < limit do
      accepted.push(t)
      out.push(true)
    else
      out.push(false)
    end if
  end for
  return out
end fn allowed_requests
'''

PYTHON["allowed_requests"] = '''
def allowed_requests(times: list[int], window: int, limit: int) -> list[bool]:
    accepted, out = [], []
    for t in times:
        recent = sum(1 for a in accepted if a > t - window)
        if recent < limit:
            accepted.append(t)
            out.append(True)
        else:
            out.append(False)
    return out
'''

# ---------------------------------------------------------------- checked_factorial

TESSERA["checked_factorial"] = '''module solution

pub type MathError do
  case Negative
  case Overflow
end type MathError

pub fn checked_factorial(n: i64) -> Result[i64, MathError]
  effects: none
do
  if n < 0 do
    return Err(MathError.Negative)
  end if
  if n > 20 do
    return Err(MathError.Overflow)
  end if
  var acc = 1
  for i in 2..n + 1 do
    acc *= i
  end for
  return Ok(acc)
end fn checked_factorial
'''

PYTHON["checked_factorial"] = '''
class Negative(Exception):
    pass


class Overflow(Exception):
    pass


def checked_factorial(n: int) -> int:
    if n < 0:
        raise Negative()
    result = 1
    for i in range(2, n + 1):
        result *= i
        if result >= 2**63:
            raise Overflow()
    return result
'''

# ---------------------------------------------------------------- rle_encode

TESSERA["rle_encode"] = '''module solution

pub fn rle_encode(text: Str) -> Str
  effects: none
do
  let chars = text.chars()
  var out: List[Str] = []
  var i = 0
  while i < chars.len() do
    var j = i
    while j < chars.len() and chars[j] == chars[i] do
      j += 1
    end while
    out.push("{j - i}{chars[i]}")
    i = j
  end while
  return out.join("")
end fn rle_encode
'''

PYTHON["rle_encode"] = '''
def rle_encode(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        j = i
        while j < len(text) and text[j] == text[i]:
            j += 1
        out.append(f"{j - i}{text[i]}")
        i = j
    return "".join(out)
'''

# ---------------------------------------------------------------- checked_sum

TESSERA["checked_sum"] = '''module solution

pub type SumError do
  case Overflow
end type SumError

pub fn checked_sum(values: List[i64]) -> Result[i64, SumError]
  effects: none
do
  var total = 0
  for v in values do
    if v > 0 and total > 9223372036854775807 - v do
      return Err(SumError.Overflow)
    end if
    if v < 0 and total < -9223372036854775807 - 1 - v do
      return Err(SumError.Overflow)
    end if
    total += v
  end for
  return Ok(total)
end fn checked_sum
'''

PYTHON["checked_sum"] = '''
class Overflow(Exception):
    pass


def checked_sum(values: list[int]) -> int:
    total = 0
    for v in values:
        total += v
        if not -2**63 <= total < 2**63:
            raise Overflow()
    return total
'''
