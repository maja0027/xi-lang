# Effect System Specification

Xi tracks computational effects through an algebraic effect system built into the type theory. Effects separate pure computations (which can be optimized, reordered, and memoized) from impure ones (which interact with the outside world).

---

## 1. Effect Sets

An effect set is a bitfield of possible effects:

| Bit | Name | Description |
|-----|------|-------------|
| 0 | `Pure` | No effects (empty set ∅) |
| 1 | `IO` | Console, file, network I/O |
| 2 | `Mut` | Mutable state (references) |
| 3 | `Exn` | May throw exceptions |
| 4 | `NonDet` | Nondeterministic choice |
| 5 | `Conc` | Concurrent/parallel execution |
| 6 | `Div` | May diverge (non-termination) |
| 7 | `FFI` | Foreign function interface |

Effect sets support union: `{IO, Mut}` means the computation may perform I/O and mutate state.

---

## 2. Effect-Annotated Types

```
!{E} T
```

A computation of type `T` that may perform effects in set `E`.

Examples:
- `!{IO} String` — reading from console produces a string
- `!{Mut} Int` — reading a mutable reference produces an int
- `!{IO, Exn} ()` — writing to a file may fail
- `Int` — equivalent to `!{∅} Int` (pure)

---

## 3. Subtyping and Lifting

Effect subtyping is covariant: if `E₁ ⊆ E₂`, then:

```
!{E₁} T  <:  !{E₂} T
```

This means pure computations can be used in any effectful context:

```
!{∅} Int  <:  !{IO} Int  <:  !{IO, Mut} Int
```

**Key properties (proved in Lean 4):**
- `E ⊆ E` (reflexivity)
- `E₁ ⊆ E₂ ∧ E₂ ⊆ E₃ ⟹ E₁ ⊆ E₃` (transitivity)
- `∅ ⊆ E` for all `E` (empty subset)
- `E ⊆ E ∪ F` (union weakening)

---

## 4. Effect Rules for Expressions

**Pure expressions:**
```
Γ ⊢ n : Int          (integer literal — pure)
Γ ⊢ "s" : String     (string literal — pure)
Γ ⊢ λx.e : A → B     (lambda — pure, body may be effectful)
```

**Effectful application:**
```
Γ ⊢ f : A → !{E₁} B    Γ ⊢ a : !{E₂} A
─────────────────────────────────────────────
Γ ⊢ f a : !{E₁ ∪ E₂} B
```

Effects from the function and argument are combined.

**Primitive effects:**
```
print : ∀a. a → !{IO} a
readLine : !{IO} String
throw : ∀a. String → !{Exn} a
ref : ∀a. a → !{Mut} (Ref a)
```

**Fix with divergence:**
```
Γ, f:T ⊢ body : !{E} T
────────────────────────────
Γ ⊢ μf.body : !{E ∪ Div} T
```

Recursive definitions may diverge, so `μ` adds the `Div` effect.

---

## 5. Effect Polymorphism

Functions can be polymorphic over effects:

```
map : ∀a b E. (a → !{E} b) → List a → !{E} (List b)
```

This lets `map` work with both pure and effectful functions:
- `map (λx. x + 1) [1,2,3]` — pure
- `map (λx. print x) [1,2,3]` — effectful (IO)

---

## 6. Effect Handlers (Future)

The roadmap includes algebraic effect handlers:

```
handle expr with {
  return x → ...
  throw e k → ...
}
```

Handlers intercept effects and provide implementations, similar to delimited continuations. This is planned for a future version.

---

## 7. Hardware Implications

The effect system directly impacts hardware execution:

- **Pure computations** (∅) can be freely parallelized, memoized, and reordered by the Xi-Machine
- **IO effects** are serialized through the Effect Control Unit (ECU)
- **Mut effects** require memory barriers between reduction cores
- **Div effects** trigger watchdog timers in hardware

The Xi-Machine's spark pool only generates parallel sparks for pure subexpressions, using effect annotations to determine what can safely run in parallel.

---

## 8. Binary Encoding

In the binary format, effects are encoded as an 8-bit field in the node:

```
node.effect = bit 0: IO
              bit 1: Mut
              bit 2: Exn
              bit 3: NonDet
              bit 4: Conc
              bit 5: Div
              bit 6: FFI
              bit 7: reserved
```

Pure nodes have `effect = 0x00`.
