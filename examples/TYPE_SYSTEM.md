# Xi Type System

**Version:** 0.1-draft
**Author:** Alex P. Slaby

---

## Overview

Xi's type system is based on the **Calculus of Inductive Constructions (CIC)** — the same foundation used by Coq/Rocq and Lean. It features dependent types, a cumulative universe hierarchy, inductive types with pattern matching, and propositional equality.

---

## Core Concepts

### Types Are First-Class

In Xi, types are values. They can be stored in data structures, passed as function arguments, and returned from functions.

```
Nat : 𝒰₀               -- Nat is a type
𝒰₀ : 𝒰₁                -- 𝒰₀ is a type (of types)
List : 𝒰₀ → 𝒰₀          -- List is a function from types to types
```

### Dependent Types

Types can **depend on values**:

```
Vec : 𝒰₀ → Nat → 𝒰₀                -- vector of exactly n elements
zeros : Π(n : Nat). Vec Float n      -- returns a vector of given length
concat : Π(A : 𝒰₀). Π(m n : Nat). Vec A m → Vec A n → Vec A (m + n)
```

The type checker statically verifies that `concat` returns a vector of the correct length.

---

## What Dependent Types Catch

### Buffer Overflows

```
index : Π(A : 𝒰₀). Π(n : Nat). Vec A n → Fin n → A
```

`Fin n` has exactly `n` inhabitants (0..n-1). Out-of-bounds access is a **type error**.

### Null Pointer Dereference

```
Option A = ι { none : Option A | some : A → Option A }
unwrap : Π(A : 𝒰₀). Π(x : Option A). (x ≡ none → ⊥) → A
```

There is no null. Extracting a value requires proving it exists.

### Division by Zero

```
div : Π(a : Int). Π(b : Int). (b ≡ 0 → ⊥) → Int
```

The third argument is a proof that `b ≠ 0`.

### Race Conditions

```
Ref : 𝒰₀ → 𝒰₀
read  : Π(A : 𝒰₀). Ref A → !{Mut} A
locked : Π(A : 𝒰₀). Ref A → !{Conc, Mut} A  -- acquires lock
```

The effect system forces concurrent code to use synchronization primitives.

---

## Universe Hierarchy

```
𝒰₀ : 𝒰₁ : 𝒰₂ : 𝒰₃ : ...
```

Each universe contains types from lower universes. This prevents Girard's paradox.

**Universe polymorphism** avoids redundant definitions:
```
id : Π(l : Level). Π(A : 𝒰ₗ). A → A
```

---

## Curry-Howard Correspondence

Types are propositions, programs are proofs:

| Logic | Xi Type |
|---|---|
| Implication (A → B) | Function type `Π(_ : A). B` |
| Conjunction (A ∧ B) | Pair type `Σ(_ : A). B` |
| Universal (∀x. P(x)) | `Π(x : A). P x` |
| Existential (∃x. P(x)) | `Σ(x : A). P x` |
| True | `Unit` (one constructor) |
| False | `⊥` (no constructors) |

### Verified Sort Example

```
sort : Π(xs : List Nat).
       Σ(ys : List Nat).
       Σ(_ : Sorted ys).
       Permutation xs ys
```

To inhabit this type, one must produce a sorted list AND proofs that it's sorted and a permutation of the input.

---

## Type Checking

Xi uses **bidirectional type checking** alternating between inference and checking modes, with **pattern unification** for solving metavariables. Type checking is decidable for all well-formed programs.
