# ERRORS — Xi Error Catalog

Every Xi error has a code, message, cause, and fix. Use this to self-correct.

## Exit Codes

| Code | Category | Meaning |
|------|----------|---------|
| 0 | OK | Success |
| 1 | INPUT | Parse, decode, or validation error |
| 2 | RUNTIME | Gas exhausted, timeout, capability denied |
| 3 | TYPE | Type mismatch, unification failure |
| 4 | IO | File not found, read/write failure |
| 5 | INTERNAL | Bug in Xi itself |

## Parse Errors (Exit 1)

### E100: Unexpected token
```
1:5: Unexpected token '+'
```
**Cause:** Syntax error — the parser didn't expect this token here.
**Fix:** Check expression syntax. Common issues:
- Missing parentheses around complex expressions
- Missing `in` after `let x = expr`
- Missing `→` in match branches

### E101: Undefined variable
```
1:8: Undefined variable 'x'
```
**Cause:** Used a name that hasn't been `def`'d or bound by `λ`.
**Fix:** Add `def x = ...` or wrap in `λx. ...`

### E102: Unknown constructor
```
2:5: Unknown constructor 'Foo'
```
**Cause:** Constructor not defined by any `type` declaration.
**Fix:** Add `type T = Foo | Bar` before using `Foo`.

### E103: Unterminated string
```
1:12: Unterminated string literal
```
**Cause:** Missing closing `"`.
**Fix:** Ensure strings have matching quotes.

### E104: Expected declaration
```
4:1: Expected declaration (def/type/import), got IDENT
```
**Cause:** Top-level code must be `def`, `type`, or `import`.
**Fix:** Wrap expression in `def main = <expr>`.

### E105: Entry point not found
```
No 'main'. Available: ['square', 'double']
```
**Cause:** Program has no `def main`.
**Fix:** Add `def main = ...` or use `--entry <name>`.

## Runtime Errors (Exit 2)

### E200: Gas exhausted
```json
{"error": "Gas exhausted: exceeded 100000 reduction steps"}
```
**Cause:** Program takes too many steps (likely infinite loop).
**Fix:** Increase `--gas N` or simplify the program. Check for non-terminating recursion.

### E201: Memory exceeded
```json
{"error": "Memory exceeded: more than 50000 live nodes"}
```
**Cause:** Too many nodes allocated (growing data structure).
**Fix:** Increase `--max-nodes N` or add garbage collection points.

### E202: Timeout
```json
{"error": "Timeout: exceeded 10s wall-clock time"}
```
**Cause:** Evaluation too slow.
**Fix:** Increase `--timeout N` or optimize the program.

### E203: Capability denied
```json
{"error": "Capability denied: 'io' not granted"}
```
**Cause:** Program uses effects (e.g., `print`) but sandbox doesn't allow them.
**Fix:** Add `--cap io` to grant IO capability, or remove the effect from the program.

### E204: Purity violation
```json
{"error": "Purity violation: PRINT (IO effect) not allowed in pure mode"}
```
**Cause:** Used `--pure` but program has effect nodes.
**Fix:** Remove `--pure` flag or eliminate all effects from the program.

## Type Errors (Exit 3)

### E300: Type mismatch
```
TypeError: Cannot unify Int with String
```
**Cause:** Expression produces wrong type.
**Fix:** Check that operators match their expected types. `+` expects Int, `++` expects String.

### E301: Occurs check failure
```
TypeError: Occurs check: α appears in α → Int
```
**Cause:** Infinite type detected (e.g., `λx. x x`).
**Fix:** Add type annotations or restructure to avoid self-application.

### E302: Unification failure
```
TypeError: Cannot unify Bool with Int → Int
```
**Cause:** Using a value where a function is expected, or vice versa.
**Fix:** Check arity — are you passing enough arguments?

## Decode Errors (Exit 1)

### E400: Invalid magic
```
Decode failed: invalid magic header
```
**Cause:** File is not a valid `.xi` or `.xic` binary.
**Fix:** Ensure the file was produced by `xi encode` or `xi build`.

### E401: Truncated data
```
Decode failed: unexpected end of input
```
**Cause:** Binary file is incomplete.
**Fix:** Re-encode from source.

### E402: Unknown tag
```
Decode failed: unknown tag value 15
```
**Cause:** Binary contains a tag outside the 0–9 range.
**Fix:** Re-encode from source. File may be corrupted.

## JSON-IR Validation Errors

### E500: Missing version
```
Expected version 'xi-ir-v1', got 'null'
```
**Fix:** Add `"version": "xi-ir-v1"` to top level.

### E501: Missing root
```
Missing 'root' field
```
**Fix:** Add `"root": { <NODE> }` to top level.

### E502: Unknown tag in node
```
root.children[0]: unknown tag 'lambda'
```
**Fix:** Use lowercase tag names: `lam`, not `lambda`.

### E503: Invalid prim_op
```
Unknown prim_op: 'addition'
```
**Fix:** Use exact prim_op names: `int_add`, not `addition`. See PROMPT_SPEC.md table.

## Self-Correction Protocol

When you get an error:

1. **Read the error code** (E100–E503)
2. **Find it in this file**
3. **Apply the fix**
4. **Re-run the command**
5. **If still failing:** simplify the program to the minimal failing case, then fix

### Example Recovery Loop

```
xi eval -e "let x = 3 x + x"
→ E100: Unexpected token 'x' at 1:19

# Fix: missing 'in'
xi eval -e "let x = 3 in x + x"
→ {"ok": true, "result": 6}
```

```
xi eval --pure -e "print 42"
→ E204: Purity violation

# Fix: remove --pure
xi eval -e "print 42" --cap io
→ {"ok": true, "result": 42}
```
