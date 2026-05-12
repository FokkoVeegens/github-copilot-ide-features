# Plan: Automated IDE release-notes collection

## TL;DR
Build a Python-based scraper toolkit driven by a single `config/ides.yml`, executed by per-IDE GitHub Actions workflows on a daily cron. Each IDE has a dedicated fetcher module that handles its source quirks (Atom feed + per-version page scrape, HTML release-notes page splitting, JetBrains Marketplace REST API). Each release becomes one JSON file at `data/<ide>/<version>.json`; presence of the file = "already processed", which makes incremental runs naturally idempotent. A `start_version` (or `start_date`) per IDE filters out pre-Copilot releases. Workflows commit new files via a PR or directly to main.

## Sources — verified findings
- **VS Code** `https://code.visualstudio.com/feed.xml` — Atom feed, no pagination, mixes "release" and "blog" `<category>` entries. Only ~30 most recent entries. To backfill to 1.75 we must construct URLs `https://code.visualstudio.com/updates/v1_<N>` directly (N from 75…current). Per-version page contains the full release notes HTML.
- **Visual Studio 2022 / 2026** — the `devblogs.microsoft.com/vsnews/feed` is stale (last item 2021). NOT usable. Instead scrape `https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes` (and `…/2026/…`) which is one large HTML page with `## Version 17.X.Y` sections covering every servicing release; must split by heading. There is also a per-major-version "history" page `…/release-history` we may need to follow for older majors (17.0–17.13).
- **JetBrains** `https://plugins.jetbrains.com/api/plugins/17718/updates?page=N&size=100` — clean JSON. Each plugin release has multiple entries (one per IntelliJ build line, e.g. `1.8.2-242` and `1.8.2-243`); we will collapse on the semantic version (`1.8.2`) and store per-build compat info inside the file.
- **Xcode** — official repo `github/CopilotForXcode`. GitHub Releases API: `https://api.github.com/repos/github/CopilotForXcode/releases?per_page=100&page=N`. ⚠️ Release body content is a one-line placeholder ("Release 0.48.0 of Copilot extension for Xcode"); the real changelog lives in `CHANGELOG.md` on the default branch. Plan: fetch the CHANGELOG via raw.githubusercontent.com and split per version; use Releases API to get the publish date + tag list.
- **Vim/Neovim** — No useful changelog exists in `github/copilot.vim`. Data is sourced from the [GitHub Copilot feature matrix](https://docs.github.com/en/copilot/reference/copilot-feature-matrix?tool=vimneovim) docs page, which lists supported features per Copilot extension version, organised into NeoVim era sections (latest, 2024, 2023, 2022, 2021). Produces one JSON record per plugin version (e.g. `1.18.0.json`); the NeoVim era is stored as a `neovim_era` property inside each file. `body_markdown` contains a bullet list of only the features that are supported (✓) or partially supported for that version — unsupported features (✗) are omitted. No GitHub API or authentication required.
- **Eclipse** — official repo `microsoft/copilot-for-eclipse` (NOT `github/CopilotForEclipse` which 404s). GitHub Releases API: `https://api.github.com/repos/microsoft/copilot-for-eclipse/releases?per_page=100&page=N`. ⭐ Release body is rich HTML (Added/Changed/Fixed sections) — ready to use directly, no extra scraping needed. Earliest release `0.9.2 - 20250723`; copilot-for-eclipse first ships in ~2025.
- **SQL Server Management Studio** — Copilot was introduced in SSMS 21 (May 2025). One large HTML page per major: `https://learn.microsoft.com/en-us/ssms/release-notes-22`, `…/release-notes-21`. Same structural pattern as Visual Studio: `### X.Y.Z` headings with "Release date: <date>" lines and `#### What's new in X.Y.Z` / `#### Bug fixes in X.Y.Z` subsections. Reuse the Visual Studio HTML splitter.

## Phases & Steps

### Phase 1 — Repo scaffolding (foundation, blocks all later phases)
1. Add `config/ides.yml` listing each IDE with: `id`, `name`, `data_dir`, `fetcher` (module name), `start_version` / `start_date`, source URLs.
2. Add `scripts/` Python package: `scripts/common/` (config loader, JSON schema, file-naming, version comparison via `packaging.version`, HTTP client with retries/UA, HTML→Markdown via `markdownify`, copilot-mention extractor), `scripts/fetchers/` (one module per IDE).
3. Add `pyproject.toml` (or `requirements.txt`) pinning: `requests`, `feedparser`, `beautifulsoup4`, `lxml`, `markdownify`, `pyyaml`, `packaging`.
4. Add `scripts/run.py` CLI: `python -m scripts.run --ide <id>` — loads config, runs fetcher, writes only new files, prints a summary.
5. Update `AGENTS.md` and `README.md` with run instructions and the layout.

### Phase 2 — Shared schema & utilities (parallel with Phase 3 fetchers)
1. Define JSON schema (one file = one release):
   - `ide` (string id), `version` (semver-ish), `release_date` (ISO-8601), `title`, `url` (canonical release-notes URL), `source` (`feed` / `html` / `api`), `body_markdown`, `body_html` (raw), `categories[]`, `copilot_mentions[]` (lines/sections containing /copilot|github copilot|ai|chat|agent/i — heuristic configurable per-IDE), `fetched_at`, `schema_version`.
2. File naming: `data/<ide>/<version>.json` — version normalized (e.g. `1.75.0` not `v1_75`). Existence check = idempotency.
3. `copilot_mentions` extraction: split body into list items / paragraphs, regex-match the pattern, store the matching snippets (still preserving full notes).

### Phase 3 — Per-IDE fetchers (each step parallel with the others)
1. **vs-code fetcher** (`fetchers/vs_code.py`):
   - Parse `feed.xml` to discover the latest version number.
   - Iterate N from `start_version` (1.75) up to latest, fetch `https://code.visualstudio.com/updates/v1_<N>`, extract `<main>` content, store as `1.<N>.0.json`. Skip if file already exists.
   - Skip blog entries (filter by `<category term="release"/>` or by URL pattern `/updates/v1_`).
2. **visual-studio-2022 / visual-studio-2026 fetcher** (`fetchers/visual_studio.py`, parameterized by year):
   - Fetch the year's `release-notes` HTML page.
   - Parse h2/h3 sections matching `Version X.Y.Z` (and the dated header beneath, e.g. *Released April 21st, 2026*) — extract release date and per-version body.
   - For 2022, iterate older majors (17.0..17.13) via `release-history` page links. Document this as a follow-up if older history page is structured differently.
   - Filter releases below `start_version`.
3. **jetbrains fetcher** (`fetchers/jetbrains.py`):
   - Page through `https://plugins.jetbrains.com/api/plugins/17718/updates?page=N&size=100` until empty. (Note: API returns flat array; loop until empty page.)
   - Group entries by semantic version (drop the `-NNN` IDE-build suffix). For each group, write one JSON file `<semver>.json` containing: shared `notes` (HTML+markdown), `release_date` (earliest cdate), and a `builds[]` array with `{ide_build, since, until, compatibleVersions, file_id, downloads}`.
   - `start_version: all` — no filter; backfill everything currently exposed by the API.
4. **xcode fetcher** (`fetchers/xcode.py`):
   - List releases via `GET https://api.github.com/repos/github/CopilotForXcode/releases?per_page=100&page=N` (use `GITHUB_TOKEN` for higher rate limit).
   - Fetch `CHANGELOG.md` from default branch (raw.githubusercontent.com), split by `## [X.Y.Z]` / `## X.Y.Z` headings.
   - For each tag from the API, look up the matching CHANGELOG section; if missing (e.g. pre-release patch), fall back to the API release body.
   - Store `<version>.json` (e.g. `0.48.0.json`); record `prerelease` boolean from API.
5. **vim-neovim fetcher** (`fetchers/copilot_vim.py`):
   - HTML scraper of the [GitHub Copilot feature matrix](https://docs.github.com/en/copilot/reference/copilot-feature-matrix?tool=vimneovim) docs page.
   - Produces one JSON record per plugin version (e.g. `1.18.0.json`); the NeoVim era section (`neovim-latest`, `neovim-2024`, …) is stored as a `neovim_era` field inside each record.
   - `body_markdown` = bullet list of supported features only; features marked ✗ are excluded. Features with partial support (P/C) are listed with their qualifier in parentheses.
   - No GitHub API needed; `use_auth=False` for the docs page.
6. **eclipse fetcher** (`fetchers/eclipse.py`):
   - Page through `GET https://api.github.com/repos/microsoft/copilot-for-eclipse/releases?per_page=100&page=N`.
   - Release body is already rich HTML (Added/Changed/Fixed) — store directly as `body_html`, convert to markdown for `body_markdown`.
   - Title format `0.16.0 - 20260403` — parse semver and yyyymmdd into `version` and `release_date`.
   - `start_version: all` (plugin only exists post-Copilot).
7. **ssms fetcher** (`fetchers/ssms.py`):
   - Fetch one HTML page per major: `release-notes-22`, `release-notes-21`. (Older 19/20 don't have Copilot — exclude via config.)
   - Reuse the Visual Studio HTML splitter (parameterized): split on `### X.Y.Z` headings; capture the "Release date: <Month Day, Year>" line and the `What's new` / `Bug fixes` subsections as the body.
   - `start_version: 21.0.0` (Copilot in SSMS introduced in SSMS 21 GA, May 2025).

### Phase 4 — GitHub Actions workflows
1. One workflow per IDE under `.github/workflows/`: `fetch-vs-code.yml`, `fetch-visual-studio-2022.yml`, `fetch-visual-studio-2026.yml`, `fetch-jetbrains.yml`, `fetch-xcode.yml`, `fetch-vim-neovim.yml`, `fetch-eclipse.yml`, `fetch-ssms.yml`. Each:
   - Triggers: `schedule: cron '17 6 * * *'` (daily, staggered minutes per IDE), and `workflow_dispatch` for manual backfills.
   - Steps: checkout → setup-python 3.12 → `pip install -r requirements.txt` → `python -m scripts.run --ide <id>` → if new files, commit on `main` using `peter-evans/create-pull-request@v6` (PR-based, safer) OR `git commit && push` for direct mode (decide via Further Considerations #1).
   - Permissions: `contents: write`, `pull-requests: write` (only if PR mode); GitHub API fetchers (Xcode, Vim, Eclipse) use the workflow's `GITHUB_TOKEN` for rate-limit headroom.
2. Optional `fetch-all.yml` that calls the others via `workflow_call` for ad-hoc full runs.

### Phase 5 — Hardening (after Phase 4 green)
1. Backfill: trigger each workflow once via `workflow_dispatch` with `force_backfill=true` input that ignores existing files for one run.
2. Add a small CI lint workflow that validates each `data/<ide>/*.json` against the schema (using `jsonschema`).
3. All seven IDEs covered in this iteration — no remaining placeholder folders.

## Relevant files (to be created)
- [config/ides.yml](config/ides.yml) — single source of truth for IDE config.
- [scripts/run.py](scripts/run.py) — CLI entry point.
- [scripts/common/__init__.py](scripts/common/__init__.py), [scripts/common/config.py](scripts/common/config.py), [scripts/common/http.py](scripts/common/http.py), [scripts/common/io.py](scripts/common/io.py), [scripts/common/extract.py](scripts/common/extract.py).
- [scripts/fetchers/vs_code.py](scripts/fetchers/vs_code.py), [scripts/fetchers/visual_studio.py](scripts/fetchers/visual_studio.py), [scripts/fetchers/jetbrains.py](scripts/fetchers/jetbrains.py).
- [pyproject.toml](pyproject.toml) or [requirements.txt](requirements.txt).
- [.github/workflows/fetch-vs-code.yml](.github/workflows/fetch-vs-code.yml), [.github/workflows/fetch-visual-studio-2022.yml](.github/workflows/fetch-visual-studio-2022.yml), [.github/workflows/fetch-visual-studio-2026.yml](.github/workflows/fetch-visual-studio-2026.yml), [.github/workflows/fetch-jetbrains.yml](.github/workflows/fetch-jetbrains.yml).
- Existing [data/vs-code/](data/vs-code/), [data/visual-studio-2022/](data/visual-studio-2022/), [data/visual-studio-2026/](data/visual-studio-2026/), [data/jetbrains/](data/jetbrains/) — targets for output.

## Verification
1. Run each fetcher locally: `python -m scripts.run --ide vs-code` etc., assert ≥1 new JSON file in `data/<ide>/` and that re-running produces 0 new files (idempotency).
2. Validate every produced JSON file with `jsonschema` against the schema in `scripts/common/schema.json`.
3. Spot-check `body_markdown` for a known release (e.g. VS Code 1.95) contains the expected Copilot section and that `copilot_mentions` is non-empty.
4. JetBrains: confirm `1.5.62` and `1.5.63` produce one file each with multiple `builds[]` entries (-241, -242, -243).
5. Visual Studio: confirm `17.14.31` and `17.14.1` are split into separate files with correct `release_date` parsed from "Released April 21th, 2026".
6. Trigger each workflow via `workflow_dispatch` and confirm it commits / opens a PR with new JSONs.

## Decisions
- Runtime: Python 3.12.
- Schema: extended (raw_html, categories, copilot_mentions[]).
- Filter: store full notes; do not pre-filter.
- Schedule: daily cron + manual dispatch.
- Naming: `data/<ide>/<version>.json`; presence = processed.
- Config: single `config/ides.yml`.
- JetBrains source: Marketplace REST API only.
- IDEs covered (7): VS Code, Visual Studio 2022, Visual Studio 2026, JetBrains, Xcode, Vim/Neovim (`copilot.vim`), Eclipse, SSMS.
- Existing `data/` folders renamed where needed: keep `vs-code`, `visual-studio-2022`, `visual-studio-2026`, `jetbrains`, `eclipse`, `vim-neovim`, `sql-server-management-studio`. Add `xcode/`.

## Further Considerations
1. **Commit strategy** — How should the workflows publish new files?
   - A) Direct push to `main` (simplest, fastest) — *recommended* for a data-collection repo with low blast radius.
   - B) Open a PR per IDE per day with `peter-evans/create-pull-request` (review gate, noisier).
2. **JetBrains: per-IDE-build vs. semver grouping** — current plan groups by semver (`1.8.2.json`) with a `builds[]` array. Alternative: one file per `version+build` (e.g. `1.8.2-242.json`, `1.8.2-243.json`). Grouping is cleaner for "Copilot release notes" since the notes text is identical across builds.
3. **Visual Studio older majors (17.0–17.13)** — the current 17.14 page only contains 17.14.x entries. We need to also crawl `release-history` and per-major archived pages. Recommend a follow-up phase once 17.14 fetcher works, since the HTML structure may differ.
4. **`start_version` semantics** — recommend `start_version` (string, semver-compared) for VS Code & JetBrains, and `start_date` (YYYY-MM-DD) as an alternative for HTML sources where parsing the version is unreliable. Both supported in config; fetcher picks whichever is set.

---

## MVPs — testable in isolation

Each MVP is independently runnable, locally verifiable, and additive (later MVPs build on earlier outputs without breaking them). Ordered by smallest-blast-radius first.

### MVP 0 — Walking skeleton (no network)
**Goal:** prove the pipeline shape end-to-end with a fake fetcher.

- `config/ides.yml` with one fake entry: `id: dummy`, `fetcher: dummy`.
- `scripts/common/`: config loader, JSON schema, `io.write_release()` (idempotent: skip if file exists).
- `scripts/fetchers/dummy.py`: returns 2 hardcoded release dicts.
- `scripts/run.py --ide dummy` writes `data/dummy/0.0.1.json` and `0.0.2.json`.
- `requirements.txt` pinning the minimal deps (`pyyaml`, `packaging`, `jsonschema`).

**Test in isolation:**
1. `python -m scripts.run --ide dummy` → 2 new files, exit 0.
2. Re-run → 0 new files (idempotency).
3. `jsonschema` validates both files.
4. No internet required → runs in any sandbox.

**Done when:** the runner, config, schema, and write-once semantics work without any real source.

---

### MVP 1 — Eclipse fetcher (simplest real source)
**Why first:** GitHub Releases API returns rich HTML bodies directly — no CHANGELOG cross-reference, no HTML splitting, no pagination quirks. Smallest real fetcher.

- Add `requests` + `markdownify` + `beautifulsoup4` to deps.
- `scripts/common/http.py` (retries, UA, optional `GITHUB_TOKEN`).
- `scripts/common/extract.py`: HTML → markdown + `copilot_mentions` regex.
- `scripts/fetchers/eclipse.py`: paginate `/releases`, parse `0.16.0 - 20260403` title.

**Test in isolation:**
1. `python -m scripts.run --ide eclipse` → N files in `data/eclipse/`.
2. Re-run → 0 new files.
3. Spot-check one file: `release_date` parsed correctly, `body_markdown` non-empty, `copilot_mentions[]` populated.
4. Schema validation passes for all files.

**Done when:** Eclipse backfill is complete and stable, and the workflow runs cleanly in CI. Validates the schema + extract utilities against real-world HTML, and proves the CI plumbing before fanning out.

**Why include the workflow here:** the Eclipse fetcher is the simplest real fetcher and the ideal place to validate commit strategy, `GITHUB_TOKEN` usage, and idempotent CI runs. Every subsequent workflow is a copy-paste with a different `--ide` flag — no value in deferring.

**Additional steps (CI):**
- `.github/workflows/fetch-eclipse.yml`: cron + `workflow_dispatch`, direct push to main (per Decision A).
- Permissions: `contents: write`.

**Additional tests (CI):**
5. Trigger via `workflow_dispatch` on a branch — confirm green run.
6. Delete one local file, trigger again — confirm exactly that file is recommitted.
7. Trigger again — confirm "no changes" (no empty commits).

---

### MVP 2 — JetBrains fetcher (JSON API + grouping logic)
**Why next:** clean JSON, but introduces semver-grouping + `builds[]` array — exercises the schema's flexibility before harder HTML sources.

- `scripts/fetchers/jetbrains.py`: paginate Marketplace API, group by semver, collapse builds.

**Test in isolation:**
1. Run → files like `1.5.62.json` containing multiple `builds[]` entries.
2. Re-run → 0 new files.
3. Assert: `1.5.62.json` has builds `-241`, `-242`, `-243`.
4. Assert: shared `notes` text is identical across builds (sanity for grouping).

**Done when:** grouping logic is verified on real data; schema accommodates `builds[]`.

---

### MVP 3 — Xcode + Vim/Neovim fetchers
**Xcode** follows the CHANGELOG.md pattern (GitHub Releases API for tag/date + raw `CHANGELOG.md` split by version heading).
**Vim/Neovim** uses a different approach: HTML scraping of the GitHub Copilot feature matrix docs page.

- `scripts/common/changelog.py`: split markdown by `## [X.Y.Z]` / `## X.Y.Z` (used by Xcode).
- `scripts/fetchers/xcode.py` uses the changelog helper.
- `scripts/fetchers/copilot_vim.py` scrapes the feature matrix page (no GitHub API).

**Test in isolation:**
1. Run each → files in `data/xcode/` and `data/vim-neovim/`.
2. Xcode spot-check: a known version's `body_markdown` matches the CHANGELOG section (not the placeholder API body).
3. Vim/Neovim spot-check: one file per plugin version (e.g. `1.18.0.json`) produced; each file has a `neovim_era` field and `body_markdown` containing only the supported features as a bullet list.
4. Re-run idempotent.

**Done when:** Xcode CHANGELOG splitter is reusable; Vim/Neovim produces 5 clean era records.

**Additional steps (CI):**
- `.github/workflows/fetch-xcode.yml`: cron + `workflow_dispatch`, direct push to main (per Decision A).
- `.github/workflows/fetch-vim-neovim.yml`: cron + `workflow_dispatch`, direct push to main.
- Permissions: `contents: write`.

**Additional tests (CI):**
5. Trigger each via `workflow_dispatch` on a branch — confirm green run.
6. Delete one file per IDE, trigger again — confirm exactly that file is recommitted.
7. Trigger again — confirm "no changes" (no empty commits).

---

### MVP 4 — VS Code fetcher (Atom feed + version-URL crawl)
**Why now:** introduces feed parsing + URL construction + per-version page scrape. Independent of the HTML splitter used by VS / SSMS.

- Add `feedparser`.
- `scripts/fetchers/vs_code.py`: discover latest N from feed, iterate `v1_75`…`v1_N`, scrape `<main>`.

**Test in isolation:**
1. Run → files `1.75.0.json`…`1.<latest>.0.json`.
2. Re-run → 0 new files.
3. Spot-check `1.95.0.json`: contains the expected Copilot section, `copilot_mentions[]` non-empty.
4. Confirm blog feed entries are filtered out.

**Done when:** all VS Code releases since 1.75 are captured.

**Additional steps (CI):**
- `.github/workflows/fetch-vs-code.yml`: cron + `workflow_dispatch`, direct push to main (per Decision A).
- Permissions: `contents: write`.

**Additional tests (CI):**
5. Trigger via `workflow_dispatch` on a branch — confirm green run.
6. Delete one local file, trigger again — confirm exactly that file is recommitted.
7. Trigger again — confirm "no changes" (no empty commits).

---

### MVP 5 — HTML splitter + Visual Studio 2026 (current-only)
**Why split from VS 2022:** 2026 page only has current-major entries → simplest application of the splitter. Defer 2022 historical majors to MVP 7.

- `scripts/common/html_split.py`: split a learn.microsoft.com page into per-version sections by heading regex (parameterized: heading level, version regex, date regex).
- `scripts/fetchers/visual_studio.py` (parameterized by year): use splitter for 2026.

**Test in isolation:**
1. Run with `--ide visual-studio-2026` → one file per `17.X.Y` section.
2. Assert: `17.14.31.json` has correct `release_date` parsed from "Released April 21st, 2026".
3. Schema validation, idempotency.

**Done when:** the HTML splitter works on one real page, ready for reuse.

**Additional steps (CI):**
- `.github/workflows/fetch-visual-studio-2026.yml`: cron + `workflow_dispatch`, direct push to main (per Decision A).
- Permissions: `contents: write`.

**Additional tests (CI):**
4. Trigger via `workflow_dispatch` on a branch — confirm green run.
5. Delete one local file, trigger again — confirm exactly that file is recommitted.
6. Trigger again — confirm "no changes" (no empty commits).

---

### MVP 6 — SSMS fetcher (reuse splitter)
**Why now:** validates that `html_split.py` is truly reusable.

- `scripts/fetchers/ssms.py` calls the splitter on `release-notes-22` and `release-notes-21` with `start_version: 21.0.0`.

**Test in isolation:**
1. Run → files in `data/sql-server-management-studio/`.
2. Assert: no files below `21.0.0` present (filter works).
3. Assert: `What's new` and `Bug fixes` subsections both appear in `body_markdown`.

**Done when:** splitter is proven reusable; SSMS data complete.

**Additional steps (CI):**
- `.github/workflows/fetch-ssms.yml`: cron + `workflow_dispatch`, direct push to main (per Decision A).
- Permissions: `contents: write`.

**Additional tests (CI):**
4. Trigger via `workflow_dispatch` on a branch — confirm green run.
5. Delete one local file, trigger again — confirm exactly that file is recommitted.
6. Trigger again — confirm "no changes" (no empty commits).

---

### MVP 7 — Visual Studio 2022 (full history)
**Why last among fetchers:** requires crawling `release-history` + older per-major archived pages with potentially varying HTML. Highest risk; isolated here so it doesn't block earlier MVPs.

- Extend `visual_studio.py` to walk history page links and apply the splitter (with per-page heading-regex overrides as needed).

**Test in isolation:**
1. Run → files spanning 17.0–17.14.
2. Assert: at least one file from each major `17.0`…`17.14` exists.
3. Spot-check 3 random older releases for body content.

**Done when:** full 2022 backfill present.

**Additional steps (CI):**
- `.github/workflows/fetch-visual-studio-2022.yml`: cron + `workflow_dispatch`, direct push to main (per Decision A).
- Permissions: `contents: write`.

**Additional tests (CI):**
4. Trigger via `workflow_dispatch` on a branch — confirm green run.
5. Delete one local file, trigger again — confirm exactly that file is recommitted.
6. Trigger again — confirm "no changes" (no empty commits).

---

### MVP 8 — JetBrains workflow + schema-lint CI
**Note:** Workflows for all IDEs except JetBrains were added alongside their respective fetchers (MVPs 1–7). This MVP closes the gap and adds cross-IDE CI guardrails.

- `.github/workflows/fetch-jetbrains.yml`: cron + `workflow_dispatch`, direct push to main (per Decision A). Permissions: `contents: write`.
- Add `.github/workflows/lint-schema.yml` running `jsonschema` over all `data/**/*.json` on PR.
- Optional `fetch-all.yml` via `workflow_call`.

**Test in isolation:**
1. Trigger `fetch-jetbrains.yml` via `workflow_dispatch` on a branch — confirm green run.
2. Open a PR that adds a malformed JSON → lint fails.
3. Manually dispatch `fetch-all.yml` — confirm all IDE workflows run.

**Done when:** all 8 IDEs run on schedule and PRs are guarded by schema lint.

---

### MVP 9 — Hardening
- `--force-backfill` flag (re-process existing files).
- Per-IDE `copilot_mentions` regex override in config.
- Error-budget: fetcher returns partial success, `run.py` exits non-zero only on hard errors.

---

### MVP dependency graph

```
MVP 0 ──┬─► MVP 1 (Eclipse + CI)
        ├─► MVP 2 (JetBrains)
        ├─► MVP 3 (Xcode + Vim + CI)
        └─► MVP 4 (VS Code + CI) ──► MVP 5 (VS 2026 + CI) ──┬─► MVP 6 (SSMS + CI)
                                                             └─► MVP 7 (VS 2022 + CI)

All of MVP 1–7 ──► MVP 8 (JetBrains CI + schema-lint) ──► MVP 9
```

MVPs 1–4 are mutually independent after MVP 0 — easy to parallelize across contributors.
