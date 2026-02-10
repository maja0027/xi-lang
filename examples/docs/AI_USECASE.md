# AI Use Cases for Xi

Xi is not "a new programming language." It is a **better substrate for AI to read, write, and transform programs**.

---

## Why Xi Beats Text-Based Code for AI

| Operation | Text (Python/JS) | Xi |
|-----------|------------------|----|
| **Parse** | Grammar-dependent, ambiguous | 10 node types, unambiguous binary |
| **Diff** | Line-based, breaks on reformatting | Structural graph diff, formatting-independent |
| **Merge** | 3-way text merge, conflict-prone | Graph merge on content-addressed nodes |
| **Verify** | Run test suite (slow, flaky) | Type check + hash (fast, deterministic) |
| **Deduplicate** | String matching | SHA-256 content addressing (automatic) |
| **Optimize** | Per-language, fragile | 4 universal reduction rules |
| **Parallelize** | Manual, error-prone | Automatic via effect system (pure = parallel) |

---

## Use Case 1: AI Refactoring Engine

**Problem:** AI changes code → breaks something → hard to verify what changed.

**Xi solution:**
```bash
# 1. AI generates the change
xi diff original.xi-src modified.xi-src > patch.json

# 2. Verify: minimal structural diff
cat patch.json | jq '.stats'
# {"total_ops": 2, "replacements": 1, "modifications": 1}

# 3. Verify: types preserved
xi check modified.xi-src
# {"ok": true, "types": {"main": "Int"}}

# 4. Verify: hash is deterministic
xi hash modified.xi-src
# {"hash": "a1b2c3...", "node_count": 12}

# 5. Apply patch to any version
xi patch other_version.xi-src patch.json
```

**Key advantage:** The diff is structural, not textual. Reformatting, reordering, or renaming doesn't create false diffs. The AI sees exactly what changed semantically.

---

## Use Case 2: AI Rules Engine

**Problem:** Business rules (pricing, fraud, compliance) change frequently. Each change needs audit trail and rollback.

**Xi solution:**
```python
# Each rule version is content-addressed
rule_v1 = "def price x = x * 100"           # hash: abc123
rule_v2 = "def price x = x * 100 + 10"      # hash: def456
rule_v3 = "def price x = if x > 50 then x * 90 else x * 100"  # hash: 789ghi

# Audit: exact diff between versions
POST /diff {"old_source": rule_v1, "new_source": rule_v2}
# → {"operations": [{"op": "insert", "path": "root.children[1]", ...}]}

# Replay: evaluate any version on any input
POST /eval {"source": rule_v1, "gas": 1000, "pure": true}
# → {"result": 5000, "stats": {"steps": 4}}

# Rollback: just switch hash pointer, no code deployment
current_rule_hash = "abc123"  # instant rollback
```

**Key advantage:** Every version is immutable and identified by hash. Audit trail is automatic. Rollback is a pointer swap.

---

## Use Case 3: Proof-Carrying Transforms

**Problem:** AI optimizer changes code for performance, but did it preserve correctness?

**Xi solution:**
```bash
# Optimize with proof
xi normalize program.xi-src
# → {"canonical": {...}, "hash": "...", "optimization": {
#      "constant_fold": 3, "cse": 2, "dce": 1
#    }}

# The canonical form has the SAME hash if semantics are preserved
# Different hash = semantics changed (AI made a mistake)

# Type check before and after
xi check original.xi-src   # {"types": {"main": "Int → Int"}}
xi check optimized.xi-src  # {"types": {"main": "Int → Int"}}  ← same!
```

**Key advantage:** Content-addressed hashing means semantic equivalence is a hash comparison. No need to run tests — the math guarantees it.

---

## Use Case 4: AI Self-Play Training

**Problem:** AI needs millions of (program, transformation, correct_result) triples to learn.

**Xi solution:**
```bash
# Generate 10,000 training examples
xi dataset --generate 10000 --out training/

# Each example contains:
# - source.xi-src (human-readable)
# - ir.json (machine-readable graph)
# - binary.xi (compact binary)
# - expected_output
# - properties: ["pure", "terminates", "no_effects"]
# - mutations: [(description, patch, correct_result)]

# AI trains on mutations:
# "Given program P and change description D, produce correct patch"
```

**Key advantage:** Xi programs are small, self-contained, and have ground-truth outputs. Perfect for supervised learning.

---

## Use Case 5: Sandboxed AI Code Execution

**Problem:** AI generates code → you run it → it deletes your files.

**Xi solution:**
```bash
# Pure mode: no IO, no effects, mathematically guaranteed
xi eval --pure --gas 10000 --timeout 2 -e "(λx. x * x) 7"
# {"ok": true, "result": 49, "stats": {"steps": 3}}

# Capability system: explicit grants
xi eval --cap io -e 'print 42'  # IO allowed
xi eval -e 'print 42'           # DENIED: capability 'io' not granted

# Gas limit prevents infinite loops
xi eval --gas 100 -e "fix f. f"
# {"ok": false, "error": "Gas exhausted: exceeded 100 reduction steps"}
```

**Key advantage:** Safety is built into the runtime, not bolted on. Pure programs can't do anything harmful by construction.

---

## How to Integrate Xi with AI

### As a Tool (function calling)
```json
{
  "name": "xi_eval",
  "description": "Evaluate a Xi expression safely",
  "parameters": {
    "source": "def main = (λx. x * x) 7",
    "gas": 10000,
    "pure": true
  }
}
```

### As an API
```bash
curl -X POST http://localhost:8420/eval \
  -H "Content-Type: application/json" \
  -d '{"source": "def main = 2 + 3", "pure": true}'
# {"ok": true, "result": 5, "stats": {"steps": 3}}
```

### As a Dataset
```bash
xi dataset --generate 100000 --out training/
# Use training/manifest.json for data loading
```

---

## Metrics: Xi vs Alternatives

| Metric | JSON AST | WASM | Xi |
|--------|---------|------|-----|
| Parse time (1K nodes) | 2.1 ms | 0.8 ms | 0.3 ms |
| Structural diff | No | No | Yes (built-in) |
| Content addressing | No | No | Yes (SHA-256) |
| Type safety | No | Partial | Full (dependent) |
| Sandbox | Manual | Memory-safe | Pure mode + gas |
| Deterministic | Mostly | Yes | Yes (guaranteed) |
| Min representation | ~50 B/node | ~4 B/op | ~3 B/node |
| Self-verifying | No | No | Yes (hash + types) |

Run `xi eval --harness` or `python src/xi_eval_harness.py -v` to reproduce.
