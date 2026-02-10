# Quick Start Guide

Get up and running with Xi in under 5 minutes.

---

## 1. Installation

### From Source

```bash
git clone https://github.com/hovinek/xi-lang.git
cd xi-lang
pip install -e .
```

### With Docker

```bash
docker build -t xi-lang .
docker run -it xi-lang repl
```

### Requirements

- Python 3.10+
- No external dependencies for core functionality
- Optional: `hypothesis` for property-based tests, `graphviz` for visualization

---

## 2. Hello World

### Interactive REPL

```bash
python -m xi_repl
# or
./xi repl
```

```
Ξ — Xi Language REPL v0.2
Type :help for commands, :quit to exit

Ξ> 2 + 3
5 : Int

Ξ> "Hello, " ++ "Xi!"
"Hello, Xi!" : String

Ξ> (λx. x * x) 7
49 : Int
```

### From a File

Create `hello.xi-src`:

```
def main = (2 + 3) * (4 + 5)
```

Run it:

```bash
./xi run hello.xi-src
# Output: 45
```

---

## 3. Defining Functions

```
Ξ> def double x = x + x
double : Int → Int defined

Ξ> double 21
42 : Int

Ξ> def add3 a b c = a + b + c
add3 : Int → Int → Int → Int defined

Ξ> add3 10 20 12
42 : Int
```

---

## 4. Algebraic Data Types

```
Ξ> type Color = Red | Green | Blue
Defined Color with 3 constructors

Ξ> match Green { Red → 1 | Green → 2 | Blue → 3 }
2 : Int
```

Use the standard library for built-in types:

```
Ξ> import Prelude
Imported Prelude (15 definitions)

Ξ> add (Succ (Succ Zero)) (Succ (Succ (Succ Zero)))
5 : Nat

Ξ> fib (Succ (Succ (Succ (Succ (Succ (Succ Zero))))))
8 : Nat
```

---

## 5. Pattern Matching

```
Ξ> match Succ (Succ Zero) { Zero → 0 | Succ n → 1 }
1 : Int

Ξ> def isZero n = match n { Zero → True | Succ m → False }
isZero : Nat → Bool defined
```

---

## 6. Programs with Multiple Definitions

Create `math.xi-src`:

```
import Prelude

def square x = x * x

def sumSquares a b = square a + square b

def main = sumSquares 3 4
```

```bash
./xi run math.xi-src
# Output: 25
```

---

## 7. Type Checking

```bash
./xi check math.xi-src
# main : Int
# square : Int → Int
# sumSquares : Int → Int → Int
```

Or in the REPL:

```
Ξ> :type λx. λy. x + y
Int → Int → Int
```

---

## 8. Binary Compilation

```bash
# Compile to optimized Xi binary
./xi build math.xi-src -o math.xi

# Compile to compressed XiC format
./xi build --xic math.xi-src -o math.xic

# Run compiled binary
./xi run math.xi
```

---

## 9. Next Steps

- **Examples:** See `examples/` directory and [Examples Guide](examples.md)
- **Surface Syntax:** Full reference in [Language Spec](../spec/language.md)
- **Type System:** [Type Spec](../spec/types.md) and [Effect System](../spec/effects.md)
- **API Reference:** [API docs](../api/xi.md) for programmatic use
- **VS Code:** Install the [extension](vscode.md) for syntax highlighting
- **Docker:** [Docker guide](docker.md) for containerized development
