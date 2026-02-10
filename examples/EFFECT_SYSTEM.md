# Xi Effect System

**Version:** 0.1-draft
**Author:** Alex P. Slaby

---

## Overview

In most programming languages, any function can secretly perform side effects. Xi makes all effects **explicit in the type**. A function's type tells you exactly what it can and cannot do.

---

## Standard Effects

| Effect | Tag | Description |
|--------|-----|-------------|
| `IO` | `0x01` | Input/output: file access, network, console |
| `Mut` | `0x02` | Mutable state: reading/writing references |
| `Nondet` | `0x04` | Nondeterminism: random numbers, scheduling |
| `Exn` | `0x08` | Exceptions: computations that may fail |
| `Conc` | `0x10` | Concurrency: forking, joining, synchronization |

## Effect Sets and Subtyping

```
!{IO} T              -- may perform IO
!{IO, Exn} T         -- may perform IO or throw
!{∅} T  ≡  T         -- pure computation
```

A computation with fewer effects can be used where more effects are expected (covariant subtyping). Pure functions can be used in any effectful context.

## Effect Handlers

Effects can be intercepted and reinterpreted:

```
toOption : !{Exn} A → Option A
toOption = handle _ with {
  return x   → some x
  throw _, _ → none
}
```

After handling, the `Exn` effect is removed from the type.

## Effect Algebra

Effect sets form a bounded join-semilattice with union, intersection, empty set (pure), and top (all effects).

## User-Defined Effects

```
effect Database where
  query  : SQL → Database ResultSet
  insert : Table → Row → Database Unit

runWithPostgres : Connection → !{Database} A → !{IO, Exn} A
```
