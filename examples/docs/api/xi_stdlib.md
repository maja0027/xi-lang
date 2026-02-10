# API: xi_stdlib.py — Standard Library

Built-in data types and operations available without explicit import.

## Data Types

### Nat (Peano Naturals)
```
type Nat = Zero | Succ Nat
```

### Bool
```
type Bool = True | False
```

### Option
```
type Option a = None | Some a
```

### List
```
type List a = Nil | Cons a (List a)
```

### Result
```
type Result a b = Ok a | Err b
```

## Functions (via `import Prelude`)

| Function | Type | Description |
|----------|------|-------------|
| `id` | `a → a` | Identity |
| `const` | `a → b → a` | Constant function |
| `compose` | `(b → c) → (a → b) → a → c` | Function composition |
| `add` | `Nat → Nat → Nat` | Peano addition |
| `mul` | `Nat → Nat → Nat` | Peano multiplication |
| `fib` | `Nat → Nat` | Fibonacci |
| `fact` | `Nat → Nat` | Factorial |
| `min` | `Int → Int → Int` | Minimum |
| `max` | `Int → Int → Int` | Maximum |
| `mapOpt` | `(a → b) → Option a → Option b` | Map over Option |
| `isZero` | `Nat → Bool` | Test for Zero |
| `pred` | `Nat → Nat` | Predecessor |
| `not` | `Bool → Bool` | Boolean negation |

## Source

The stdlib is defined in `lib/Prelude.xi-src` using Xi surface syntax, demonstrating the language's self-hosting capability at the library level.
