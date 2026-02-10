# Xi Examples

Run all examples:
```bash
python src/xi.py demo
```

## Example 1: Hello World
```
!{IO}
└─ @
   ├─ # [print]
   └─ # [str: "Hello, World!"]
```
Type: `!{IO} Unit` — Prints a string with IO effect.

## Example 2: Arithmetic — (3 + 5) × 2
```
!{IO}
└─ @
   ├─ # [print]
   └─ @
      ├─ @
      │  ├─ # [mul]
      │  └─ @
      │     ├─ @
      │     │  ├─ # [add]
      │     │  └─ # [int: 3]
      │     └─ # [int: 5]
      └─ # [int: 2]
```
Type: `!{IO} Unit` — Computes (3+5)×2 = 16.

## Example 3: String Concatenation
```
!{IO}
└─ @
   ├─ # [print]
   └─ @
      ├─ @
      │  ├─ # [str_concat]
      │  └─ # [str: "Hello, "]
      └─ # [str: "Xi!"]
```
Type: `!{IO} Unit` — Concatenates two strings.

## Example 4: Lambda — Double Function
```
λ
├─ 𝒰₀
└─ @
   ├─ @
   │  ├─ # [add]
   │  └─ var(0)
   └─ var(0)
```
Type: `Nat → Nat` — A function that doubles its argument.
