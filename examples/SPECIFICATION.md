# Xi Language Specification

**Version:** 0.1-draft
**Date:** February 2026
**Author:** Alex P. Slaby
**Status:** Research Draft

---

## 1. Introduction

Xi is a programming language whose programs are binary-encoded directed acyclic graphs (DAGs) composed of exactly 10 primitive node types. The language is founded on the **Calculus of Inductive Constructions (CIC)** extended with algebraic effects and hardware primitives.

This specification defines:
- The abstract syntax (graph structure)
- The type system (dependent types with universes)
- The operational semantics (graph reduction rules)
- The effect system (algebraic effects)
- The concrete representation (binary encoding)

### 1.1 Notation

Throughout this specification:
- `Γ` denotes a typing context (a sequence of type assumptions)
- `Γ ⊢ e : T` means "in context Γ, expression e has type T"
- `e[x ↦ v]` means "e with all free occurrences of x replaced by v"
- `e ⟶ e'` means "e reduces to e' in one step"
- `e ⟶* e'` means "e reduces to e' in zero or more steps"

### 1.2 Debug Notation

For readability, this specification uses a human-readable debug notation for Xi terms. This notation is **not part of the language** — it exists solely for documentation. The actual representation is the binary graph format defined in Section 4.

```
Debug notation          Meaning
─────────────────────   ──────────────────────────────────
λ(x : T). e            Abstraction with type annotation
e₁ e₂                  Application
Π(x : A). B            Dependent product (function type)
Σ(x : A). B            Dependent sum (pair type)
𝒰ᵢ                     Universe at level i
μ(f : T). e            Fixed point (recursion)
ι{C₁ | C₂ | ...}      Inductive type definition
a ≡_A b                Identity type
!{E₁, E₂} T           Effectful computation type
#[op]                   Hardware primitive
```

---

## 2. Design Principles

### 2.1 Immutable Core

The 10 primitive constructs form a complete, immutable foundation. No construct shall be added, removed, or modified. Any desired functionality must be expressed as a composition of existing constructs.

**Justification:** The Calculus of Inductive Constructions is known to be equivalent to higher-order predicate logic with induction. Any extension that is consistent with CIC can be encoded within CIC. Any extension that is inconsistent with CIC would compromise the soundness of the type system.

### 2.2 No Textual Syntax

Xi has no grammar, no parser, no lexer. Programs are graphs encoded directly in binary. There is no canonical textual representation.

### 2.3 Content-Addressed Identity

Two Xi terms are identical if and only if their binary encodings produce the same SHA-256 hash. There is no separate notion of "alpha equivalence" because variables are nameless (de Bruijn indices).

### 2.4 Effects as Data

Side effects are not implicit behaviors but explicit annotations in the type system. A function that performs IO has a different type than one that does not, and the type system enforces this distinction.

---

## 3. Core Constructs

### 3.1 Abstraction (λ) — Tag `0x0`

```
    Γ, x : A ⊢ e : B
─────────────────────────
  Γ ⊢ λ(x : A). e : Π(x : A). B
```

Creates a function that binds variable `x` of type `A` in body `e`.

**Graph structure:** Tag `0x0`, arity 2. Child 0: type annotation `A`. Child 1: body `e` (with de Bruijn index 0 referring to the bound variable).

### 3.2 Application (@) — Tag `0x1`

```
  Γ ⊢ f : Π(x : A). B    Γ ⊢ a : A
────────────────────────────────────────
         Γ ⊢ f a : B[x ↦ a]
```

Applies function `f` to argument `a`.

**Graph structure:** Tag `0x1`, arity 2. Child 0: function `f`. Child 1: argument `a`.

### 3.3 Dependent Product (Π) — Tag `0x2`

```
  Γ ⊢ A : 𝒰ᵢ    Γ, x : A ⊢ B : 𝒰ⱼ
──────────────────────────────────────
    Γ ⊢ Π(x : A). B : 𝒰_max(i,j)
```

The type of functions from `A` to `B`, where `B` may depend on the argument value. When `B` does not depend on `x`, this is the ordinary function type `A → B`.

**Graph structure:** Tag `0x2`, arity 2. Child 0: domain `A`. Child 1: codomain `B`.

### 3.4 Dependent Sum (Σ) — Tag `0x3`

```
  Γ ⊢ A : 𝒰ᵢ    Γ, x : A ⊢ B : 𝒰ⱼ
──────────────────────────────────────
    Γ ⊢ Σ(x : A). B : 𝒰_max(i,j)
```

The type of pairs `(a, b)` where `a : A` and `b : B[x ↦ a]`. When `B` does not depend on `x`, this is the ordinary product type `A × B`.

**Graph structure:** Tag `0x3`, arity 2. Child 0: first type `A`. Child 1: second type `B`.

### 3.5 Universe (𝒰) — Tag `0x4`

```
──────────────────
  Γ ⊢ 𝒰ᵢ : 𝒰ᵢ₊₁
```

Universes are the types of types forming a cumulative hierarchy: `𝒰₀ : 𝒰₁ : 𝒰₂ : ...`

**Cumulativity:** If `Γ ⊢ A : 𝒰ᵢ` and `i ≤ j`, then `Γ ⊢ A : 𝒰ⱼ`.

