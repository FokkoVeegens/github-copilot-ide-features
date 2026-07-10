# AGENTS

This repository collects GitHub Copilot release notes across IDEs using scheduled GitHub Actions workflows.

## Running a fetcher locally

```bash
pip install -r requirements.txt

# Fetch (or update) release notes for a specific IDE:
GITHUB_TOKEN=<your-token> python -m scripts.run --ide eclipse

# Re-running is safe — existing files are never overwritten (idempotent).
```

## Running the tests

```bash
pip install -r requirements.txt
ruff check scripts tests
pytest
node --test site/search.test.mjs
```

**Python**: Both `ruff` and `pytest` must pass before committing.  
**JavaScript**: All Node.js tests in `site/search.test.mjs` must pass.  
Run the full suite locally before pushing.

## Repository layout

```
config/ides.yml              – IDE configuration (id, fetcher, data_dir, source_url)
data/<ide>/<version>.json    – one JSON file per release; presence = already processed
data/<ide>/index.json        – auto-generated index of all versions with the release date and filename
scripts/run.py               – CLI entry point: --ide <id>
scripts/build_search_index.py – Build search index for the GitHub Pages site
scripts/common/              – shared utilities (config, HTTP, JSON schema, extraction, I/O)
scripts/fetchers/            – one module per IDE (eclipse.py, dummy.py, …)
site/                        – static GitHub Pages site (index.html, app.js, search.js, style.css)
site/search.test.mjs         – JavaScript tests for site/search.js
tests/                       – pytest test suite
.github/workflows/           – GitHub Actions workflows (fetch-*.yml, deploy-pages.yml, ci.yml)
```

## Adding a new IDE

1. Add an entry to `config/ides.yml` with `id`, `name`, `data_dir`, `fetcher`, and source URL fields.
2. Create `scripts/fetchers/<fetcher>.py` with a `fetch(ide_config) -> list[dict]` function.
3. Add a `mkdir -p data/<ide>` directory (a `.gitkeep` is fine to start).
4. Add a `.github/workflows/fetch-<ide>.yml` workflow (copy `fetch-eclipse.yml` and update `--ide`).

## Workflow behaviour

### Fetch workflows
Each `fetch-*.yml` workflow runs on a daily cron and can also be triggered manually via `workflow_dispatch`.
It commits any newly written files directly to `main`. If the fetcher produces no new files, no
commit is made (no empty commits).

When a workflow is triggered on a non-default branch, the commit step is skipped. Instead, a
"Simulate commit" step logs which files *would* have been committed, allowing safe testing of
the fetch logic on feature branches without writing to the repository.

### Pages deployment workflow
The `deploy-pages.yml` workflow:
- **Triggers**: On `push` to `main` with changes to `data/**`, `site/**`, `scripts/**`, or `config/ides.yml`; also on `pull_request` and `workflow_dispatch`
- **Test job**: Runs Python linting, pytest, and JavaScript tests (before any builds)
- **Build job**: Generates the search index via `build_search_index.py` and builds the Pages artifact
- **Deploy job**: Deploys to GitHub Pages (only on `main` branch)
- **Development**: On feature branches, only test + build jobs run (no deployment)
