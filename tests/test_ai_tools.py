"""
Tests for Xi AI-first tooling: JSON-IR, Sandbox, Eval Harness
"""
import pytest, json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from xi import Node, Tag, PrimOp, serialize
from xi_compiler import Compiler
from xi_json import (to_json, from_json, to_json_str, canonicalize, hash_node,
                     diff, patch, diff_stats, validate_json, analyze_properties,
                     node_count, max_depth, XI_IR_SCHEMA)
from xi_sandbox import (SandboxedInterpreter, SandboxConfig,
                        GasExhausted, CapabilityDenied, PurityViolation)


# ═══════════════════════════════════════════
# JSON-IR
# ═══════════════════════════════════════════

class TestJsonIR:
    def _compile(self, expr):
        c = Compiler()
        return c.compile_program(f"def main = {expr}").get("main")

    def test_to_json_basic(self):
        node = self._compile("2 + 3")
        j = to_json(node)
        assert j["version"] == "xi-ir-v1"
        assert "root" in j
        assert "metadata" in j
        assert isinstance(j["metadata"]["hash"], str)
        assert len(j["metadata"]["hash"]) == 64

    def test_json_roundtrip(self):
        node = self._compile("(λx. x + 1) 41")
        j = to_json(node)
        node2 = from_json(j)
        assert hash_node(node) == hash_node(node2)

    def test_json_string_roundtrip(self):
        node = self._compile("2 + 3")
        s = to_json_str(node)
        parsed = json.loads(s)
        assert parsed["version"] == "xi-ir-v1"

    def test_validate_valid(self):
        node = self._compile("42")
        j = to_json(node)
        errors = validate_json(j)
        assert errors == []

    def test_validate_bad_version(self):
        errors = validate_json({"version": "wrong", "root": {"tag": "prim"}})
        assert len(errors) > 0

    def test_validate_missing_root(self):
        errors = validate_json({"version": "xi-ir-v1"})
        assert any("root" in e for e in errors)

    def test_hash_determinism(self):
        node = self._compile("(λx. x * x) 7")
        h1 = hash_node(node)
        h2 = hash_node(node)
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_different_programs(self):
        a = self._compile("2 + 3")
        b = self._compile("2 * 3")
        assert hash_node(a) != hash_node(b)

    def test_canonicalize_idempotent(self):
        node = self._compile("(λx. x + x) 5")
        c1 = canonicalize(node)
        c2 = canonicalize(c1)
        assert hash_node(c1) == hash_node(c2)

    def test_node_count(self):
        node = self._compile("42")
        assert node_count(node) >= 1

    def test_max_depth(self):
        node = self._compile("42")
        assert max_depth(node) >= 0

    def test_analyze_properties_pure(self):
        node = self._compile("2 + 3")
        props = analyze_properties(node)
        assert "pure" in props["properties"]

    def test_schema_valid(self):
        assert XI_IR_SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert XI_IR_SCHEMA["title"] == "Xi-IR v1"


# ═══════════════════════════════════════════
# STRUCTURAL DIFF
# ═══════════════════════════════════════════

class TestDiff:
    def _compile(self, expr):
        c = Compiler()
        return c.compile_program(f"def main = {expr}").get("main")

    def test_identical_no_ops(self):
        a = self._compile("2 + 3")
        b = self._compile("2 + 3")
        ops = diff(a, b)
        assert len(ops) == 0

    def test_different_constant(self):
        a = self._compile("2 + 3")
        b = self._compile("2 + 7")
        ops = diff(a, b)
        assert len(ops) >= 1

    def test_different_operator(self):
        a = self._compile("5 + 3")
        b = self._compile("5 * 3")
        ops = diff(a, b)
        assert len(ops) >= 1
        # Should detect prim_op change
        assert any(o["op"] == "modify_data" for o in ops)

    def test_diff_stats(self):
        a = self._compile("2 + 3")
        b = self._compile("2 * 7")
        ops = diff(a, b)
        stats = diff_stats(ops)
        assert "total_ops" in stats
        assert stats["total_ops"] == len(ops)


# ═══════════════════════════════════════════
# SANDBOX
# ═══════════════════════════════════════════

