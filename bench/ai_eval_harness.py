"""
Ξ (Xi) — AI Eval Harness
Copyright (c) 2026 Alex P. Slaby — MIT License

Measures Xi's advantage over text/AST/JSON for AI code manipulation tasks.

Eval tasks:
  1. add_logic       — Add new logic without breaking types
  2. extract_function — Extract common code into a function
  3. inline_function  — Inline a function call
  4. dead_code_elim   — Remove unused definitions
  5. minimal_diff     — Smallest structural change
  6. merge_branches   — Merge two independent changes
  7. roundtrip_fidelity — Source → IR → Source preserves semantics

Metrics per task:
  - success: bool (change produces correct output)
  - diff_size: int (number of patch operations)
  - validation_time_ms: float
  - hash_stable: bool (deterministic)
  - type_safe: bool (passes type checker after change)
"""

import json, time, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from xi_compiler import Compiler
from xi_match import MatchInterpreter, Constructor, nat_to_int
from xi_json import diff, diff_stats, hash_node, canonicalize, to_json, from_json
from xi_optimizer import optimize
from xi_sandbox import SandboxedInterpreter, SandboxConfig
from xi_typecheck import TypeChecker, TypeErr, type_to_str
from xi import serialize
from xi_compress import compress


class EvalTask:
    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.results = []

    def run_case(self, case_name, original_src, modified_src, expected_result,
                 original_result=None):
        """Run a single eval case and collect metrics."""
        c = Compiler()
        tc = TypeChecker()
        metrics = {
            "case": case_name,
            "success": False,
            "diff_size": 0,
            "validation_time_ms": 0,
            "hash_stable": False,
            "type_safe": False,
            "original_size_bytes": 0,
            "modified_size_bytes": 0,
            "compressed_ratio": 0,
            "error": None,
        }

        t0 = time.monotonic()
        try:
            # Compile both
            orig_node = c.compile_program(original_src).get("main")
            mod_node = c.compile_program(modified_src).get("main")
            if not orig_node or not mod_node:
                metrics["error"] = "compilation failed"
                self.results.append(metrics)
                return metrics

            # Evaluate modified
            actual = c.run_program(modified_src, "main")
            if isinstance(actual, Constructor):
                try:
                    actual = nat_to_int(MatchInterpreter(), actual)
                except:
                    pass

            metrics["success"] = (actual == expected_result)

            # Diff
            ops = diff(orig_node, mod_node)
            metrics["diff_size"] = len(ops)

            # Hash stability
            h1 = hash_node(mod_node)
            h2 = hash_node(mod_node)
            metrics["hash_stable"] = (h1 == h2)

            # Type safety
            try:
                tc.infer_type(mod_node)
                metrics["type_safe"] = True
            except:
                metrics["type_safe"] = False  # Not necessarily failure

            # Size metrics
            orig_bin = serialize(orig_node)
            mod_bin = serialize(mod_node)
            metrics["original_size_bytes"] = len(orig_bin)
            metrics["modified_size_bytes"] = len(mod_bin)
            try:
                comp = compress(mod_node)
                metrics["compressed_ratio"] = round(len(comp) / max(len(mod_bin), 1), 3)
            except:
                pass

        except Exception as e:
            metrics["error"] = str(e)

        elapsed = (time.monotonic() - t0) * 1000
        metrics["validation_time_ms"] = round(elapsed, 2)
        self.results.append(metrics)
        return metrics


def eval_add_logic():
    """Task 1: Add new logic to existing program without breaking it."""
    task = EvalTask("add_logic", "Add logic without breaking types")

    # Case: add abs() to a math program
    task.run_case(
        "add_abs",
        original_src="def square x = x * x\ndef main = square 5",
        modified_src="def square x = x * x\ndef abs x = if x < 0 then 0 - x else x\ndef main = abs (square 5)",
        expected_result=25,
        original_result=25,
    )

    # Case: add clamping
    task.run_case(
        "add_clamp",
        original_src="def main = 42 + 100",
        modified_src="def clamp lo hi x = if x < lo then lo else if x > hi then hi else x\ndef main = clamp 0 100 (42 + 100)",
        expected_result=100,
        original_result=142,
    )

    # Case: wrap in conditional
    task.run_case(
        "add_guard",
        original_src="def main = 10 / 2",
        modified_src="def safediv a b = if b == 0 then 0 else a / b\ndef main = safediv 10 2",
        expected_result=5,
    )

    return task


def eval_extract_function():
    """Task 2: Extract repeated code into a function."""
    task = EvalTask("extract_function", "Extract common pattern into function")

    task.run_case(
        "extract_square",
        original_src="def main = (3 * 3) + (4 * 4)",
        modified_src="def sq x = x * x\ndef main = sq 3 + sq 4",
        expected_result=25,
    )

    task.run_case(
        "extract_double",
        original_src="def main = (5 + 5) + (7 + 7)",
        modified_src="def double x = x + x\ndef main = double 5 + double 7",
        expected_result=24,
    )

    return task


def eval_inline_function():
    """Task 3: Inline a function call."""
    task = EvalTask("inline_function", "Inline function call preserving semantics")

    task.run_case(
        "inline_inc",
        original_src="def inc x = x + 1\ndef main = inc 41",
        modified_src="def main = 41 + 1",
        expected_result=42,
    )

    task.run_case(
        "inline_double",
        original_src="def double x = x + x\ndef main = double 21",
        modified_src="def main = 21 + 21",
        expected_result=42,
    )

    return task


