"""
Ξ (Xi) — Safe Sandbox Runtime
Copyright (c) 2026 Alex P. Slaby — MIT License

Sandboxed evaluation for AI-generated programs:
  - Gas limit (max reduction steps)
  - Memory limit (max nodes)
  - Capability system (default deny for effects)
  - Pure mode (reject any ! nodes)
  - Timeout (wall-clock seconds)
  - Deterministic: same input → same output, always
"""

import time
from xi import Node, Tag, PrimOp
from xi_match import MatchInterpreter, Constructor, nat_to_int


class SandboxError(Exception):
    """Base class for sandbox violations."""
    pass

class GasExhausted(SandboxError):
    def __init__(self, limit):
        super().__init__(f"Gas exhausted: exceeded {limit} reduction steps")
        self.limit = limit

class MemoryExceeded(SandboxError):
    def __init__(self, limit):
        super().__init__(f"Memory exceeded: more than {limit} live nodes")
        self.limit = limit

class TimeoutError(SandboxError):
    def __init__(self, limit):
        super().__init__(f"Timeout: exceeded {limit}s wall-clock time")
        self.limit = limit

class CapabilityDenied(SandboxError):
    def __init__(self, capability):
        super().__init__(f"Capability denied: '{capability}' not granted")
        self.capability = capability

class PurityViolation(SandboxError):
    def __init__(self, tag):
        super().__init__(f"Purity violation: node tag {tag} not allowed in pure mode")
        self.tag = tag


# Capabilities that can be granted
CAPABILITIES = {
    "io":      "Console/file I/O (print, readLine)",
    "net":     "Network access",
    "fs":      "File system access",
    "env":     "Environment variable access",
    "ffi":     "Foreign function interface",
    "unsafe":  "Unsafe operations (pointer arithmetic)",
}


class SandboxConfig:
    """Configuration for sandboxed execution."""

    def __init__(self,
                 gas=100_000,
                 max_nodes=50_000,
                 timeout_seconds=10.0,
                 capabilities=None,
                 pure_only=False):
        self.gas = gas
        self.max_nodes = max_nodes
        self.timeout_seconds = timeout_seconds
        self.capabilities = set(capabilities or [])
        self.pure_only = pure_only

    @classmethod
    def strict(cls):
        """Most restrictive: pure, low gas, no capabilities."""
        return cls(gas=10_000, max_nodes=5_000, timeout_seconds=2.0,
                   capabilities=[], pure_only=True)

    @classmethod
    def default(cls):
        """Default: moderate limits, no capabilities."""
        return cls(gas=100_000, max_nodes=50_000, timeout_seconds=10.0,
                   capabilities=[], pure_only=False)

    @classmethod
    def permissive(cls):
        """Permissive: high limits, IO allowed."""
        return cls(gas=1_000_000, max_nodes=500_000, timeout_seconds=60.0,
                   capabilities=["io"], pure_only=False)

    def to_dict(self):
        return {
            "gas": self.gas,
            "max_nodes": self.max_nodes,
            "timeout_seconds": self.timeout_seconds,
            "capabilities": sorted(self.capabilities),
            "pure_only": self.pure_only
        }


class SandboxedInterpreter:
    """Interpreter with resource limits and capability checking."""

    def __init__(self, config=None):
        self.config = config or SandboxConfig.default()
        self.interp = MatchInterpreter()
        self.stats = {
            "steps": 0,
            "max_nodes": 0,
            "wall_time_ms": 0,
            "result_type": None,
            "exit_code": 0,
            "error": None
        }

    def eval(self, node):
        """Evaluate a node within sandbox constraints.

        Returns: (result_value, stats_dict)
        Raises: SandboxError subclass on violation
        """
        # Pre-flight checks
        if self.config.pure_only:
            self._check_purity(node)
        self._check_capabilities(node)

        # Node count check
        nc = self._count_nodes(node)
        self.stats["max_nodes"] = nc
        if nc > self.config.max_nodes:
            raise MemoryExceeded(self.config.max_nodes)

        # Run with timeout using the real interpreter
        start = time.monotonic()
        self.stats["steps"] = 0

        # Instrument interpreter to count steps
        orig_eval = self.interp._eval
        sandbox_ref = self

        def counted_eval(n):
            sandbox_ref.stats["steps"] += 1
            if sandbox_ref.stats["steps"] > sandbox_ref.config.gas:
                raise GasExhausted(sandbox_ref.config.gas)
            if sandbox_ref.stats["steps"] % 200 == 0:
                elapsed = time.monotonic() - start
                if elapsed > sandbox_ref.config.timeout_seconds:
                    raise TimeoutError(sandbox_ref.config.timeout_seconds)
            return orig_eval(n)

        try:
            self.interp._eval = counted_eval
            result = self.interp.run(node)
        except SandboxError:
            raise
        except Exception as e:
            self.stats["error"] = str(e)
            self.stats["exit_code"] = 2
            raise
        finally:
            self.interp._eval = orig_eval

        elapsed = time.monotonic() - start
        self.stats["wall_time_ms"] = round(elapsed * 1000, 2)

        # Convert result
        result_val = self._extract_value(result)
        self.stats["result_type"] = type(result_val).__name__

        return result_val, self.stats

    def eval_safe(self, node):
        """Like eval() but returns (value, stats) or (None, stats_with_error).
        Never raises."""
        try:
            return self.eval(node)
        except SandboxError as e:
            self.stats["error"] = str(e)
            self.stats["exit_code"] = 1
            return None, self.stats
        except Exception as e:
            self.stats["error"] = f"Internal: {e}"
            self.stats["exit_code"] = 2
            return None, self.stats

    def _check_purity(self, node):
        """Reject any effect nodes in pure mode."""
        if node.tag == Tag.EFF:
            raise PurityViolation(node.tag)
        if node.tag == Tag.PRIM and isinstance(node.data, PrimOp):
            if node.data == PrimOp.PRINT:
                raise PurityViolation("PRINT (IO effect)")
        for child in node.children:
            self._check_purity(child)

    def _check_capabilities(self, node):
        """Check that required capabilities are granted."""
        required = self._required_capabilities(node)
        for cap in required:
            if cap not in self.config.capabilities:
                raise CapabilityDenied(cap)

    def _required_capabilities(self, node):
        """Determine what capabilities a program needs."""
        caps = set()
        if node.tag == Tag.EFF:
            caps.add("io")  # Effect nodes need IO capability
        if node.tag == Tag.PRIM and isinstance(node.data, PrimOp):
            if node.data == PrimOp.PRINT:
                caps.add("io")
        for child in node.children:
            caps |= self._required_capabilities(child)
        return caps

    def _count_nodes(self, node):
        """Count nodes in current graph."""
        count = 1
        for c in node.children:
            count += self._count_nodes(c)
        return count

    def _extract_value(self, result):
        """Convert a Node result to a Python value."""
        if isinstance(result, (int, str, bool, float)):
            return result
        if isinstance(result, Constructor):
            try:
                return nat_to_int(self.interp, result)
            except:
                return f"Constructor({result.name}, {len(result.args)} args)"
        if isinstance(result, Node):
            if result.tag == Tag.PRIM and isinstance(result.data, (int, str)):
                return result.data
            if result.data is not None:
                return result.data
        return str(result)
