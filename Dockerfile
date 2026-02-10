# ═══════════════════════════════════════════════════════════════
# Ξ (Xi) — The final programming language
# Copyright (c) 2026 Alex P. Slaby — MIT License
#
# Build:  docker build -t xi-lang .
# Run:    docker run xi-lang
# REPL:   docker run -it xi-lang repl
# Tests:  docker run xi-lang test
# ═══════════════════════════════════════════════════════════════

FROM python:3.12-slim

LABEL maintainer="Alex P. Slaby"
LABEL description="Ξ (Xi) — AI-native programming language with 10 primitives"
LABEL version="0.1.0"

WORKDIR /xi

# Copy everything (Dockerfile, editors, etc. included for test completeness)
COPY . .

RUN pip install --no-cache-dir pytest hypothesis

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["demo"]