**Graph structure:** Tag `0x4`, arity 0. Data: universe level `i` (varint).

### 3.6 Fixed Point (μ) — Tag `0x5`

```
  Γ, f : T ⊢ e : T    T is a valid recursive type
────────────────────────────────────────────────────
            Γ ⊢ μ(f : T). e : T
```

Defines a recursive value. Reduction: `μ(f : T). e ⟶ e[f ↦ μ(f : T). e]`.

**Termination requirement:** All recursive definitions must be structurally decreasing.

**Graph structure:** Tag `0x5`, arity 2. Child 0: type `T`. Child 1: body `e`.

### 3.7 Induction (ι) — Tag `0x6`

An inductive type definition specifies a type name (implicit, identified by hash), type parameters, and a list of constructors.

**Example — Natural numbers:**
```
Nat = ι { zero : Nat | succ : Nat → Nat }
```

**Well-formedness:** The type being defined must appear only in strictly positive positions.

**Graph structure:** Tag `0x6`, variable arity. Children encode parameters and constructors.

### 3.8 Identity (≡) — Tag `0x7`

```
  Γ ⊢ A : 𝒰ᵢ    Γ ⊢ a : A    Γ ⊢ b : A
─────────────────────────────────────────────
          Γ ⊢ (a ≡_A b) : 𝒰ᵢ
```

The type of proofs that `a` and `b` are equal. Introduction: `refl : (a ≡_A a)`. Elimination: J-rule (path induction).

**Graph structure:** Tag `0x7`, arity 3. Child 0: type `A`. Child 1: left side `a`. Child 2: right side `b`.

### 3.9 Effect (!) — Tag `0x8`

```
  Γ ⊢ T : 𝒰ᵢ    E is a valid effect set
───────────────────────────────────────────
        Γ ⊢ !{E} T : 𝒰ᵢ
```

A computation that may perform effects in set `E` and produces a value of type `T`. Standard effects: `IO`, `Mut`, `Nondet`, `Exn`, `Conc`. The empty set `∅` means pure.

**Graph structure:** Tag `0x8`, arity 1+. Child 0: inner expression. Data: effect set bitfield.

### 3.10 Primitive (#) — Tag `0x9`

```
  op is a registered primitive operation
──────────────────────────────────────────
       Γ ⊢ #[op] : type_of(op)
```

Hardware-level operations: arithmetic, bitwise, IO, string operations. Their types are declared axiomatically.

**Graph structure:** Tag `0x9`, arity 0. Data: opcode (1 byte) + optional literal data.

---

## 4. Binary Encoding

See [BINARY_FORMAT.md](BINARY_FORMAT.md) for the complete wire format specification.

### File Header

| Offset | Size | Description |
|--------|------|-------------|
| `0x00` | 2 bytes | Magic: `0xCE 0x9E` (UTF-8 of Ξ) |
| `0x02` | 1 byte | Format version (currently `0x01`) |
| `0x03` | 2 bytes | Node count (big-endian uint16) |
| `0x05` | 2 bytes | Root node index (big-endian uint16) |
| `0x07` | ... | Node data |

### Node Header

```
Byte 0: [TTTT AAAA]    T = tag (4 bits), A = arity (4 bits)
```

---

## 5. Variable Binding

Xi uses **de Bruijn indices** for variable references. A variable is a natural number indicating how many binders are between the occurrence and its binding site.

```
Human notation:    λ(x : A). λ(y : B). x + y
De Bruijn:         λ(A). λ(B). #[add] (var 1) (var 0)
```

---

## 6. Reduction Rules

| Rule | Description |
|------|-------------|
| **β-reduction** | `@ (λ(A). e) v ⟶ e[0 ↦ v]` |
| **δ-reduction** | `@ (@ (#[add]) 3) 5 ⟶ 8` |
| **ι-reduction** | Pattern matching on constructors |
| **μ-reduction** | `μ(f:T). e ⟶ e[0 ↦ μ(f:T). e]` |

Default strategy: **call-by-need** (lazy with sharing). Metadata can override to eager.

---

## 7. Content Hash

```
hash(node) = SHA-256(tag ‖ arity ‖ hash(child₀) ‖ hash(child₁) ‖ ... ‖ data)
```

Metadata is NOT included in the hash. Two nodes differing only in metadata have identical hashes.

---

## 8. Formal Properties

- **Subject reduction:** Well-typed terms remain well-typed after reduction.
- **Progress:** Well-typed closed terms are either values or can be reduced.
- **Strong normalization** (type-level): All type computations terminate.
- **Consistency:** The empty type `⊥` has no closed inhabitants.
- **Decidable type checking:** For all well-formed Xi programs.

---

## References

1. T. Coquand and G. Huet. *The Calculus of Constructions*. 1988.
2. C. Paulin-Mohring. *Inductive Definitions in the System Coq*. 1993.
3. N.G. de Bruijn. *Lambda Calculus Notation with Nameless Dummies*. 1972.
4. G. Plotkin and J. Power. *Algebraic Operations and Generic Effects*. 2003.
5. A. Bauer and M. Pretnar. *Programming with Algebraic Effects and Handlers*. 2015.
6. Y. Lafont. *Interaction Nets*. 1990.
