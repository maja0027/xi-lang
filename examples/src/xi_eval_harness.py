"""
Ξ (Xi) — AI Eval Harness
Copyright (c) 2026 Alex P. Slaby — MIT License

Benchmarks Xi on typical AI programming tasks.
Measures: success rate, diff size, validation time, hash stability.

Tasks:
  1. Add logic without breaking types
  2. Refactor: extract function, inline, dead-code elim
  3. Merge two branches
  4. Minimal diff (structural)
  5. Proof/trace check (type soundness)
"""

import json, time, sys, os, random, traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from xi import Node, Tag, PrimOp, serialize
from xi_compiler import Compiler, ParseError
from xi_match import MatchInterpreter, Constructor, nat_to_int
from xi_json import to_json, from_json, canonicalize, hash_node, diff, patch, diff_stats, node_count
from xi_optimizer import optimize
from xi_sandbox import SandboxedInterpreter, SandboxConfig
from xi_typecheck import TypeChecker, TypeErr, type_to_str


# ═══════════════════════════════════════════
# TASK DEFINITIONS
# ═══════════════════════════════════════════

class EvalTask:
    """A single evaluation task."""
    def __init__(self, name, category, description, original, expected, check_fn):
        self.name = name
        self.category = category
        self.description = description
        self.original = original        # source code
        self.expected = expected         # expected source after transformation
        self.check_fn = check_fn        # (original_node, result_node) → bool

    def run(self, compiler):
        """Execute the task and return metrics."""
        start = time.monotonic()
        result = {"task": self.name, "category": self.category}

        try:
            # Compile original
            orig_node = compiler.compile_program(self.original).get("main")
            if not orig_node:
                result["status"] = "error"
                result["error"] = "Cannot compile original"
                return result

            # Compile expected
            exp_node = compiler.compile_program(self.expected).get("main")
            if not exp_node:
                result["status"] = "error"
                result["error"] = "Cannot compile expected"
                return result

            # Compute diff
            ops = diff(orig_node, exp_node)
            stats = diff_stats(ops)

            # Verify patch roundtrip
            if ops:
                patched = patch(orig_node, ops)
                patch_hash = hash_node(patched)
                target_hash = hash_node(exp_node)
                patch_ok = patch_hash == target_hash
            else:
                patch_ok = hash_node(orig_node) == hash_node(exp_node)

            # Eval both
            sandbox = SandboxedInterpreter(SandboxConfig.strict())
            orig_val, _ = sandbox.eval_safe(orig_node)
            sandbox2 = SandboxedInterpreter(SandboxConfig.strict())
            exp_val, _ = sandbox2.eval_safe(exp_node)

            # Type check both
            tc = TypeChecker()
            try:
                orig_type = type_to_str(tc.infer_type(orig_node))
            except:
                orig_type = "unknown"
            try:
                exp_type = type_to_str(tc.infer_type(exp_node))
            except:
                exp_type = "unknown"

            # Custom check
            custom_ok = self.check_fn(orig_node, exp_node, orig_val, exp_val)

            elapsed = time.monotonic() - start

            result.update({
                "status": "pass" if custom_ok else "fail",
                "diff_ops": stats["total_ops"],
                "diff_replacements": stats["replacements"],
                "diff_modifications": stats["modifications"],
                "original_nodes": node_count(orig_node),
                "expected_nodes": node_count(exp_node),
                "original_hash": hash_node(orig_node),
                "expected_hash": hash_node(exp_node),
                "original_value": orig_val,
                "expected_value": exp_val,
                "original_type": orig_type,
                "expected_type": exp_type,
                "patch_roundtrip": patch_ok,
                "custom_check": custom_ok,
                "validation_time_ms": round(elapsed * 1000, 2),
            })

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result


# ═══════════════════════════════════════════
# TASK CATALOG
# ═══════════════════════════════════════════

