# Xi Compared to Existing Languages and Systems

**Version:** 0.1-draft
**Author:** Alex P. Slaby

---

## Feature Ancestry

| Xi Feature | Precedent |
|---|---|
| Dependent types | Coq (1989), Lean 4, Agda, Idris |
| Content-addressed code | Unison (2015) |
| Binary format | WebAssembly |
| Algebraic effects | Koka, Eff, Frank |
| Graph reduction | Haskell/GHC (STG), HVM2, Reduceron |
| De Bruijn indices | Lambda calculus theory (1972) |
| Formal verification | Coq, Lean, Isabelle, F* |

## System Comparison

| Feature | JS | Rust | Haskell | Lean 4 | Unison | WASM | **Xi** |
|---|---|---|---|---|---|---|---|
| Human syntax | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | **✗** |
| Binary format | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | **✓** |
| Graph repr. | ✗ | ✗ | internal | internal | ✗ | ✗ | **✓** |
| Dependent types | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | **✓** |
| Verification | ✗ | partial | partial | ✓ | ✗ | ✗ | **✓** |
| Algebraic effects | ✗ | ✗ | monads | monads | ✓ | ✗ | **✓** |
| Content-addressed | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | **✓** |
| Immutable core | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓** |
| AI-optimized | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓** |

## What Xi Uniquely Combines

No existing system combines all of:
1. Binary graph representation (not text)
2. Dependent types (not simple types)
3. Content addressing (not named definitions)
4. Algebraic effects (not monads)
5. Designed for AI authorship (not human authorship)

## Addressing Criticisms

**"This is just Coq in binary"** — The type theory is similar to CIC, but representation (binary graph), identity (content-addressed), effects (algebraic), and intended authorship (AI) are fundamentally different.

**"Binary formats have been tried and failed"** — WASM succeeded. Xi targets a different niche: AI-generated, formally verified code.

**"No one will use a language they can't read"** — Correct. Humans won't write Xi. They'll specify what they want; AI generates Xi; the type checker verifies it; visualization tools make it inspectable. No one writes JPEG by hand either.

**"Lazy evaluation is slow on real hardware"** — True today. The value proposition is correctness now, speed with purpose-built hardware later.
