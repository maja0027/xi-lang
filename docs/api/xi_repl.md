# API: xi_repl.py — Interactive REPL

Read-Eval-Print Loop for interactive Xi development.

## Classes

### `XiREPL`
```python
class XiREPL:
    def __init__()
    def start()                    # Enter interactive loop
    def eval_line(line: str) → str # Evaluate one input line
```

## Commands

| Input | Action |
|-------|--------|
| Expression | Evaluate and print result with type |
| `def name params = expr` | Define persistent function |
| `type Name = C1 \| C2 ...` | Define algebraic data type |
| `import Module` | Load module definitions |
| `:type expr` | Show inferred type without evaluating |
| `:graph expr` | Show DOT graph of expression |
| `:quit` | Exit REPL |
| `:help` | Show help message |

## Example Session
```
Ξ> 2 + 3
5 : Int

Ξ> def double x = x + x
double : Int → Int defined

Ξ> double 21
42 : Int

Ξ> import Prelude
Imported Prelude (15 definitions)

Ξ> fib (Succ (Succ (Succ (Succ (Succ (Succ Zero))))))
8 : Nat
```