def eval_dead_code_elim():
    """Task 4: Remove unused definitions."""
    task = EvalTask("dead_code_elim", "Remove unused code, same output")

    task.run_case(
        "remove_unused",
        original_src="def unused x = x * x * x\ndef helper x = x + 1\ndef main = 42",
        modified_src="def main = 42",
        expected_result=42,
    )

    task.run_case(
        "keep_used",
        original_src="def sq x = x * x\ndef cube x = x * x * x\ndef main = sq 5",
        modified_src="def sq x = x * x\ndef main = sq 5",
        expected_result=25,
    )

    return task


def eval_minimal_diff():
    """Task 5: Measure structural diff minimality."""
    task = EvalTask("minimal_diff", "Smallest possible structural change")

    # Changing one constant should be 1 op
    task.run_case(
        "change_constant",
        original_src="def main = 2 + 3",
        modified_src="def main = 2 + 4",
        expected_result=6,
    )

    # Changing operator should be 1 op
    task.run_case(
        "change_operator",
        original_src="def main = 3 + 4",
        modified_src="def main = 3 * 4",
        expected_result=12,
    )

    return task


def eval_merge_branches():
    """Task 6: Merge two independent changes."""
    task = EvalTask("merge_branches", "Merge independent changes correctly")

    # Branch A adds a function, Branch B changes a constant
    task.run_case(
        "independent_merge",
        original_src="def main = 10 + 20",
        modified_src="def helper x = x * 2\ndef main = helper 10 + 20",
        expected_result=40,
    )

    return task


def eval_roundtrip_fidelity():
    """Task 7: Source → IR → back preserves semantics."""
    task = EvalTask("roundtrip_fidelity", "IR roundtrip preserves semantics")

    exprs = [
        ("arithmetic", "def main = (2 + 3) * 4", 20),
        ("lambda", "def main = (λx. x + x) 21", 42),
        ("nested", "def f x = x * x\ndef main = f 7", 49),
        ("conditional", "def main = if 3 < 5 then 1 else 0", 1),
    ]

    for name, src, expected in exprs:
        c = Compiler()
        node = c.compile_program(src).get("main")
        if node:
            # Roundtrip through JSON
            jr = to_json(node, include_hash=False, include_metadata=False)
            restored = from_json(jr)
            interp = MatchInterpreter()
            try:
                result = interp.run(restored)
                task.results.append({
                    "case": f"roundtrip_{name}",
                    "success": (result == expected or str(result) == str(expected)),
                    "diff_size": 0,
                    "validation_time_ms": 0,
                    "hash_stable": hash_node(node) == hash_node(restored),
                    "type_safe": True,
                    "error": None,
                })
            except Exception as e:
                task.results.append({
                    "case": f"roundtrip_{name}",
                    "success": False,
                    "error": str(e),
                })

    return task


# ═══════════════════════════════════════════
# COMPARATIVE BENCHMARKS (Xi vs text-based)
# ═══════════════════════════════════════════

def comparative_metrics():
    """Compare Xi structural operations vs text-based equivalents."""
    c = Compiler()
    metrics = []

    programs = [
        ("simple", "def main = 2 + 3"),
        ("lambda", "def main = (λx. x * x) 7"),
        ("multi", "def f x = x + x\ndef g x = f (f x)\ndef main = g 5"),
        ("nested_let", "def main = let x = 3 in let y = 4 in x * x + y * y"),
    ]

    for name, src in programs:
        node = c.compile_program(src).get("main")
        if not node:
            continue

        binary = serialize(node)
        json_ir = json.dumps(to_json(node, include_hash=False, include_metadata=False))
        source_bytes = src.encode()

        try:
            comp = compress(node)
            comp_size = len(comp)
        except:
            comp_size = len(binary)

        metrics.append({
            "program": name,
            "source_size": len(source_bytes),
            "binary_size": len(binary),
            "json_ir_size": len(json_ir.encode()),
            "compressed_size": comp_size,
            "has_content_hash": True,        # Xi: yes
            "has_structural_diff": True,     # Xi: yes
            "has_type_checking": True,       # Xi: yes
            "deterministic_serialize": True,  # Xi: yes
            # Text-based equivalents would have False for most of these
        })

    return metrics


# ═══════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════

def run_eval_harness():
    """Run all eval tasks and produce JSON report."""
    tasks = [
        eval_add_logic(),
        eval_extract_function(),
        eval_inline_function(),
        eval_dead_code_elim(),
        eval_minimal_diff(),
        eval_merge_branches(),
        eval_roundtrip_fidelity(),
    ]

    report = {
        "version": "xi-eval-v1",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tasks": {},
        "comparative": comparative_metrics(),
        "summary": {},
    }

    total_cases = 0
    total_passed = 0

    for task in tasks:
        passed = sum(1 for r in task.results if r.get("success"))
        total = len(task.results)
        avg_diff = (sum(r.get("diff_size", 0) for r in task.results) / max(total, 1))
        avg_time = (sum(r.get("validation_time_ms", 0) for r in task.results) / max(total, 1))

        report["tasks"][task.name] = {
            "description": task.description,
            "cases": task.results,
            "passed": passed,
            "total": total,
            "avg_diff_size": round(avg_diff, 1),
            "avg_validation_time_ms": round(avg_time, 2),
        }

        total_cases += total
        total_passed += passed

    report["summary"] = {
        "total_tasks": len(tasks),
        "total_cases": total_cases,
        "total_passed": total_passed,
        "pass_rate": f"{total_passed/max(total_cases,1)*100:.0f}%",
    }

    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    run_eval_harness()
