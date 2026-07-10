# GitHub Copilot features per IDE

[![CI](https://github.com/FokkoVeegens/github-copilot-ide-features/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/FokkoVeegens/github-copilot-ide-features/actions/workflows/ci.yml)

This repository collects release notes for GitHub Copilot features across different IDEs. Scheduled GitHub Actions workflows collect the release notes from the official IDEs and IDE extensions/plugins and store these in json files.

## Usage

The repository contains a **Skill** that can be used along with GitHub Copilot or another AI coding assistant to query the collected release notes data. For example, you can ask:

`/find-feature Next Edit Suggestions (NES)`

It would then return a summary of the release notes for that feature across all IDEs, including which IDE versions support it. The repository data is updated daily by scheduled GitHub Actions workflows, so you can be confident that the information is up to date. Pull the latest changes in this repository before asking the Skill so you have the latest data.

## Website

The repository hosts a **searchable feature matrix** on GitHub Pages at [https://FokkoVeegens.github.io/github-copilot-ide-features/](https://FokkoVeegens.github.io/github-copilot-ide-features/).

### How it works

- Enter a keyword (minimum 5 characters) to search across Copilot feature mentions in all IDEs.
- The matrix shows which IDE versions first mention that feature.
- Clicking on a version badge links to the official release notes.

### Running the site locally

```bash
# Build the search index
python -m scripts.build_search_index --output site

# Serve locally
python -m http.server -d site 8000

# Visit http://localhost:8000/
```

The site is a pure client-side application: HTML, CSS, and ES module JavaScript with no external dependencies. It loads a pre-built search index at page load and performs all searching in the browser.

## Repository layout

```
config/ides.yml              – single source of truth for IDE configuration
data/<ide>/<version>.json    – one JSON file per release; presence = already processed
data/<ide>/index.json        – auto-generated index of all versions with metadata
scripts/run.py               – CLI entry point
scripts/build_search_index.py – Build search index for the GitHub Pages site
scripts/common/              – shared utilities (config, HTTP, extraction, I/O)
scripts/fetchers/            – one module per IDE
site/                        – static GitHub Pages site (HTML, CSS, JavaScript)
tests/                       – pytest test suite
```

Fetcher endpoints are configured centrally in [config/ides.yml](config/ides.yml), including `source_url` and any per-IDE URL templates or canonical plugin URLs needed by a fetcher.

### Index files

Each IDE directory contains an automatically-generated `index.json` file that provides a quick reference to all available versions. The index contains an array of objects with the following properties:

```json
[
  {
    "version": "1.122.0",
    "release_date": "2026-05-28",
    "filename": "1.122.0.json"
  }
]
```

The index is sorted by `release_date` in descending order (newest first) and is regenerated each time the fetch workflow runs.

## Supported IDEs

| ID | Name |
|----|------|
| `eclipse` | Copilot for Eclipse |
| `copilot-cli` | GitHub Copilot CLI |
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

The fetchers that call the GitHub REST API (Eclipse, GitHub Copilot CLI) only read **public** repositories, so no specific OAuth scopes are required. Xcode (feature matrix + public `CHANGELOG.md`) and Vim/Neovim scrape public docs and do not require authentication.

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
node --test site/search.test.mjs
```

**Python**: Both `ruff` and `pytest` must pass before committing.  
**JavaScript**: All Node.js tests in `site/search.test.mjs` must pass.  
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

## GitHub Pages configuration

The website is deployed from GitHub Actions to GitHub Pages. To configure it for a new repository:

1. **Settings → Pages** → Set *Build and deployment* → **Source = GitHub Actions** (not "Deploy from a branch")
2. **Settings → Environments** → Confirm `github-pages` environment exists; optionally restrict to `main` branch
3. **Settings → Actions → General** → Ensure workflow permissions allow OIDC (usually default; no change needed)
4. **First deploy**: Manually trigger the `deploy-pages.yml` workflow via **Actions** or wait for the next push to `main` affecting `data/`, `site/`, `scripts/`, or `config/ides.yml`
5. **Site URL**: `https://<owner>.github.io/<repo-name>/` — all relative URLs in the site use `./` to work correctly from the sub-path
