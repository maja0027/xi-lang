# Type System Specification

Xi implements a dependent type theory with universe polymorphism, effect tracking, and Hindley-Milner inference for the surface language.

---

## 1. Universe Hierarchy

```
𝒰₀ : 𝒰₁ : 𝒰₂ : 𝒰₃ : ...
```

Each universe `𝒰ᵢ` contains all types expressible at level ≤ *i*. Cumulativity: if `A : 𝒰ᵢ` and `i ≤ j`, then `A : 𝒰ⱼ`.

**Consistency:** `𝒰ᵢ : 𝒰ᵢ` is not derivable (proved in Lean 4 via `no_type_in_type`). This prevents Girard's paradox, which would make the type system unsound.

Universe levels for type formers:
- `Π(x:A).B : 𝒰_{max(i,j)}` where `A : 𝒰ᵢ` and `B : 𝒰ⱼ`
- `Σ(x:A).B : 𝒰_{max(i,j)}`
- Inductive types: `ι{...} : 𝒰₀`

---

## 2. Built-in Types

| Type | Universe | Description | Literals |
|------|----------|-------------|----------|
| `Int` | `𝒰₀` | Machine integers (64-bit) | `0`, `42`, `-7` |
| `Bool` | `𝒰₀` | Boolean values | `True`, `False` |
| `String` | `𝒰₀` | UTF-8 strings | `"hello"` |
| `Nat` | `𝒰₀` | Peano naturals | `Zero`, `Succ n` |

Int, Bool, and String are primitive (δ-reducible). Nat is defined inductively.

---

## 3. Function Types (Π)

```
Π(x : A). B
```

When `B` does not depend on `x`, this is the simple arrow type `A → B`.

Examples:
- `Int → Int` = `Π(_ : Int). Int`
- `∀a. a → a` = `Π(a : 𝒰₀). Π(_ : a). a`
- `Vec : Nat → 𝒰₀` = `Π(_ : Nat). 𝒰₀`

---

## 4. Pair Types (Σ)

```
Σ(x : A). B
```

When `B` does not depend on `x`, this is the product type `A × B`.

Dependent pairs encode existential types:
- `∃n:Nat. Vec n` = `Σ(n : Nat). Vec n`

---

## 5. Inductive Types (ι)

Inductive types are defined by their constructors:

```
ι{C₀ | C₁ | ... | Cₙ}
```

Each constructor `Cᵢ` can take arguments. The eliminator is pattern matching (ι-reduction).

Predefined inductive types:

| Type | Definition | Constructors |
|------|-----------|-------------|
| Bool | `ι{True \| False}` | `True : Bool`, `False : Bool` |
| Nat | `ι{Zero \| Succ Nat}` | `Zero : Nat`, `Succ : Nat → Nat` |
| Option a | `ι{None \| Some a}` | `None : Option a`, `Some : a → Option a` |
| List a | `ι{Nil \| Cons a (List a)}` | `Nil : List a`, `Cons : a → List a → List a` |

User-defined types via `type` declarations:

```
type Color = Red | Green | Blue
type Tree = Leaf Int | Branch Tree Tree
```

---

## 6. Equality Type (≡)

```
a ≡_A b
```

Propositional equality between `a` and `b` at type `A`. Inhabited by `refl : ∀(a : A). a ≡_A a`.

Used for proof-carrying code — a program can carry a proof that two values are equal, and this proof is checked by the type system.

---

## 7. Effect System

```
!{E} T
```

Annotates type `T` with effect set `E`. See `docs/spec/effects.md` for full specification.

Effect sets are bitfields:
- `∅` — pure (no effects)
- `IO` — input/output
- `Mut` — mutable state
- `Exn` — exceptions
- `NonDet` — nondeterminism
- `Conc` — concurrency

Subtyping: if `E₁ ⊆ E₂`, then `!{E₁} T <: !{E₂} T` (covariant).

Pure computations can be lifted to any effect context: `T → !{E} T` for any `E`.

---

## 8. Hindley-Milner Inference

The surface language uses HM inference, which is simpler than full dependent type checking:

### 8.1 Algorithm

1. **Generate constraints:** Walk the AST, introducing type variables `?α` for unknowns
2. **Unify:** Solve constraints by unification
3. **Resolve:** Replace all type variables with their solutions

### 8.2 Constraint Generation Rules

- `n : Int` for integer literals
- `"s" : String` for string literals
- `True, False : Bool`
- `f a : ?β` if `f : ?α → ?β` and `a : ?α`
- `λx. body : ?α → ?β` if `body : ?β` with `x : ?α`
- `x + y : Int` adds constraints `x : Int` and `y : Int`
- `x == y : Bool` adds `x : Int` and `y : Int`

### 8.3 Occurs Check

Before unifying `?α = T`, check that `?α` does not appear in `T`. This prevents infinite types like `?α = ?α → Int`.

### 8.4 Type Errors

When unification fails, the type checker reports the conflict with source position:

```
TypeError at 1:15: Cannot unify Int with String
  in expression: (λ(x : Int). x + 1) "hello"
```

---

## 9. Canonical Forms

Proved in Lean 4:

- If `∅ ⊢ v : Π(A).B` and `v` is a value, then `v = λA.body` for some `body`
- If `∅ ⊢ v : Int` and `v` is a value, then `v` is an integer literal
- If `∅ ⊢ v : Bool` and `v` is a value, then `v` is `True` or `False`
