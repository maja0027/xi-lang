# API: xi_compiler.py — Surface Syntax Compiler

Compiles Xi surface syntax (`.xi-src` files) into binary Node graphs.

## Classes

### `Compiler`
```python
class Compiler:
    def compile_expr(source: str) → Node
    def compile_program(source: str) → dict[str, Node]
    def run_program(source: str, entry: str = "main") → any
```

- `compile_expr`: Parse and compile a single expression
- `compile_program`: Parse a multi-definition program, return name→Node map
- `run_program`: Compile and immediately evaluate, returning the result

### `Span`
```python
class Span:
    file: str   # Source filename
    line: int   # 1-indexed line number
    col: int    # 1-indexed column
```

Attached to tokens and error messages for source location tracking.

## Exceptions

- `LexError(msg, span)` — tokenization failure (unterminated string, unknown character)
- `ParseError(msg, span)` — parse failure (unexpected token, undefined variable, unknown constructor)

## Functions

### `tokenize(source: str) → list[Token]`
Lexer supporting: Unicode operators (λ, μ, Π, →, ⇒), strings, integers, identifiers, keywords (`let`, `in`, `if`, `then`, `else`, `match`, `fix`, `def`, `type`, `import`).

### `format_error(source: str, error: ParseError) → str`
Pretty-prints an error with source context and position indicator:
```
1:5: Unexpected token '+'
  1 | 1 + + 2
          ^
```

## Example
```python
from xi_compiler import Compiler
c = Compiler()
result = c.run_program("""
    def double x = x + x
    def main = double 21
""")
assert result == 42
```
