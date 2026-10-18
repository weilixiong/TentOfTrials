#!/usr/bin/env bash
# launch-assistant.sh — OpenClaw / Hermes integration for Tent of Trials
#
# Launches an AI coding assistant (OpenClaw or Hermes) with the repository
# context already loaded: project purpose, tech stack per directory, common dev
# commands, coding conventions, known pitfalls, and a "where to start" map.
#
# Usage:
#   ./scripts/launch-assistant.sh [--tool openclaw|hermes] [--print-only]
#
# The script never pretends to know more than the repo does. If the assistant
# binary isn't on PATH it prints the assembled context bundle so you can paste
# it into whatever tool you actually have.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOL="openclaw"
PRINT_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool) TOOL="$2"; shift 2 ;;
    --print-only) PRINT_ONLY=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--tool openclaw|hermes] [--print-only]"
      exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

BUNDLE="$ROOT/.assistant-context.md"

cat > "$BUNDLE" <<'EOF'
# Tent of Trials — Assistant Context Bundle

## Project purpose
Trading and risk platform. Multi-module monorepo spanning Rust, TypeScript/React,
Go, C, C++, Java, Ruby, Lua, Haskell, and Python build glue.

## Tech stack per directory
- backend/       Rust (tokio, serde, clap, tracing) — microservice orchestration
- frontend/      TypeScript/React 19, Vite, zustand, react-query
- market/        Go 1.26 (gorilla/websocket, shopspring/decimal, zap)
- frailbox/      C (gcc, seccomp sandbox, hardening flags)
- frailbox/engine/  C++ (cmake)
- frailbox/nfc/  Lua
- compliance/    Java (ComplianceAuditor)
- v2/services/   Ruby (market_stream)
- tools/         Lua (openapi diff/mock/pact)
- docs/openapi/  Haskell (GHC)
- data/          shared fixtures

## Common dev commands
- python3 build.py                       # build all modules
- python3 build.py --clean                # clean
- python3 build.py --module backend,frontend
- python3 build.py --release              # Rust release
- backend: cargo build
- frontend: npm install && npm run build  (npm run dev for dev server)
- market: go build -o market .
- frailbox: make && make test
- engine: cmake -S . -B build && cmake --build build

## Build-and-diagnostic workflow (ALWAYS)
1. Run `python3 build.py` after every change.
2. Commit the generated diagnostic bundle in diagnostic/:
   - diagnostic/build-<commit-4-bytes>.logd
   - diagnostic/build-<commit-4-bytes>-metadata.json (if present)
3. The filename is derived from the first 4 bytes of the current commit.
4. Use .github/pull_request_template.md for submissions.
5. You may request the diagnostic be removed before merge.

## Coding conventions
- Scope changes to the PR purpose; no drive-by cleanup.
- Dry, self-deprecating tone in docs/comments; no marketing fluff.
- Backend: idiomatic Rust 2021, thiserror/anyhow, tracing.
- Frontend: TS strict, React 19, Vite; reuse zustand/react-query.
- Market: Go with zap; shopspring/decimal for money.
- C (frailbox): -Wall -Wextra -Wpedantic, C2x, hardening.
- No generated artifacts committed except the diagnostic log.

## Known pitfalls
- Many toolchains required (Rust, Node, Go, gcc, g++, cmake, javac, Ruby, Lua, GHC).
  Missing ones are reported but builds may fail mid-module.
- Frontend runs tsc -b first; type errors fail the build.
- C engine builds out-of-tree in build/.
- Go module path is github.com/tent-of-trials/market.
- On Windows tool resolution differs; prefer Linux/WSL for full builds.
- README license block has mojibake; do not "fix" unless asked.

## Where to start (which file to read first)
- backend/        -> backend/src/main.rs (or lib.rs), then Cargo.toml
- frontend/       -> frontend/src/main.tsx, then src/App.tsx
- market/         -> market/main.go, then matching/, orderbook/
- frailbox/       -> frailbox/src/main.c + include/
- frailbox/engine/-> CMakeLists.txt, engine.cpp
- compliance/     -> compliance/ComplianceAuditor.java
- v2/services/    -> v2/services/market_stream.rb
- tools/          -> tools/openapi_diff.lua
- docs/openapi/   -> docs/openapi/Types.hs
- build system    -> build.py (MODULES list at top)

## Conventions for this assistant
- Read CLAUDE.md and README.md before making changes.
- Always run `python3 build.py` after changes and include the diagnostic
  artifact in the PR.
- Keep the repo's dry, self-deprecating voice.
EOF

echo "Context bundle written to $BUNDLE"

if [[ $PRINT_ONLY -eq 1 ]]; then
  cat "$BUNDLE"
  exit 0
fi

case "$TOOL" in
  openclaw)
    if command -v openclaw >/dev/null 2>&1; then
      openclaw --context "$BUNDLE" "$ROOT"
    else
      echo "openclaw not found on PATH. Context bundle: $BUNDLE" >&2
      echo "Paste $BUNDLE into your assistant of choice." >&2
      exit 1
    fi
    ;;
  hermes)
    if command -v hermes >/dev/null 2>&1; then
      hermes --context "$BUNDLE" "$ROOT"
    else
      echo "hermes not found on PATH. Context bundle: $BUNDLE" >&2
      echo "Paste $BUNDLE into your assistant of choice." >&2
      exit 1
    fi
    ;;
  *)
    echo "Unknown tool: $TOOL (expected openclaw or hermes)" >&2
    exit 2
    ;;
esac