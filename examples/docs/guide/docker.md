# Docker Guide

Run Xi in a container without installing Python or dependencies locally.

---

## 1. Building

```bash
docker build -t xi-lang .
```

The image is based on `python:3.12-slim` (~150 MB) and includes the full Xi toolchain.

## 2. Running

### REPL
```bash
docker run -it xi-lang repl
```

### Execute an Expression
```bash
docker run xi-lang run -e "(λx. x * x) 7"
# Output: 49
```

### Run a File
```bash
docker run -v $(pwd)/examples:/app/examples xi-lang run examples/demo.xi-src
```

### Type Check
```bash
docker run xi-lang check -e "λx. x + 1"
# Output: Int → Int
```

### Run Tests
```bash
docker run xi-lang test
```

### Run Benchmarks
```bash
docker run xi-lang bench
```

## 3. Docker Compose (Optional)

```yaml
services:
  xi:
    build: .
    volumes:
      - ./src:/app/src
      - ./examples:/app/examples
    command: repl
    stdin_open: true
    tty: true
```

## 4. Available Commands

| Command | Description |
|---------|-------------|
| `repl` | Interactive REPL |
| `run <file>` | Execute a `.xi-src` file |
| `run -e <expr>` | Evaluate an expression |
| `check <file>` | Type check a file |
| `build <file>` | Compile to binary |
| `test` | Run test suite |
| `bench` | Run benchmarks |
| `demo` | Run all demo checks |

## 5. CI Integration

```yaml
# GitHub Actions
- name: Run Xi tests
  run: |
    docker build -t xi-lang .
    docker run xi-lang test
```
