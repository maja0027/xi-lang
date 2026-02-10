# Xi Standard Library

**Version:** 0.1-draft
**Author:** Alex P. Slaby

---

## Overview

The Xi standard library is built entirely from the 10 primitive constructs. Every definition below is a graph of `λ`, `@`, `Π`, `Σ`, `𝒰`, `μ`, `ι`, `≡`, `!`, and `#` nodes. This document uses debug notation for readability.

---

## Layer 1: Foundational Types

### Unit
```
Unit = ι { tt : Unit }
```

### Bool
```
Bool = ι { true : Bool | false : Bool }
not : Bool → Bool
and : Bool → Bool → Bool
or  : Bool → Bool → Bool
if  : Π(A : 𝒰₀). Bool → A → A → A
```

### Natural Numbers
```
Nat = ι { zero : Nat | succ : Nat → Nat }
add : Nat → Nat → Nat
mul : Nat → Nat → Nat
sub : Nat → Nat → Nat        -- saturating
eq  : Nat → Nat → Bool
lt  : Nat → Nat → Bool
```

### Option
```
Option = ι (A : 𝒰₀) { none : Option A | some : A → Option A }
map     : Π(A B : 𝒰₀). (A → B) → Option A → Option B
flatMap : Π(A B : 𝒰₀). (A → Option B) → Option A → Option B
```

### Result
```
Result = ι (E A : 𝒰₀) { err : E → Result E A | ok : A → Result E A }
```

### Fin (Bounded Natural Numbers)
```
Fin = ι (n : Nat) { fzero : Fin (succ n) | fsucc : Fin n → Fin (succ n) }
```

---

## Layer 2: Data Structures

### List
```
List = ι (A : 𝒰₀) { nil : List A | cons : A → List A → List A }
head, tail, length, map, filter, fold, reverse, concat, zip
```

### Vector (Length-Indexed List)
```
Vec = ι (A : 𝒰₀) (n : Nat) {
  vnil  : Vec A zero
  vcons : Π(k : Nat). A → Vec A k → Vec A (succ k)
}
vindex : Π(A : 𝒰₀). Π(n : Nat). Vec A n → Fin n → A    -- safe indexing
```

### Binary Tree
```
Tree = ι (A : 𝒰₀) { leaf : A → Tree A | node : Tree A → Tree A → Tree A }
```

### String
```
Char   = Nat    -- Unicode code point
String = List Char
```

---

## Layer 2: Verified Algorithms

### Verified Sort
```
sort : Π(xs : List Nat). Σ(ys : List Nat). Σ(_ : Sorted ys). Permutation xs ys
```

### Safe Division
```
divmod : Π(a : Nat). Π(b : Nat). (b ≡ zero → ⊥) → Σ(q : Nat). Σ(r : Nat). (a ≡ add (mul q b) r)
```

---

## Layer 3: IO and Effects

```
putStrLn  : String → !{IO} Unit
getLine   : !{IO} String
readFile  : String → !{IO, Exn} String
writeFile : String → String → !{IO, Exn} Unit
newRef    : Π(A : 𝒰₀). A → !{Mut} (Ref A)
readRef   : Π(A : 𝒰₀). Ref A → !{Mut} A
fork      : !{E} Unit → !{Conc} Thread
```
