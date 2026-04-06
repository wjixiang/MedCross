# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MedCross is a Python monorepo for cross-disciplinary medical research tools — GWAS genetics, medical imaging (TCIA/DICOM), proteomics (PRIDE), radiomics, machine learning, and UK Biobank data access.

## Commands

```bash
# Install all workspace dependencies
uv sync

# Run a specific package's CLI
uv run --package opengwas-cli opengwas --help
uv run --package tcia-cli tcia --help
uv run --package pride-cli pride --help
uv run --package ukb-mcp ukb-mcp --help

# Start ukb-mcp FastAPI dev server (host 0.0.0.0, port 8000)
uv run --package ukb-mcp fastapi dev

# Run tests (ad-hoc integration scripts, not pytest-structured)
uv run pytest
```

## Monorepo Structure

Managed by `uv` workspaces. Root `pyproject.toml` defines `[tool.uv.workspace]` members (`libs/*`, `apps/*`) and `[tool.uv.sources]` for inter-package links.

**Workspace dependency graph:**
- `opengwas-cli` → `gwas-client`, `pymr`
- `pride-cli` → `pride-client`
- `ukb-mcp` → `dx-client`
- `pwas` → `dxpy` (external, not workspace-linked)

## Package Layout Patterns

Two layouts coexist:
- **libs/** use `src/` layout: `libs/dx-client/src/dx_client/`
- **apps/** mostly use flat layout: `apps/opengwas-cli/main.py` + `apps/opengwas-cli/lib/`
- Exception: `ukb-mcp` uses `src/` layout: `apps/ukb-mcp/src/ukb_mcp/`

## Architecture

### CLI Apps (opengwas-cli, tcia-cli, pride-cli)
All built with **Typer**. Commands split into `lib/commands/<subcommand>.py` modules. Shared `lib/output.py` for Rich table formatting. Each app wraps its corresponding `*-client` library.

### ukb-mcp (FastAPI + MCP)
Uses **DDD layered architecture**:
- `api/v1/` — FastAPI routes with `response_model` on all endpoints, dependency injection via `get_dx_client()`
- `domain/` — Service + Models per domain concept
- `config.py` — `pydantic_settings.BaseSettings` with env var loading
- `cli.py` — Argparse CLI for cache operations (`warm`, `cache-info`)
- `CacheStatusMiddleware` injects `X-Cache-Status` header on all responses
- Lifespan context manager handles DXClient connect/disconnect

### SDK Libraries (gwas-client, dx-client, pride-client)
- **gwas-client**: Abstract `IApiClient` → concrete `OpenGWAS_API_Client` covering all OpenGWAS REST v4 endpoints via `httpx`
- **dx-client**: Abstract `IDXClient` → `DXClient` wrapping `dxpy` with pluggable caching (`ICache` → `MemoryCache` / `DuckDBCache`). Full Pydantic model layer and typed exception hierarchy in `dx_exceptions.py`. Cohort creation logic in `cohort.py`
- **pride-client**: Async `API_Client` using `httpx.AsyncClient` with Pydantic response models

## Environment

- Python 3.13 required (`.python-version`)
- Root `.env` contains DNAnexus credentials (`DX_AUTH_TOKEN`, `DX_PROJECT_CONTEXT_ID`)
- Individual apps have their own `.env` files for API tokens
- No linting (ruff/black), type-checking (mypy), or CI configuration is set up
