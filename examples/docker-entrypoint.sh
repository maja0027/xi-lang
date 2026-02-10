#!/bin/bash
set -e

case "${1:-demo}" in
  demo)
    echo "═══ Xi Core ═══"
    python src/xi.py demo
    echo ""
    echo "═══ Type Checker ═══"
    python src/xi_typecheck.py demo
    echo ""
    echo "═══ Pattern Matching ═══"
    python src/xi_match.py demo
    echo ""
    echo "═══ Module System ═══"
    python src/xi_module.py demo
    echo ""
    echo "═══ Optimizer ═══"
    python src/xi_optimizer.py demo
    echo ""
    echo "═══ XiC Compression ═══"
    python src/xi_compress.py demo
    echo ""
    echo "═══ Parser ═══"
    python src/xi_compiler.py demo
    echo ""
    echo "═══ Examples ═══"
    python examples/xi_examples.py
    ;;
  test)
    python -m pytest tests/ -v
    ;;
  repl)
    python src/xi_repl.py
    ;;
  bench)
    python src/xi_multicore.py bench
    ;;
  match)
    python src/xi_match.py demo
    ;;
  module)
    python src/xi_module.py demo
    ;;
  typecheck)
    python src/xi_typecheck.py demo
    ;;
  optimize)
    python src/xi_optimizer.py demo
    ;;
  compress)
    python src/xi_compress.py demo
    ;;
  examples)
    python examples/xi_examples.py
    ;;
  compile)
    shift
    python src/xi_compiler.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
