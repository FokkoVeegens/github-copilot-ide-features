# GitHub Copilot features per IDE

This repository collects release notes for GitHub Copilot features across different IDEs. Scheduled GitHub Actions workflows collect the release notes from the official IDEs and IDE extensions/plugins and store these in json files.

## Repository layout

```
config/ides.yml          – single source of truth for IDE configuration
data/<ide>/<version>.json – one JSON file per release; presence = already processed
scripts/run.py           – CLI entry point
scripts/common/          – shared utilities (config, HTTP, extraction, I/O)
scripts/fetchers/        – one module per IDE
tests/                   – pytest test suite
```

Fetcher endpoints are configured centrally in [config/ides.yml](config/ides.yml), including `source_url` and any per-IDE URL templates or canonical plugin URLs needed by a fetcher.

## Supported IDEs

| ID | Name |
|----|------|
| `eclipse` | Copilot for Eclipse |
| `jetbrains` | GitHub Copilot for JetBrains |
| `xcode` | GitHub Copilot for Xcode |
| `vim-neovim` | GitHub Copilot for Vim/Neovim |
| `vs-code` | GitHub Copilot for VS Code |
| `visual-studio-2022` | Visual Studio 2022 |
| `visual-studio-2026` | Visual Studio 2026 |

## Running a fetcher locally

```bash
pip install -r requirements.txt

# Fetch (or update) release notes for a single IDE:
python -m scripts.run --ide xcode

# Set GITHUB_TOKEN for higher API rate limits (recommended):
GITHUB_TOKEN=ghp_... python -m scripts.run --ide eclipse
```

Re-running the same command is safe: existing files are never overwritten (idempotent).

### GitHub token scopes

The fetchers that call the GitHub REST API (Eclipse, Xcode) only read **public** repositories, so no specific OAuth scopes are required. Any of the following work:

> **Note:** The Vim/Neovim fetcher does not use the GitHub REST API. It scrapes the [GitHub Copilot feature matrix](https://docs.github.com/en/copilot/reference/copilot-feature-matrix?tool=vimneovim) docs page, which is publicly accessible without authentication.

| Token type | Required scopes |
|-----------|----------------|
| Personal access token (classic) | *(none — leave all scopes unchecked)* |
| Fine-grained PAT | `Public Repositories (read-only)` access (the default) |
| GitHub Actions `GITHUB_TOKEN` | Default permissions are sufficient; no extra configuration needed |

Without a token the API allows **60 requests per hour per IP address**. Any authenticated token raises this to **5,000 requests per hour**.

## Running the tests

```bash
pip install -r requirements.txt
ruff check scripts tests
pytest
```

GitHub Actions CI runs the same test suite on pushes to `main`, pull requests, and manual dispatches. It also runs `python -m compileall scripts tests` as a fast syntax check before `pytest`.

## Output format

Each file under `data/<ide>/` follows the JSON schema defined in `scripts/common/schema.json`. Key fields:

| Field | Description |
|-------|-------------|
| `ide` | IDE identifier matching `config/ides.yml` |
| `version` | Normalised version string (e.g. `0.16.0`) |
| `release_date` | ISO-8601 date (`YYYY-MM-DD`) |
| `body_markdown` | Full release notes as Markdown |
| `copilot_mentions` | Lines from the notes matching a Copilot/AI heuristic |
| `source` | How the data was obtained (`api`, `feed`, `html`, …) |
| `neovim_era` | Vim/Neovim-only era key (for example `neovim-latest`, `neovim-2024`) |