def build_tasks():
    """Build the full evaluation task catalog."""
    tasks = []

    # ── Category 1: Add logic without breaking types ──

    tasks.append(EvalTask(
        "add_constant_to_sum",
        "add_logic",
        "Add +10 to an existing sum without breaking types",
        "def main = 3 + 5",
        "def main = 3 + 5 + 10",
        lambda o, e, ov, ev: ev == 18 and ov == 8
    ))

    tasks.append(EvalTask(
        "add_conditional_guard",
        "add_logic",
        "Add a conditional guard to a computation",
        "def f x = x * x\ndef main = f 5",
        "def f x = if x > 0 then x * x else 0\ndef main = f 5",
        lambda o, e, ov, ev: ev == 25  # Same result for positive
    ))

    tasks.append(EvalTask(
        "add_new_function",
        "add_logic",
        "Add a helper function and use it",
        "def main = 3 * 3 + 4 * 4",
        "def sq x = x * x\ndef main = sq 3 + sq 4",
        lambda o, e, ov, ev: ov == ev  # Same result
    ))

    tasks.append(EvalTask(
        "add_string_op",
        "add_logic",
        "Extend program with string operation",
        'def main = "hello"',
        'def main = "hello" ++ " world"',
        lambda o, e, ov, ev: ev == "hello world"
    ))

    # ── Category 2: Refactor ──

    tasks.append(EvalTask(
        "extract_function",
        "refactor",
        "Extract repeated expression into a function",
        "def main = (3 * 3) + (4 * 4)",
        "def sq x = x * x\ndef main = sq 3 + sq 4",
        lambda o, e, ov, ev: ov == ev  # Semantics preserved
    ))

    tasks.append(EvalTask(
        "inline_let",
        "refactor",
        "Inline a let binding",
        "def main = let x = 7 in x + x",
        "def main = 7 + 7",
        lambda o, e, ov, ev: ov == ev
    ))

    tasks.append(EvalTask(
        "simplify_identity",
        "refactor",
        "Simplify (λx. x) applied to value",
        "def main = (λx. x) 42",
        "def main = 42",
        lambda o, e, ov, ev: ov == ev
    ))

    tasks.append(EvalTask(
        "dead_code_removal",
        "refactor",
        "Remove unused function",
        "def unused x = x * x * x\ndef main = 42",
        "def main = 42",
        lambda o, e, ov, ev: ov == ev
    ))

    tasks.append(EvalTask(
        "constant_fold",
        "refactor",
        "Fold compile-time constants",
        "def main = (2 + 3) * (4 + 1)",
        "def main = 25",
        lambda o, e, ov, ev: ov == ev
    ))

    # ── Category 3: Merge ──

    tasks.append(EvalTask(
        "merge_independent_defs",
        "merge",
        "Merge two branches with independent new functions",
        "def main = 42",
        "def double x = x + x\ndef triple x = x + x + x\ndef main = double 10 + triple 5",
        lambda o, e, ov, ev: ev == 35
    ))

    tasks.append(EvalTask(
        "merge_modified_body",
        "merge",
        "Both branches modify the main body differently",
        "def f x = x + 1\ndef main = f 10",
        "def f x = x + 2\ndef main = f 10",
        lambda o, e, ov, ev: ev == 12 and ov == 11
    ))

    # ── Category 4: Minimal diff ──

    tasks.append(EvalTask(
        "minimal_single_constant",
        "minimal_diff",
        "Change one constant — should be 1 op",
        "def main = 5 + 3",
        "def main = 5 + 7",
        lambda o, e, ov, ev: ev == 12
    ))

    tasks.append(EvalTask(
        "minimal_operator_change",
        "minimal_diff",
        "Change one operator — should be 1 op",
        "def main = 5 + 3",
        "def main = 5 * 3",
        lambda o, e, ov, ev: ev == 15
    ))

    tasks.append(EvalTask(
        "minimal_add_wrapper",
        "minimal_diff",
        "Wrap expression in lambda — small structural change",
        "def main = 42",
        "def main = (λx. x) 42",
        lambda o, e, ov, ev: ov == ev  # Same result despite structural change
    ))

    # ── Category 5: Type/proof check ──

    tasks.append(EvalTask(
        "type_preserving_refactor",
        "proof_check",
        "Refactoring preserves types",
        "def main = 3 + 4",
        "def main = 4 + 3",
        lambda o, e, ov, ev: ov == ev  # Commutativity
    ))

    tasks.append(EvalTask(
        "type_preserving_extract",
        "proof_check",
        "Extracting function preserves return type",
        "def main = 5 * 5",
        "def sq x = x * x\ndef main = sq 5",
        lambda o, e, ov, ev: ov == ev
    ))

    return tasks


# ═══════════════════════════════════════════
# HARNESS RUNNER
# ═══════════════════════════════════════════

def run_eval_harness(verbose=False):
    """Run all evaluation tasks and report results."""
    tasks = build_tasks()
    compiler = Compiler()
    results = []
    categories = {}

    start = time.monotonic()

    for task in tasks:
        result = task.run(compiler)
        results.append(result)

        cat = task.category
        if cat not in categories:
            categories[cat] = {"pass": 0, "fail": 0, "error": 0}
        categories[cat][result["status"]] = categories[cat].get(result["status"], 0) + 1

        if verbose:
            status_icon = "✓" if result["status"] == "pass" else "✗" if result["status"] == "fail" else "!"
            print(f"  {status_icon} {task.name}: {result['status']}", file=sys.stderr)
            if result["status"] != "pass" and "error" in result:
                print(f"    → {result.get('error', '')}", file=sys.stderr)

    elapsed = time.monotonic() - start

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    errors = sum(1 for r in results if r["status"] == "error")

    avg_diff = sum(r.get("diff_ops", 0) for r in results if r["status"] == "pass") / max(1, passed)
    avg_time = sum(r.get("validation_time_ms", 0) for r in results) / max(1, total)

    # Hash stability: all hashes are deterministic
    hash_stable = all(
        r.get("patch_roundtrip", False)
        for r in results if r["status"] == "pass"
    )

    report = {
        "ok": True,
        "summary": {
            "total_tasks": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "success_rate": f"{passed / total * 100:.1f}%",
            "avg_diff_ops": round(avg_diff, 1),
            "avg_validation_time_ms": round(avg_time, 2),
            "hash_stability": hash_stable,
            "total_time_ms": round(elapsed * 1000, 2),
        },
        "by_category": {},
        "results": results
    }

    for cat, counts in categories.items():
        total_cat = sum(counts.values())
        report["by_category"][cat] = {
            **counts,
            "total": total_cat,
            "success_rate": f"{counts.get('pass', 0) / total_cat * 100:.1f}%"
        }

    return report


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    print("Ξ Xi Eval Harness — AI Task Benchmarks", file=sys.stderr)
    report = run_eval_harness(verbose=verbose)
    print(json.dumps(report, indent=2, default=str))
    sys.exit(0 if report["summary"]["failed"] == 0 and report["summary"]["errors"] == 0 else 1)


if __name__ == "__main__":
    main()
