# CLAUDE.md

> Claude Code's cheat sheet for Tent of Trials. If you're reading this, you already know more than the build system does about your machine. Good luck.

## Project purpose

Tent of Trials is a trading and risk platform stitched together from ~12 languages and a questionable amount of optimism. It's a multi-module monorepo: a Rust backend orchestration layer, a TypeScript/React frontend, a Go market engine, a C sandbox ("frailbox"), a C++ engine, Java compliance auditor, Ruby market stream, Lua scanners, Haskell OpenAPI tooling, and Python build/diagnostic glue. Nothing here is simple, but everything is *documented* (this file exists to prove it).

## Repo layout

| Dir | Language | What it is |
|---|---|---|
| `backend/` | Rust | Microservice orchestration framework (`tent-backend`) |
| `frontend/` | TypeScript/React | Vite + React 19 SPA (`tent-frontend`) |
| `market/` | Go | Market engine (matching, orderbook, pricing, ws) |
| `frailbox/` | C | Sandboxed execution environment |
| `frailbox/engine/` | C++ | Trial engine (cmake) |
| `frailbox/nfc/` | Lua | NFC scanner |
| `compliance/` | Java | ComplianceAuditor |
| `v2/services/` | Ruby | Market stream |
| `tools/` | Lua | OpenAPI diff/mock/pact |
| `docs/openapi/` | Haskell | OpenAPI types/server/validate/generate |
| `data/` | — | Shared data/fixtures |
| `diagnostic/` | — | Git-tracked build diagnostic bundles (`.logd` + metadata) |

## Common dev commands

```sh
python3 build.py                       # build all modules
python3 build.py --clean               # clean all artifacts
python3 build.py --module backend,frontend  # build specific modules
python3 build.py --release             # release mode (Rust only)
python3 build.py --list                # list modules
```

Per-module:

```sh
# backend (Rust)
cd backend && cargo build            # or cargo build --release

# frontend (TS/React)
cd frontend && npm install && npm run build   # tsc -b && vite build
cd frontend && npm run dev                  # vite dev server

# market (Go)
cd market && go build -o market .

# frailbox (C)
cd frailbox && make && make test

# engine (C++)
cd frailbox/engine && cmake -S . -B build && cmake --build build

# compliance (Java)
cd compliance && javac -d build ComplianceAuditor.java

# v2 market stream (Ruby)
cd v2/services && ruby -c market_stream.rb

# lua scanners / tools
luac -p frailbox/nfc/scanner.lua
luac -p tools/openapi_diff.lua tools/openapi_mock.lua tools/openapi_pact.lua

# haskell openapi
cd docs/openapi && ghc -fno-code Types.hs Server.hs Validate.hs Generate.hs
```

## Build-and-diagnostic workflow (REQUIRED for PRs)

1. Run `python3 build.py` after any change.
2. The build writes a diagnostic bundle into `diagnostic/`:
   - `diagnostic/build-<commit-4-bytes>.logd` (encrypted log)
   - `diagnostic/build-<commit-4-bytes>-metadata.json` (decrypt password + module results)
   The filename is derived from the first 4 bytes of the current commit, so it's stable per commit.
3. Commit the generated `.logd` (and metadata if present) in your PR.
4. You may request the diagnostic be removed before merge (see PR template checkbox).
5. Use `.github/pull_request_template.md` for every submission.

The `diagnostic/` directory ships a stub example so you can see the expected shape; real `.logd` files come from `python3 build.py`.

## Coding conventions

- Keep changes scoped to the PR purpose; no drive-by cleanup.
- Match the repo's self-deprecating, dry tone in docs and comments.
- Backend: idiomatic Rust 2021, `thiserror`/`anyhow` for errors, `tracing` for logs.
- Frontend: TypeScript strict, React 19, Vite; prefer existing state libs (zustand, react-query) over new ones.
- Market: Go with `zap` logging; decimal via `shopspring/decimal`.
- C (frailbox): `-Wall -Wextra -Wpedantic`, C2x, hardening flags (`_FORTIFY_SOURCE=3`, stack protector, PIE, RELRO).
- No generated build artifacts committed except the required diagnostic log.
- Consider security/privacy/error-handling implications for every change.

## Known pitfalls

- The build needs a small army of toolchains (Rust, Node, Go, gcc, g++, cmake, javac, Ruby, Lua, GHC). Missing ones are reported but the build will still attempt and may fail mid-module.
- `python3 build.py` writes to `diagnostic/`; don't gitignore it.
- Frontend build runs `tsc -b` first — type errors fail the build even if Vite would succeed.
- The C engine uses cmake out-of-tree (`build/`); clean with `rm -rf build`.
- Go module path is `github.com/tent-of-trials/market` (not `tent-of-trials/TentOfTrials`).
- On Windows, tool resolution differs (no `npm` shim); prefer a Linux/WSL environment for full builds.
- README has mojibake in the license block; don't "fix" it unless asked.

## Where to start (per module)

- `backend/` → `backend/src/main.rs` (or `lib.rs`) then `Cargo.toml`
- `frontend/` → `frontend/src/main.tsx` and `frontend/src/App.tsx`
- `market/` → `market/main.go`, then `market/matching/`, `market/orderbook/`
- `frailbox/` → `frailbox/src/main.c` and `frailbox/include/`
- `frailbox/engine/` → `frailbox/engine/CMakeLists.txt` and `engine.cpp`
- `compliance/` → `compliance/ComplianceAuditor.java`
- `v2/services/` → `v2/services/market_stream.rb`
- `tools/` → `tools/openapi_diff.lua`
- `docs/openapi/` → `docs/openapi/Types.hs`
- `build.py` → top of file (MODULES list) for module definitions

## Tone note

This repo's README opens with "Trading and risk platform." and means it. Keep docs dry, a little self-deprecating, and free of marketing fluff. If a sentence sounds like a press release, rewrite it.
PY