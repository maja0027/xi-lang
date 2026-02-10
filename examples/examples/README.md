# Xi Example Programs

## Surface Syntax (.xi-src)

| File | Description | Key Features |
|------|-------------|-------------|
| `hello.xi-src` | Hello world | Simplest program |
| `demo.xi-src` | Feature showcase | All language features |
| `fibonacci.xi-src` | Fibonacci sequence | Recursion, Nat, pattern matching |
| `adt.xi-src` | Algebraic data types | User-defined types, constructors |
| `church.xi-src` | Church numerals | Higher-order encoding |
| `option.xi-src` | Safe division | Option type, error handling |
| `strings.xi-src` | String operations | Concatenation |
| `higher_order.xi-src` | Function composition | compose, twice, curry |
| `multidef.xi-src` | Multi-definition | clamp, abs, min, max |

## Compiled Binary (.xi)

| File | Description | Size |
|------|-------------|------|
| `hello_world.xi` | String literal | 24 B |
| `compiled_hello.xi` | Compiled "Hello, World!" | 24 B |
| `arithmetic_3_5_2.xi` | `(3 + 5) * 2` | ~39 B |
| `lambda_double_21.xi` | `(λx. x+x) 21` | ~33 B |
| `string_concat.xi` | `"Hello, " ++ "Xi!"` | 37 B |

## Python API Examples

| File | Description |
|------|-------------|
| `xi_examples.py` | Programmatic API usage — build, optimize, serialize, evaluate |

## Running

```bash
# Run any .xi-src file
./xi run examples/fibonacci.xi-src

# Run from REPL
./xi repl
Ξ> import Prelude
Ξ> fib (Succ (Succ (Succ (Succ (Succ (Succ Zero))))))
8 : Nat
```