class TestSandbox:
    def _compile(self, source):
        c = Compiler()
        return c.compile_program(source).get("main")

    def test_basic_eval(self):
        node = self._compile("def main = 2 + 3")
        sandbox = SandboxedInterpreter(SandboxConfig.default())
        result, stats = sandbox.eval_safe(node)
        assert result == 5
        assert stats["exit_code"] == 0

    def test_lambda_eval(self):
        node = self._compile("def main = (λx. x * x) 7")
        sandbox = SandboxedInterpreter(SandboxConfig.default())
        result, stats = sandbox.eval_safe(node)
        assert result == 49

    def test_gas_limit(self):
        node = self._compile("def main = fix f. f")
        config = SandboxConfig(gas=50, timeout_seconds=2.0)
        sandbox = SandboxedInterpreter(config)
        result, stats = sandbox.eval_safe(node)
        assert stats["exit_code"] != 0
        assert "Gas exhausted" in stats["error"]

    def test_strict_config(self):
        config = SandboxConfig.strict()
        assert config.gas == 10_000
        assert config.pure_only is True
        assert len(config.capabilities) == 0

    def test_config_to_dict(self):
        config = SandboxConfig.default()
        d = config.to_dict()
        assert "gas" in d
        assert "pure_only" in d
        assert "capabilities" in d

    def test_permissive_config(self):
        config = SandboxConfig.permissive()
        assert config.gas == 1_000_000
        assert "io" in config.capabilities


# ═══════════════════════════════════════════
# EVAL HARNESS (smoke test)
# ═══════════════════════════════════════════

class TestEvalHarness:
    def test_harness_runs(self):
        from xi_eval_harness import run_eval_harness
        report = run_eval_harness(verbose=False)
        assert report["ok"] is True
        assert report["summary"]["total_tasks"] >= 10
        assert report["summary"]["passed"] >= 10

    def test_harness_categories(self):
        from xi_eval_harness import run_eval_harness
        report = run_eval_harness()
        cats = report["by_category"]
        assert "add_logic" in cats
        assert "refactor" in cats
        assert "merge" in cats
        assert "minimal_diff" in cats
        assert "proof_check" in cats


# ═══════════════════════════════════════════
# CLI (smoke tests)
# ═══════════════════════════════════════════

class TestCLI:
    def _run_cli(self, args):
        import subprocess
        cli = os.path.join(os.path.dirname(__file__), '..', 'xi')
        result = subprocess.run(
            ['python3', cli] + args,
            capture_output=True, text=True, timeout=10
        )
        return result

    def test_cli_encode(self):
        r = self._run_cli(["encode", "-e", "2 + 3"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["ok"] is True
        assert data["format"] == "xi-binary"

    def test_cli_encode_json(self):
        r = self._run_cli(["encode", "--json", "-e", "2 + 3"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["ok"] is True
        assert data["format"] == "xi-ir-v1"

    def test_cli_eval(self):
        r = self._run_cli(["eval", "-e", "(λx. x * x) 7"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["ok"] is True
        assert data["result"] == 49

    def test_cli_eval_pure(self):
        r = self._run_cli(["eval", "--pure", "-e", "2 + 3"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["ok"] is True

    def test_cli_eval_gas_exhausted(self):
        r = self._run_cli(["eval", "--gas", "50", "-e", "fix f. f"])
        data = json.loads(r.stdout)
        assert data["ok"] is False
        assert "Gas exhausted" in data["stats"]["error"]

    def test_cli_hash(self):
        r = self._run_cli(["hash", "-e", "2 + 3"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["ok"] is True
        assert len(data["hash"]) == 64

    def test_cli_hash_deterministic(self):
        r1 = self._run_cli(["hash", "-e", "42"])
        r2 = self._run_cli(["hash", "-e", "42"])
        d1 = json.loads(r1.stdout)
        d2 = json.loads(r2.stdout)
        assert d1["hash"] == d2["hash"]

    def test_cli_schema(self):
        r = self._run_cli(["schema"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["title"] == "Xi-IR v1"

    def test_cli_check(self):
        r = self._run_cli(["check", "-e", "2 + 3"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["ok"] is True
        assert "types" in data

    def test_cli_normalize(self):
        r = self._run_cli(["normalize", "-e", "2 + 3"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["ok"] is True
        assert "hash" in data

    def test_cli_unknown_command(self):
        r = self._run_cli(["nonexistent"])
        assert r.returncode == 1  # EXIT_INPUT
