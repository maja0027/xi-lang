# Example Programs

This guide walks through Xi example programs from simple to advanced.

---

## 1. Arithmetic

```
-- Simple calculation
def main = (2 + 3) * (4 + 5)
-- Result: 45
```

All standard operators are available: `+`, `-`, `*`, `/`, `%`, `==`, `<`, `>`.

## 2. Lambda Calculus

```
-- Identity function
def id x = x

-- Apply identity
def main = id 42
-- Result: 42
```

```
-- Function composition
def compose f g x = f (g x)

def double x = x + x
def inc x = x + 1

def main = compose double inc 20
-- Result: 42
```

## 3. Boolean Logic

```
def main = if 3 < 5 then 42 else 0
-- Result: 42
```

Booleans are constructors: `True` and `False`. Comparison operators produce booleans.

## 4. Pattern Matching

```
type Shape = Circle Int | Rect Int Int | Point

def area s = match s {
    Circle r → r * r * 3
  | Rect w h → w * h
  | Point → 0
}

def main = area (Rect 4 5)
-- Result: 20
```

## 5. Recursive Functions (Peano Naturals)

```
import Prelude

-- Addition on Peano naturals
def add a b = match a {
    Zero → b
  | Succ n → Succ (add n b)
}

-- 3 + 4 = 7
def main = add (Succ (Succ (Succ Zero))) (Succ (Succ (Succ (Succ Zero))))
-- Result: 7 (as Succ(Succ(Succ(Succ(Succ(Succ(Succ(Zero))))))))
```

## 6. Fibonacci

```
import Prelude

def fib n = match n {
    Zero → Zero
  | Succ m → match m {
      Zero → Succ Zero
    | Succ k → add (fib m) (fib (Succ k))
    }
}

def main = fib (Succ (Succ (Succ (Succ (Succ (Succ Zero))))))
-- Result: 8
```

## 7. Church Numerals

```
-- Church encoding of natural numbers
def zero f x = x
def one f x = f x
def two f x = f (f x)
def three f x = f (f (f x))

-- Church addition
def church_add m n f x = m f (n f x)

-- Convert Church numeral to Int
def to_int n = n (λx. x + 1) 0

def main = to_int (church_add three two)
-- Result: 5
```

## 8. Option Type

```
def safeDivide a b = if b == 0 then None else Some (a / b)

def main = match safeDivide 10 3 {
    None → 0
  | Some x → x
}
-- Result: 3
```

## 9. Strings

```
def greet name = "Hello, " ++ name ++ "!"

def main = greet "Xi"
-- Result: "Hello, Xi!"
```

## 10. Multi-Module Program

`lib/Math.xi-src`:
```
def square x = x * x
def cube x = x * x * x
def abs x = if x < 0 then 0 - x else x
```

`main.xi-src`:
```
import Prelude
import Math

def main = abs (square 3 - cube 2)
-- Result: 1
```

---

## Running Examples

```bash
# All examples are in the examples/ directory
./xi run examples/demo.xi-src

# Or use the REPL to explore interactively
./xi repl
```
