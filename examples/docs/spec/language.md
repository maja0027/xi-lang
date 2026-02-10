# Language Specification

**Version:** 0.4.0 — February 2026

Xi is a dependently-typed language with exactly 10 primitive node types. Every program is a directed acyclic graph (DAG) of these nodes, content-addressed by SHA-256 hash.

---

## 1. Node Types

| Tag | Symbol | Name | Arity | Description |
|-----|--------|------|-------|-------------|
| 0x0 | λ | Lambda | 2 | Function abstraction: `λ(A). body` |
| 0x1 | @ | Application | 2 | Function application: `f a` |
| 0x2 | Π | Pi | 2 | Dependent function type: `Π(x:A). B` |
| 0x3 | Σ | Sigma | 2 | Dependent pair type: `Σ(x:A). B` |
| 0x4 | 𝒰 | Universe | 0 | Type of types at level *i*: `𝒰ᵢ` |
| 0x5 | μ | Fix | 2 | Fixed-point combinator: `μ(f:T). body` |
| 0x6 | ι | Inductive | n | Inductive type: `ι{C₁ \| C₂ \| ...}` |
| 0x7 | ≡ | Equality | 3 | Propositional equality: `a ≡_A b` |
| 0x8 | ! | Effect | 1 | Effect annotation: `!{E} T` |
| 0x9 | # | Primitive | 0 | Built-in operation or literal |

### 1.1 Why Exactly 10?

These 10 form a minimal complete basis for a dependently-typed calculus with effects:

- **λ, @, Π** — the core of any typed lambda calculus (Calculus of Constructions)
- **Σ** — dependent pairs, needed for existential types and records
- **𝒰** — universe hierarchy prevents Girard's paradox
- **μ** — general recursion (controlled by the effect system)
- **ι** — inductive types subsume Nat, Bool, List, Tree, etc.
- **≡** — propositional equality enables proofs
- **!** — effect annotations track IO, mutation, nondeterminism
- **#** — escape hatch for machine primitives (integers, strings)

Removing any one loses expressiveness. Adding more would be redundant.

---

## 2. Reduction Rules

Xi has four reduction rules:

### 2.1 β-reduction (Lambda Application)

```
(λA. body) arg  ⟶  body[0 := arg]
```

Standard beta reduction with de Bruijn substitution.

### 2.2 μ-reduction (Fixed-Point Unfolding)

```
μT. body  ⟶  body[0 := μT. body]
```

Unfolds the fixpoint by substituting the recursive reference with the fixpoint itself.

### 2.3 δ-reduction (Primitive Evaluation)

```
#[+] 2 3  ⟶  5
#[<] 4 7  ⟶  True
#[++] "a" "b"  ⟶  "ab"
```

Evaluates built-in operations on literal values.

### 2.4 ι-reduction (Pattern Matching)

```
match (Cᵢ a₁ ... aₖ) { C₀ → b₀ | ... | Cₙ → bₙ }  ⟶  bᵢ a₁ ... aₖ
```

Selects the branch matching the constructor index and applies constructor arguments.

---

## 3. Type System

Xi implements a predicative universe hierarchy with cumulativity:

```
𝒰₀ : 𝒰₁ : 𝒰₂ : ...
```

### 3.1 Typing Rules

**Variable:**  `Γ(x) = T  ⟹  Γ ⊢ x : T`

**Universe:**  `Γ ⊢ 𝒰ᵢ : 𝒰ᵢ₊₁`

**Lambda:**  `Γ ⊢ A : 𝒰ᵢ  ∧  Γ,x:A ⊢ b : B  ⟹  Γ ⊢ λA.b : Π(A).B`

**Application:**  `Γ ⊢ f : Π(A).B  ∧  Γ ⊢ a : A  ⟹  Γ ⊢ f a : B[0:=a]`

**Pi:**  `Γ ⊢ A : 𝒰ᵢ  ∧  Γ,x:A ⊢ B : 𝒰ⱼ  ⟹  Γ ⊢ Π(A).B : 𝒰_{max(i,j)}`

**Fix:**  `Γ ⊢ T : 𝒰ᵢ  ∧  Γ,f:T ⊢ b : T  ⟹  Γ ⊢ μT.b : T`

**Cumulativity:**  `Γ ⊢ t : 𝒰ᵢ  ∧  i ≤ j  ⟹  Γ ⊢ t : 𝒰ⱼ`

### 3.2 Hindley-Milner Inference

The surface syntax uses HM-style inference mapped to dependent types:

- Unification variables `?α` are introduced for unannotated parameters
- Constraints propagated through application and primitive ops
- Occurs check prevents infinite types
- Resolved types map to Π and literal types

### 3.3 Metatheory (Proved in Lean 4)

- **Subject Reduction:** `Γ ⊢ t : T ∧ t ⟶ t' ⟹ Γ ⊢ t' : T`
- **Progress:** `∅ ⊢ t : T ⟹ IsValue(t) ∨ ∃t'. t ⟶ t'`
- **Type Safety:** Well-typed closed programs don't get stuck
- **Universe Consistency:** `¬(𝒰ᵢ : 𝒰ᵢ)` — no Girard's paradox

See `formal/Xi/Basic.lean` for the full formalization.

---

## 4. Content Addressing

Every node is identified by the SHA-256 hash of its serialized form:

```
hash(node) = SHA-256(tag ∥ arity ∥ children_hashes ∥ data)
```

Properties:
- **Structural sharing:** Identical subexpressions are stored once
- **Deduplication:** `2 + 2` and `let x = 2 in x + x` share the node for `2`
- **Integrity:** Any modification changes the hash of all ancestors
- **Deterministic:** Same program always has the same hash, regardless of how it was constructed

---

## 5. Primitive Operations

| Opcode | Symbol | Type Signature |
|--------|--------|---------------|
| 0x10 | + | Int → Int → Int |
| 0x11 | - | Int → Int → Int |
| 0x12 | * | Int → Int → Int |
| 0x13 | / | Int → Int → Int |
| 0x14 | % | Int → Int → Int |
| 0x20 | == | Int → Int → Bool |
| 0x21 | < | Int → Int → Bool |
| 0x22 | > | Int → Int → Bool |
| 0x30 | not | Bool → Bool |
| 0x31 | && | Bool → Bool → Bool |
| 0x32 | ∥∥ | Bool → Bool → Bool |
| 0x40 | ++ | String → String → String |
| 0x41 | strlen | String → Int |
| 0x01 | print | ∀a. a → !{IO} a |

---

## 6. Surface Syntax

The surface syntax compiles to the binary graph representation.

### 6.1 Expressions

```
expr ::= λ params . expr           -- lambda
       | let name = expr in expr   -- let binding
       | if expr then expr else expr
       | match expr { branches }   -- pattern matching
       | fix name . expr           -- recursion
       | expr binop expr           -- binary operator
       | expr expr                 -- application
       | atom

atom ::= integer | string | bool | name | ( expr )

binop ::= + | - | * | / | % | == | < | > | ++ | && | ||
```

### 6.2 Declarations

```
decl ::= def name params = expr    -- function definition
       | type Name = constructors  -- algebraic data type
       | import ModuleName         -- module import
```

### 6.3 Algebraic Data Types

```
type Color = Red | Green | Blue
type Maybe = Nothing | Just Int
type Shape = Circle Int | Rect Int Int | Point
type List = Nil | Cons Int List
```

Constructors are numbered left-to-right starting at 0. Pattern matching uses constructor index for ι-reduction.
